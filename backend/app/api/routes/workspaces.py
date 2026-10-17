from fastapi import APIRouter, HTTPException, status, Depends, Body, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from sqlmodel import Session, select
from typing import List, Dict, Any
from ...models.workspace import Workspace, WorkspaceCreate, FileNode
from ...services.workspace_service import WorkspaceService
from ...services.competition_config_service import CompetitionConfigService
from ...db.database import get_session
from pathlib import Path
from ...core.config import settings
import json
import os
import shutil
import io
import zipfile

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

@router.post("/triage", summary="7.1 Multi-Problem Triage")
async def triage_problems(payload: Dict[str, Any] = Body(...)):
    """
    多赛题智能选题分析。

    接收多个赛题描述（文本或 PDF 路径），使用 LLM 分析：
    - 数据需求（是否需要外部采集）
    - 技术难度（数学建模、编程、写作复杂度）
    - 团队匹配度（基于团队技能标签）
    - 预期产出（哪些模型适用、论文结构复杂度）

    返回结构化决策矩阵和推荐。
    """
    problem_files = payload.get("problems", [])
    team_skills = payload.get("team_skills", [])
    workspace_id = payload.get("workspace_id", "")

    if not problem_files:
        raise HTTPException(status_code=400, detail="No problems provided for triage.")

    # Read problem contents
    problem_texts = []
    for pf in problem_files:
        if isinstance(pf, dict):
            problem_texts.append({"id": pf.get("id", ""), "text": pf.get("text", ""), "title": pf.get("title", "")})
        elif isinstance(pf, str) and workspace_id:
            # Try to read as file path
            from ...core.prompts import read_workspace_file
            content = read_workspace_file(workspace_id, pf)
            if content:
                problem_texts.append({"id": pf, "text": content[:3000], "title": pf})
            else:
                problem_texts.append({"id": pf, "text": pf, "title": pf})
        else:
            problem_texts.append({"id": str(pf), "text": str(pf), "title": str(pf)})

    async def triage_generator():
        yield "data: [INFO] 开始多赛题智能选题分析...\n\n"
        yield f"data: [INFO] 分析 {len(problem_texts)} 个赛题，团队技能: {', '.join(team_skills) if team_skills else '未指定'}...\n\n"

        try:
            from ...services.api_client_service import APIClientService

            problems_desc = ""
            for i, pt in enumerate(problem_texts):
                problems_desc += f"\n### 赛题 {pt['id']}\n{pt['text'][:2000]}\n"

            skills_desc = ", ".join(team_skills) if team_skills else "通用（数学建模、Python 编程、论文写作）"

            triage_system = (
                "你是数学建模竞赛选题专家。根据赛题描述和团队技能，生成详细的选题决策矩阵。\n\n"
                "输出 JSON 格式：\n"
                "```json\n"
                "{\n"
                "  \"decision_matrix\": [\n"
                "    {\n"
                "      \"problem\": \"题号\",\n"
                "      \"title\": \"题目简述\",\n"
                "      \"type\": \"题型分类（优化/预测/评价/分类/其他）\",\n"
                "      \"data_requirement\": \"数据需求描述\",\n"
                "      \"data_source\": \"是否需要外部采集（是/否/部分）\",\n"
                "      \"difficulty\": \"难度（1-5）\",\n"
                "      \"math_complexity\": \"数学复杂度（1-5）\",\n"
                "      \"coding_complexity\": \"编程复杂度（1-5）\",\n"
                "      \"team_match\": \"团队匹配度（高/中/低）\",\n"
                "      \"match_reason\": \"匹配/不匹配原因\",\n"
                "      \"recommended_models\": [\"适用的数学模型列表\"],\n"
                "      \"estimated_hours\": \"预估工作时间\",\n"
                "      \"risks\": [\"主要风险点\"],\n"
                "      \"recommendation\": \"综合推荐意见\"\n"
                "    }\n"
                "  ],\n"
                "  \"suggested_choice\": \"推荐选择的题号\",\n"
                "  \"reasoning\": \"选择理由\"\n"
                "}\n"
                "```\n\n"
                "评估维度：数据可获取性、数学建模难度、编程实现难度、论文写作难度、团队匹配度。"
            )

            triage_user = (
                f"## 团队技能\n{skills_desc}\n\n"
                f"## 赛题列表\n{problems_desc}\n\n"
                "请分析每个赛题，生成选题决策矩阵。"
            )

            collected = ""
            async for chunk in APIClientService.call_llm(
                system=triage_system,
                user=triage_user,
                temperature=0.3,
            ):
                collected += chunk
                yield f"data: {chunk}\n\n"

            # Try to extract structured JSON
            import re
            json_match = re.search(r'\{[\s\S]*"decision_matrix"[\s\S]*\}', collected)
            if json_match:
                try:
                    result = json.loads(json_match.group())

                    # Validate schema
                    matrix = result.get("decision_matrix", [])
                    if not isinstance(matrix, list):
                        matrix = []
                    for item in matrix:
                        item.setdefault("problem", "")
                        item.setdefault("type", "未知")
                        item.setdefault("difficulty", "未知")
                        item.setdefault("team_match", "未知")
                        item.setdefault("recommendation", "")
                        item.setdefault("data_requirement", "")
                        item.setdefault("recommended_models", [])
                        item.setdefault("risks", [])
                    result["decision_matrix"] = matrix
                    result.setdefault("suggested_choice", "")
                    result.setdefault("reasoning", "")
                    result.setdefault("analyzed_at", __import__("datetime").datetime.now().isoformat())
                    result.setdefault("team_skills", team_skills)
                    result.setdefault("problems_count", len(problem_texts))

                    yield f"\ndata: [RESULT] {json.dumps(result, ensure_ascii=False)}\n\n"

                    # Persist to workspace if workspace_id provided
                    if workspace_id:
                        try:
                            from ...core.config import settings
                            from pathlib import Path
                            ws_dir = Path(settings.DATA_DIR) / workspace_id
                            ws_dir.mkdir(parents=True, exist_ok=True)
                            out_path = ws_dir / "triage_decision_matrix.json"
                            with open(out_path, "w", encoding="utf-8") as f:
                                json.dump(result, f, ensure_ascii=False, indent=2)
                            yield f"data: [INFO] 决策矩阵已保存到 triage_decision_matrix.json\n\n"
                        except Exception as save_err:
                            yield f"data: [WARNING] 决策矩阵保存失败: {save_err}\n\n"

                except json.JSONDecodeError:
                    pass

            yield "data: [SUCCESS] 选题分析完成。\n\n"

        except Exception as e:
            yield f"data: [ERROR] 选题分析失败: {str(e)}\n\n"
            # Fallback: basic analysis
            matrix = {
                "decision_matrix": [
                    {
                        "problem": pt["id"],
                        "title": pt["title"][:50],
                        "type": "待分析",
                        "difficulty": "未知",
                        "team_match": "待评估",
                        "recommendation": "需要更多分析"
                    } for pt in problem_texts
                ],
                "suggested_choice": problem_texts[0]["id"] if problem_texts else "",
                "reasoning": "AI 分析失败，请手动评估"
            }
            yield f"data: [RESULT] {json.dumps(matrix, ensure_ascii=False)}\n\n"

    return StreamingResponse(triage_generator(), media_type="text/event-stream")

@router.post("/", response_model=Workspace, status_code=status.HTTP_201_CREATED)
async def create_workspace(workspace_in: WorkspaceCreate, session: Session = Depends(get_session)):
    try:
        # Create physical folder structure and workspace object
        ws = WorkspaceService.create_workspace_folder(workspace_in)

        # UX-5: Auto-create standard directory template
        CompetitionConfigService.init_workspace(ws.id)

        session.add(ws)
        session.commit()
        session.refresh(ws)
        return ws
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[Workspace])
async def list_workspaces(session: Session = Depends(get_session)):
    workspaces = session.exec(select(Workspace)).all()
    return workspaces

@router.get("/{workspace_id}/tree", response_model=List[FileNode])
async def get_workspace_tree(workspace_id: str, session: Session = Depends(get_session)):
    ws = session.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    return WorkspaceService.get_file_tree(workspace_id)


# ============================================================
# Dashboard
# ============================================================

@router.get("/{workspace_id}/dashboard")
async def get_workspace_dashboard(workspace_id: str, session: Session = Depends(get_session)):
    """
    获取 workspace 的仪表盘数据：状态总览、各阶段完成度、最近任务、文件统计。
    """
    ws = session.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    from ...services.task_service import TaskService
    from ...core.prompts import read_workspace_file

    # 最近任务
    recent_tasks = TaskService.get_workspace_tasks(workspace_id, limit=10)
    tasks_summary = []
    for t in recent_tasks:
        tasks_summary.append({
            "id": t.id,
            "stage": t.stage,
            "status": t.status,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "duration_seconds": t.duration_seconds,
        })

    # 各阶段完成状态
    stage_checklist = {}
    stage_files = {
        "decompose":      "problem_decomposition.md",
        "model-select":   "model_recommendation.md",
        "write":          "paper/main.tex",
        "format-check":   "format_check_report.md",
        "paper-ref":      "paper_reference_report.md",
    }
    for stage_name, file_path in stage_files.items():
        content = read_workspace_file(workspace_id, file_path)
        stage_checklist[stage_name] = {
            "completed": content is not None,
            "file": file_path,
            "size_chars": len(content) if content else 0,
        }

    # 检查是否有编译好的 PDF
    pdf_exists = (settings.DATA_DIR / workspace_id / "paper" / "main.pdf").exists()
    stage_checklist["compile"] = {
        "completed": pdf_exists,
        "file": "paper/main.pdf",
    }

    # 文件统计
    ws_path = settings.DATA_DIR / workspace_id
    file_stats = {
        "src_files": len(list((ws_path / "src").rglob("*.py"))) if (ws_path / "src").exists() else 0,
        "tex_files": len(list((ws_path / "paper").rglob("*.tex"))) if (ws_path / "paper").exists() else 0,
        "figures": len(list((ws_path / "output" / "figures").glob("*"))) if (ws_path / "output" / "figures").exists() else 0,
        "raw_data": len(list((ws_path / "raw").glob("*"))) if (ws_path / "raw").exists() else 0,
    }

    # 总体进度
    completed_stages = sum(1 for v in stage_checklist.values() if v["completed"])
    total_stages = len(stage_checklist)
    progress_pct = round(completed_stages / total_stages * 100) if total_stages > 0 else 0

    return {
        "workspace": {
            "id": ws.id,
            "title": ws.title,
            "question_id": ws.question_id,
            "problem_type": ws.problem_type,
            "status": ws.status,
            "created_at": ws.created_at.isoformat() if ws.created_at else None,
        },
        "progress": {
            "completed_stages": completed_stages,
            "total_stages": total_stages,
            "percentage": progress_pct,
        },
        "stage_checklist": stage_checklist,
        "file_stats": file_stats,
        "recent_tasks": tasks_summary,
        "next_steps": _get_next_steps(stage_checklist),
    }


def _get_next_steps(checklist: dict) -> list:
    """根据当前完成状态推荐下一步操作。"""
    steps = []
    if not checklist.get("decompose", {}).get("completed"):
        steps.append({"action": "decompose", "description": "上传赛题文件后执行拆解"})
    elif not checklist.get("model-select", {}).get("completed"):
        steps.append({"action": "model-select", "description": "基于拆解结果推荐模型"})
    elif not checklist.get("write", {}).get("completed"):
        steps.append({"action": "write", "description": "生成论文 LaTeX"})
    elif not checklist.get("compile", {}).get("completed"):
        steps.append({"action": "compile", "description": "编译论文 PDF"})
    elif not checklist.get("format-check", {}).get("completed"):
        steps.append({"action": "format-check", "description": "检查竞赛格式合规性"})
    else:
        steps.append({"action": "pack", "description": "打包提交材料"})
    return steps


# ============================================================
# 文件上传
# ============================================================

# 支持的文件类型
ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".doc",
    ".xlsx", ".xls", ".csv", ".txt",
    ".md", ".tex", ".py", ".json",
    ".png", ".jpg", ".jpeg",
}


@router.post("/{workspace_id}/upload")
async def upload_files(
    workspace_id: str,
    files: List[UploadFile] = File(...),
    subfolder: str = "raw",
    session: Session = Depends(get_session),
):
    """
    上传文件到 workspace。

    - 支持多文件上传
    - PDF 自动提取文本内容保存为 .txt
    - 文件保存到 data/{workspace_id}/{subfolder}/
    - 文件大小限制: 50MB
    """
    ws = session.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Validate subfolder doesn't escape workspace
    if ".." in subfolder or "/" in subfolder or "\\" in subfolder:
        raise HTTPException(status_code=400, detail="Invalid subfolder name")

    ws_base = (settings.DATA_DIR / workspace_id).resolve()
    upload_dir = (ws_base / subfolder).resolve()
    if not str(upload_dir).startswith(str(ws_base)):
        raise HTTPException(status_code=403, detail="Access denied")
    upload_dir.mkdir(parents=True, exist_ok=True)

    # File size limit: 50MB per file
    MAX_FILE_SIZE = 50 * 1024 * 1024

    results = []
    for file in files:
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            results.append({
                "filename": file.filename,
                "status": "rejected",
                "reason": f"不支持的文件类型: {ext}",
            })
            continue

        # Sanitize filename: strip path separators and traversal
        safe_name = Path(file.filename).name  # strips directory components
        if ".." in safe_name or not safe_name:
            results.append({"filename": file.filename, "status": "rejected", "reason": "Invalid filename"})
            continue

        # Save file
        save_path = upload_dir / safe_name
        # Verify resolved path stays within upload_dir
        if not str(save_path.resolve()).startswith(str(upload_dir.resolve())):
            results.append({"filename": file.filename, "status": "rejected", "reason": "Path traversal"})
            continue

        content = await file.read()

        # File size check
        if len(content) > MAX_FILE_SIZE:
            results.append({
                "filename": file.filename,
                "status": "rejected",
                "reason": f"File too large ({len(content) / 1024 / 1024:.1f}MB > 50MB)",
            })
            continue

        with open(save_path, "wb") as f:
            f.write(content)

        result = {
            "filename": file.filename,
            "status": "uploaded",
            "path": str(save_path),
            "size_bytes": len(content),
        }

        # PDF 自动提取文本
        if ext == ".pdf":
            text = _extract_pdf_text(save_path)
            if text:
                txt_path = save_path.with_suffix(".txt")
                txt_path.write_text(text, encoding="utf-8")
                result["text_extracted"] = True
                result["text_file"] = str(txt_path)
                result["text_preview"] = text[:500]
            else:
                result["text_extracted"] = False
                result["text_note"] = "PDF 文本提取需要安装 PyPDF2: pip install PyPDF2"

        # Excel/CSV 自动预览
        elif ext in (".xlsx", ".xls", ".csv"):
            preview = _preview_tabular(save_path)
            if preview:
                result["preview"] = preview

        results.append(result)

    # ── 标准化：自动生成 problem.md 到 workspace 根目录 ──
    ws_root = settings.DATA_DIR / workspace_id
    problem_md = ws_root / "problem.md"
    if not problem_md.exists():
        # 优先从上传的 .md/.txt 文件中提取
        for r in results:
            if r.get("status") != "uploaded":
                continue
            fname = r.get("filename", "")
            fpath = Path(r.get("path", ""))
            if fname.lower().endswith((".md", ".txt")) and fpath.exists():
                try:
                    text = fpath.read_text(encoding="utf-8", errors="replace")
                    if len(text) > 50:
                        problem_md.write_text(text, encoding="utf-8")
                        break
                except Exception:
                    pass
        # 其次从 PDF 提取的 .txt 中获取
        if not problem_md.exists():
            for r in results:
                if r.get("text_extracted") and r.get("text_file"):
                    try:
                        text = Path(r["text_file"]).read_text(encoding="utf-8", errors="replace")
                        if len(text) > 50:
                            problem_md.write_text(text, encoding="utf-8")
                            break
                    except Exception:
                        pass

    return {"workspace_id": workspace_id, "uploaded": len(results), "files": results}


@router.get("/{workspace_id}/files")
async def list_uploaded_files(workspace_id: str, subfolder: str = "raw"):
    """列出 workspace 中已上传的文件。"""
    # Validate subfolder doesn't escape workspace
    if ".." in subfolder or "/" in subfolder or "\\" in subfolder:
        raise HTTPException(status_code=400, detail="Invalid subfolder name")

    ws_base = (settings.DATA_DIR / workspace_id).resolve()
    upload_dir = (ws_base / subfolder).resolve()
    if not str(upload_dir).startswith(str(ws_base)):
        raise HTTPException(status_code=403, detail="Access denied")

    if not upload_dir.exists():
        return {"files": []}
    files = []
    for f in sorted(upload_dir.iterdir()):
        if f.is_file():
            files.append({
                "name": f.name,
                "size_bytes": f.stat().st_size,
                "suffix": f.suffix,
            })
    return {"files": files}


def _extract_pdf_text(pdf_path: Path) -> str:
    """尝试从 PDF 提取文本。"""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(str(pdf_path))
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n\n".join(text_parts)
    except ImportError:
        pass
    try:
        import subprocess
        result = subprocess.run(
            ["pdftotext", str(pdf_path), "-"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


def _preview_tabular(file_path: Path) -> dict:
    """预览 Excel/CSV 文件的前几行。"""
    try:
        import pandas as pd
        ext = file_path.suffix.lower()
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(file_path, nrows=5)
        else:
            df = pd.read_csv(file_path, nrows=5)
        return {
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "sample_rows": df.to_dict(orient="records"),
            "total_preview_rows": len(df),
        }
    except Exception:
        return None


# ============================================================
# UX-4: Competition Config
# ============================================================

@router.get("/{workspace_id}/config")
async def get_workspace_config(workspace_id: str, session: Session = Depends(get_session)):
    """Get competition configuration for this workspace."""
    ws = session.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return CompetitionConfigService.get_config(workspace_id)


@router.put("/{workspace_id}/config")
async def update_workspace_config(
    workspace_id: str,
    updates: Dict[str, Any] = Body(...),
    session: Session = Depends(get_session),
):
    """Update competition configuration (partial update, only provided fields)."""
    ws = session.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return CompetitionConfigService.update_config(workspace_id, updates)


# ============================================================
# UX-2 / UX-3: Download & Preview
# ============================================================

@router.get("/{workspace_id}/download/pdf")
async def download_pdf(workspace_id: str, session: Session = Depends(get_session)):
    """Download the compiled paper as PDF."""
    ws = session.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    pdf_path = settings.DATA_DIR / workspace_id / "paper" / "main.pdf"
    if not pdf_path.exists():
        raise HTTPException(
            status_code=404,
            detail="PDF not found. Run 'compile' stage first."
        )

    filename = f"{ws.title or workspace_id}_paper.pdf"
    return FileResponse(
        path=str(pdf_path),
        filename=filename,
        media_type="application/pdf",
    )


@router.get("/{workspace_id}/preview/pdf")
async def preview_pdf(workspace_id: str, session: Session = Depends(get_session)):
    """Preview the compiled paper PDF inline in browser."""
    ws = session.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    pdf_path = settings.DATA_DIR / workspace_id / "paper" / "main.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )


@router.get("/{workspace_id}/download/zip")
async def download_workspace_zip(workspace_id: str, session: Session = Depends(get_session)):
    """
    Download the entire workspace as a ZIP archive.
    Includes: paper/, src/, data/, output/, docs/, config.json
    """
    ws = session.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    ws_path = settings.DATA_DIR / workspace_id
    if not ws_path.exists():
        raise HTTPException(status_code=404, detail="Workspace directory not found")

    # Build ZIP in memory
    buf = io.BytesIO()
    include_dirs = ["paper", "src", "data", "output", "docs"]

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add config.json at root
        config_path = ws_path / "config.json"
        if config_path.exists():
            zf.write(config_path, "config.json")

        # Add top-level markdown files
        for md in ws_path.glob("*.md"):
            zf.write(md, md.name)

        # Add each directory
        for dir_name in include_dirs:
            dir_path = ws_path / dir_name
            if not dir_path.exists():
                continue
            for file_path in dir_path.rglob("*"):
                if file_path.is_file():
                    # Skip very large binary files (>50MB)
                    if file_path.stat().st_size > 50 * 1024 * 1024:
                        continue
                    arcname = str(file_path.relative_to(ws_path))
                    zf.write(file_path, arcname)

    buf.seek(0)
    # Sanitize filename for Content-Disposition header
    safe_title = "".join(c for c in (ws.title or workspace_id) if c.isalnum() or c in " _-").strip()
    if not safe_title:
        safe_title = workspace_id
    filename = f"{safe_title}.zip"

    from fastapi.responses import Response
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ============================================================
# D4: 数据探索
# ============================================================

@router.get("/{workspace_id}/data/preview")
async def preview_data(
    workspace_id: str,
    file: str = "",
    rows: int = 20,
    session: Session = Depends(get_session),
):
    """
    Preview data files in the workspace.
    Returns column info, statistics, and sample rows.
    """
    ws = session.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    ws_path = settings.DATA_DIR / workspace_id

    # Find the data file
    data_file = None
    if file:
        candidate = ws_path / file
        if not str(candidate.resolve()).startswith(str(ws_path.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")
        if candidate.exists():
            data_file = candidate
    else:
        # Auto-find first CSV/Excel in data/raw/
        raw_dir = ws_path / "data" / "raw"
        if raw_dir.exists():
            for ext in ("*.csv", "*.xlsx", "*.xls"):
                files = sorted(raw_dir.glob(ext))
                if files:
                    data_file = files[0]
                    break

    if not data_file:
        raise HTTPException(status_code=404, detail="No data file found")

    try:
        import pandas as pd
        ext = data_file.suffix.lower()
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(data_file, nrows=rows)
        else:
            for enc in ["utf-8", "gbk", "gb2312", "latin1"]:
                try:
                    df = pd.read_csv(data_file, nrows=rows, encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise HTTPException(status_code=422, detail="Could not decode file")
    except ImportError:
        raise HTTPException(status_code=500, detail="pandas not installed")
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Build response
    columns = []
    for col in df.columns:
        columns.append({
            "name": str(col),
            "dtype": str(df[col].dtype),
            "null_count": int(df[col].isnull().sum()),
            "null_pct": round(df[col].isnull().sum() / len(df) * 100, 1),
            "unique": int(df[col].nunique()),
        })

    return {
        "file": data_file.name,
        "rows": len(df),
        "columns": columns,
        "sample": df.head(min(10, len(df))).to_dict(orient="records"),
        "statistics": df.describe(include="all").fillna("").to_dict(),
    }
