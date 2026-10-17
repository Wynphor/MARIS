"""
Pipeline 路由 — 任务持久化 + 结构化 prompt + Stage Machine

每个执行都创建 PipelineTask 记录，AI 阶段通过 SSE 实时推送。
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session
from ...models.pipeline import PipelineRequest
from ...models.workspace import Workspace
from ...db.database import get_session
from ...services.task_service import TaskService
from ...services.stage_registry import (
    STAGE_DEPENDENCIES,
    STAGE_STATUS_MAP,
    DEFAULT_PIPELINE_ORDER,
    STATUS_PROGRESSION,
    check_dependencies,
    get_stage_stream,
    get_completed_stages,
    mark_stage_completed,
    wrap_with_auto_compile,
    compile_stream,
    compile_latex_sse,
)
import json

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/execute")
async def execute_pipeline_stage(request: PipelineRequest, session: Session = Depends(get_session)):
    """执行 Pipeline 的指定阶段，自动创建持久化任务记录。"""
    from ...services.snapshot_service import SnapshotService

    # 验证 workspace 存在
    ws = session.get(Workspace, request.workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace {request.workspace_id} not found")

    ws_id = request.workspace_id
    stage = request.stage

    # ── 检查前置依赖（Stage Machine） ──
    check_dependencies(ws, stage)

    # ── 创建持久化任务记录 ──
    task = TaskService.create_task(
        workspace_id=ws_id,
        stage=stage,
        mode=request.mode,
        provider=request.provider,
        model_name=request.model_name or "",
    )

    # ── 预阶段快照 ──
    if stage in ["decompose", "code-gen", "write"]:
        try:
            SnapshotService.create_snapshot(ws_id, f"pre_{stage}")
        except Exception:
            pass

    # ════════════════════════════════════════════════════
    # Stage 路由（每个返回 SSE 流）
    # ════════════════════════════════════════════════════

    # ── 非 AI Stage（直接返回结果） ──
    if stage == "ingest":
        from ...services.data_service import DataService
        file_name = request.keywords or "data.xlsx"
        result = DataService.ingest_raw_data(ws_id, file_name)
        async def res_gen():
            yield f"data: [TASK] {task.id}\n\n"
            yield f"data: {json.dumps(result)}\n\n"
            task.mark_completed(json.dumps(result))
            TaskService.update_task(task)
            if result.get("status") != "error":
                TaskService.mark_workspace_stage_completed(ws_id, stage)
            yield f"data: [TASK_COMPLETE] {task.id} ({task.status})\n\n"
        return StreamingResponse(res_gen(), media_type="text/event-stream")

    elif stage == "audit":
        from ...services.compliance_service import ComplianceService
        result = ComplianceService.audit_workspace(ws_id)
        async def res_gen():
            yield f"data: [TASK] {task.id}\n\n"
            yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
            task.mark_completed(json.dumps(result, ensure_ascii=False))
            TaskService.update_task(task)
            if result.get("status") != "error":
                TaskService.mark_workspace_stage_completed(ws_id, stage)
            yield f"data: [TASK_COMPLETE] {task.id} ({task.status})\n\n"
        return StreamingResponse(res_gen(), media_type="text/event-stream")

    elif stage == "pack":
        from ...services.submission_service import SubmissionService
        result = SubmissionService.pack_submission(ws_id)
        async def res_gen():
            yield f"data: [TASK] {task.id}\n\n"
            yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
            task.mark_completed(json.dumps(result, ensure_ascii=False))
            TaskService.update_task(task)
            if result.get("status") != "error":
                TaskService.mark_workspace_stage_completed(ws_id, stage)
            yield f"data: [TASK_COMPLETE] {task.id} ({task.status})\n\n"
        return StreamingResponse(res_gen(), media_type="text/event-stream")

    elif stage == "figures":
        from ...services.figure_audit_service import FigureAuditService
        stream = TaskService.wrap_sse_stream(task, FigureAuditService.audit_figures(ws_id))
        return StreamingResponse(stream, media_type="text/event-stream")

    elif stage == "archive":
        from ...services.knowledge_service import KnowledgeService
        stream = TaskService.wrap_sse_stream(task, KnowledgeService.archive_learnings(ws_id))
        return StreamingResponse(stream, media_type="text/event-stream")

    elif stage == "knowledge-archive":
        from ...services.knowledge_service import KnowledgeService
        stream = TaskService.wrap_sse_stream(task, KnowledgeService.archive_learnings(ws_id))
        return StreamingResponse(stream, media_type="text/event-stream")

    elif stage == "figure-audit":
        from ...services.figure_audit_service import FigureAuditService
        stream = TaskService.wrap_sse_stream(task, FigureAuditService.audit_figures(ws_id))
        return StreamingResponse(stream, media_type="text/event-stream")

    # ── AI Stage（通过 TaskService 持久化 + SSE 流） ──

    elif stage == "claim-audit":
        from ...services.compliance_service import ComplianceService
        stream = TaskService.wrap_sse_stream(task, ComplianceService.paper_claim_audit(ws_id))
        return StreamingResponse(stream, media_type="text/event-stream")

    elif stage == "citation-audit":
        from ...services.compliance_service import ComplianceService
        stream = TaskService.wrap_sse_stream(task, ComplianceService.paper_citation_audit(ws_id))
        return StreamingResponse(stream, media_type="text/event-stream")

    elif stage == "decompose":
        from ...core.prompts import read_workspace_file
        from ...core.config import settings
        from pathlib import Path

        problem_text = ""

        # 1. Check workspace root for standard problem files
        for candidate in ["problem.md", "problem.txt", "problem.pdf"]:
            content = read_workspace_file(ws_id, candidate)
            if content:
                problem_text = content
                break

        # 2. If not found, scan raw/ directory for uploaded files
        if not problem_text:
            raw_dir = Path(settings.DATA_DIR) / ws_id / "raw"
            if raw_dir.exists():
                # Priority: .md > .txt > .pdf (text before binary)
                for ext in ("*.md", "*.txt"):
                    found = sorted(raw_dir.glob(ext))
                    if found:
                        content = read_workspace_file(ws_id, f"raw/{found[0].name}")
                        if content:
                            problem_text = content
                            break
                # Try PDFs — extract text if possible
                if not problem_text:
                    for pdf_path in sorted(raw_dir.glob("*.pdf")):
                        try:
                            import fitz  # PyMuPDF
                            doc = fitz.open(str(pdf_path))
                            pages_text = []
                            for page in doc:
                                pages_text.append(page.get_text())
                            doc.close()
                            text = "\n".join(pages_text).strip()
                            if text:
                                problem_text = text
                                break
                        except ImportError:
                            # PyMuPDF not installed, try pdftotext
                            try:
                                import subprocess
                                result = subprocess.run(
                                    ["pdftotext", str(pdf_path), "-"],
                                    capture_output=True, text=True, timeout=30
                                )
                                if result.returncode == 0 and result.stdout.strip():
                                    problem_text = result.stdout.strip()
                                    break
                            except Exception:
                                pass
                        except Exception:
                            pass

        # 3. Fallback to keywords parameter
        if not problem_text:
            problem_text = request.keywords or ""

        if not problem_text:
            task.mark_failed("No problem text provided")
            TaskService.update_task(task)
            raise HTTPException(
                status_code=422,
                detail="未找到赛题文本。请先上传赛题文件（PDF/TXT/MD），或通过 keywords 参数提供赛题描述。"
            )

        from ...services.ai_service import AIService
        stream = TaskService.wrap_sse_stream(task, AIService.run_decompose(request, problem_text))
        return StreamingResponse(stream, media_type="text/event-stream")

    elif stage == "model-select":
        from ...services.ai_service import AIService
        stream = TaskService.wrap_sse_stream(task, AIService.run_model_select(request))
        return StreamingResponse(stream, media_type="text/event-stream")

    elif stage == "code-gen":
        from ...services.ai_service import AIService
        from ...services.python_runner import PythonRunner
        from ...core.config import settings
        from pathlib import Path

        async def res_gen():
            # Phase 1: Generate code
            async for chunk in AIService.run_code_gen(request):
                yield chunk

            # Phase 2: Auto-run generated code (if enabled)
            if getattr(request, 'run_generated_code', True):
                yield "data: [SYSTEM] 代码生成完成，开始自动运行...\n\n"
                ws_dir = Path(settings.DATA_DIR) / ws_id
                src_dir = ws_dir / "src"
                solve_script = src_dir / "solve_all.py"

                if solve_script.exists():
                    max_fix_attempts = 3
                    for attempt in range(max_fix_attempts):
                        yield f"data: [SYSTEM] 运行 solve_all.py (尝试 {attempt + 1}/{max_fix_attempts})...\n\n"
                        run_output = []
                        run_success = False
                        try:
                            async for line in PythonRunner.run_solver(ws_id, "solve_all.py", timeout=180):
                                run_output.append(line)
                                yield line
                            output_text = "".join(run_output)
                            # 三重判定：退出码 + 错误标记 + 结果产物
                            # 检查结构化退出码
                            exit_code = 0
                            for line in run_output:
                                if "[EXIT_CODE]" in line:
                                    try:
                                        exit_code = int(line.split("[EXIT_CODE]")[1].strip())
                                    except ValueError:
                                        pass
                            has_error_marker = (
                                "[ERROR]" in output_text
                                or "Traceback" in output_text
                                or exit_code != 0
                            )
                            has_result_files = (
                                (ws_dir / "output" / "tables").exists() and any((ws_dir / "output" / "tables").glob("*.csv"))
                            ) or (
                                (ws_dir / "output" / "figures").exists() and any((ws_dir / "output" / "figures").glob("*.png"))
                            ) or (
                                (ws_dir / "output" / "results.json").exists()
                            )
                            if not has_error_marker:
                                if has_result_files:
                                    run_success = True
                                    yield "data: [INFO] 检测到结果产物（CSV/PNG/results.json）。\n\n"
                                else:
                                    # 无错误但无产物 — 不算成功，触发修复
                                    run_success = False
                                    yield "data: [WARNING] 运行无错误但未检测到标准结果产物（output/tables/*.csv、output/figures/*.png、output/results.json）。触发修复...\n\n"
                        except Exception as e:
                            yield f"data: [ERROR] 运行异常: {str(e)}\n\n"

                        if run_success:
                            yield "data: [SUCCESS] solve_all.py 运行成功！\n\n"
                            # 验证或生成 results.json
                            results_json = ws_dir / "output" / "results.json"
                            results_json.parent.mkdir(parents=True, exist_ok=True)

                            # 检查脚本是否自己生成了 results.json
                            if results_json.exists():
                                try:
                                    with open(results_json, "r", encoding="utf-8") as f:
                                        script_result = json.load(f)
                                    # Schema 校验：必须有 status 字段
                                    if "status" not in script_result:
                                        script_result["status"] = "success"
                                        script_result["_schema_note"] = "auto-added by MathModel-Engine"
                                    with open(results_json, "w", encoding="utf-8") as f:
                                        json.dump(script_result, f, ensure_ascii=False, indent=2)
                                    yield f"data: [INFO] results.json schema 校验通过。\n\n"
                                except (json.JSONDecodeError, OSError):
                                    yield "data: [WARNING] results.json 格式无效，重新生成。\n\n"
                                    results_json.unlink(missing_ok=True)

                            # 如果脚本没生成，由系统生成
                            if not results_json.exists():
                                result_summary = {
                                    "status": "success",
                                    "script": "solve_all.py",
                                    "attempt": attempt + 1,
                                    "output_lines": len(run_output),
                                    "has_tables": any((ws_dir / "output" / "tables").glob("*.csv")) if (ws_dir / "output" / "tables").exists() else False,
                                    "has_figures": any((ws_dir / "output" / "figures").glob("*.png")) if (ws_dir / "output" / "figures").exists() else False,
                                    "generated_by": "MathModel-Engine",
                                }
                                with open(results_json, "w", encoding="utf-8") as f:
                                    json.dump(result_summary, f, ensure_ascii=False, indent=2)
                            break

                        # Phase 3: Fix code on failure
                        if attempt < max_fix_attempts - 1:
                            yield f"data: [SYSTEM] 运行失败，AI 修复中 (第 {attempt + 1} 次)...\n\n"
                            current_code = ""
                            try:
                                with open(solve_script, "r", encoding="utf-8") as f:
                                    current_code = f.read()
                            except Exception:
                                break

                            error_text = "".join(run_output[-50:])
                            fix_system = (
                                "你是 Python 代码修复专家。根据错误信息修复数学建模脚本。\n"
                                "输出完整修复后代码。\n"
                                "使用 artifact 协议：<artifact path=\"src/solve_all.py\">完整代码</artifact>"
                            )
                            fix_user = (
                                f"## 当前代码\n```python\n{current_code}\n```\n\n"
                                f"## 错误输出\n```\n{error_text}\n```\n\n"
                                "请修复代码，输出完整可运行的修复后代码。"
                            )
                            async for chunk in AIService.run_stage_with_prompts(request, fix_system, fix_user):
                                yield chunk
                            yield "data: [SYSTEM] AI 修复完成，重新运行...\n\n"
                        else:
                            yield f"data: [WARNING] {max_fix_attempts} 次修复后仍未成功，请手动检查代码。\n\n"
                else:
                    yield "data: [WARNING] 未找到 solve_all.py，跳过自动运行。\n\n"

            task.mark_completed("code-gen with auto-run")
            TaskService.update_task(task)
            TaskService.mark_workspace_stage_completed(ws_id, stage)
            yield f"data: [TASK_COMPLETE] {task.id} ({task.status})\n\n"

        return StreamingResponse(res_gen(), media_type="text/event-stream")

    elif stage == "write":
        from ...services.ai_service import AIService
        stream = TaskService.wrap_sse_stream(task, AIService.run_write(request))
        return StreamingResponse(
            wrap_with_auto_compile(stream, ws_id),
            media_type="text/event-stream",
        )

    elif stage == "compile":
        return StreamingResponse(
            compile_stream(task, ws_id),
            media_type="text/event-stream",
        )

    elif stage == "format-check":
        from ...services.ai_service import AIService
        from ...core.format_profiles import check_latex_compliance
        from ...core.prompts import read_workspace_file
        from ...core.config import settings

        # 先运行确定性格式检查
        tex_content = read_workspace_file(ws_id, "paper/main.tex") or ""
        comp_type = "国赛"  # 默认
        try:
            config_path = Path(settings.DATA_DIR) / ws_id / "config.json"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    comp_type = cfg.get("competition_type", "国赛")
        except Exception:
            pass

        det_result = check_latex_compliance(tex_content, comp_type)

        async def format_check_stream():
            # 先输出确定性检查结果
            yield f"data: [INFO] 格式合规检查 ({comp_type}): {'通过' if det_result['passed'] else '有问题'}\n\n"
            for issue in det_result.get("issues", []):
                yield f"data: [{issue['level']}] {issue['rule']}: {issue['detail']}\n\n"

            # 再运行 LLM 深度检查
            async for chunk in AIService.run_format_check(request):
                yield chunk

            task.mark_completed(json.dumps(det_result, ensure_ascii=False))
            TaskService.update_task(task)
            TaskService.mark_workspace_stage_completed(ws_id, stage)
            yield f"data: [TASK_COMPLETE] {task.id} ({task.status})\n\n"

        return StreamingResponse(format_check_stream(), media_type="text/event-stream")

    elif stage == "review":
        from ...services.review_service import ReviewService
        rounds = request.review_rounds or 2
        stream = TaskService.wrap_sse_stream(task, ReviewService.run_adversarial_review(ws_id, "all", max_rounds=rounds))
        return StreamingResponse(stream, media_type="text/event-stream")

    elif stage == "auto-improve":
        from ...services.orchestrator_service import OrchestratorService
        stream = TaskService.wrap_sse_stream(task, OrchestratorService.run_improvement_loop(ws_id))
        return StreamingResponse(stream, media_type="text/event-stream")

    elif stage == "validate":
        from ...services.simulation_service import SimulationService
        val_type = request.keywords or "sensitivity"
        stream = TaskService.wrap_sse_stream(task, SimulationService.run_validation(ws_id, val_type))
        return StreamingResponse(stream, media_type="text/event-stream")

    elif stage == "preprocess":
        from ...services.data_service import DataService
        stream = TaskService.wrap_sse_stream(task, DataService.preprocess_data(ws_id, request.keywords))
        return StreamingResponse(stream, media_type="text/event-stream")

    elif stage == "figure-gen":
        from ...services.figure_service import FigureService
        fig_type = request.keywords or "auto"
        stream = TaskService.wrap_sse_stream(task, FigureService.generate_figures(ws_id, fig_type))
        return StreamingResponse(stream, media_type="text/event-stream")

    elif stage == "paper-ref":
        from ...services.paper_reference_service import PaperReferenceService
        problem_type = request.keywords or "优化类"
        result = PaperReferenceService.search_papers(problem_type)
        async def ref_gen():
            yield f"data: [TASK] {task.id}\n\n"
            yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
            task.mark_completed(json.dumps(result, ensure_ascii=False)[:2000])
            TaskService.update_task(task)
            TaskService.mark_workspace_stage_completed(ws_id, stage)
            yield f"data: [TASK_COMPLETE] {task.id} ({task.status})\n\n"
        return StreamingResponse(ref_gen(), media_type="text/event-stream")

    else:
        task.mark_failed(f"Unsupported stage: {stage}")
        TaskService.update_task(task)
        raise HTTPException(status_code=400, detail=f"Unsupported stage: {stage}")


# ════════════════════════════════════════════════════
# 一键全流程编排
# ════════════════════════════════════════════════════

@router.post("/run-all")
async def run_all_stages(
    workspace_id: str,
    stages: str = "",
    problem_text: str = "",
    start_from: str = "",
    session: Session = Depends(get_session),
):
    """
    一键全流程：按顺序自动执行多个 stage。

    参数:
      - workspace_id: 工作区 ID
      - stages: 逗号分隔的 stage 列表（留空则使用默认全流程）
      - problem_text: 可选的赛题文本
      - start_from: UX-1 恢复执行 — 从指定 stage 开始，跳过已完成的
      - problem_text: 赛题文本（decompose 需要）

    返回 SSE 流，包含每个 stage 的执行结果。
    """
    ws = session.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # 确定要执行的 stages
    if stages:
        stage_list = [s.strip() for s in stages.split(",") if s.strip()]
    else:
        stage_list = DEFAULT_PIPELINE_ORDER.copy()

    # UX-1: Resume logic — skip stages before start_from
    skip_stages = set()
    if start_from and start_from in stage_list:
        start_idx = stage_list.index(start_from)
        skip_stages = set(stage_list[:start_idx])

    # Also skip stages whose target status is already achieved
    already_done = get_completed_stages(stage_list, ws.status, ws.completed_stages)

    # If user explicitly set start_from, override: only skip stages BEFORE start_from
    # (don't skip start_from itself even if status says it's done)
    if start_from and start_from in stage_list:
        already_done = {s for s in already_done if s in skip_stages and s != start_from}

    async def run_all_generator():
        yield f"data: ╔══════════════════════════════════════════════════╗\n\n"
        yield f"data: ║  MathModel-Engine 全流程编排                    ║\n\n"
        yield f"data: ║  Workspace: {workspace_id[:30]}            ║\n\n"
        yield f"data: ║  Stages: {len(stage_list)} 个                         ║\n\n"
        if skip_stages:
            yield f"data: ║  Resume from: {start_from:<34}║\n\n"
        yield f"data: ╚══════════════════════════════════════════════════╝\n\n"

        completed = 0
        failed = 0
        skipped = 0

        for idx, stage_name in enumerate(stage_list, 1):
            # UX-1: Skip already-completed stages or stages before start_from
            if stage_name in already_done:
                yield f"data: [{idx}/{len(stage_list)}] SKIP {stage_name} (already completed)\n\n"
                skipped += 1
                continue
            yield f"data: \n\n"
            yield f"data: ─── [{idx}/{len(stage_list)}] Stage: {stage_name} ───\n\n"

            # 构造 request
            req = PipelineRequest(
                workspace_id=workspace_id,
                stage=stage_name,
                mode="API",
                keywords=problem_text if stage_name == "decompose" else "",
            )

            # 创建任务
            task = TaskService.create_task(
                workspace_id=workspace_id,
                stage=stage_name,
                mode="API",
            )
            task.mark_running()
            TaskService.update_task(task)

            output_buffer = ""
            has_error = False

            try:
                # 根据 stage 选择正确的执行方法
                stream = get_stage_stream(stage_name, req, workspace_id, problem_text)
                if stream is None:
                    yield f"data: [SKIP] stage '{stage_name}' 不支持自动编排，跳过。\n\n"
                    task.mark_cancelled()
                    TaskService.update_task(task)
                    continue

                async for chunk in stream:
                    yield chunk
                    # 收集输出
                    if chunk.startswith("data: ") and not any(
                        chunk.startswith(p) for p in
                        ["data: [TASK]", "data: [STATS]", "data: [INFO]",
                         "data: [DONE]", "data: ╔", "data: ║", "data: ╚", "data: ──"]
                    ):
                        content = chunk[6:].strip()
                        if content:
                            output_buffer += content + "\n"
                    if "[ERROR]" in chunk:
                        has_error = True

                # 自动落盘
                if output_buffer and not has_error:
                    from ...services.output_persistence_service import OutputPersistenceService
                    saved = OutputPersistenceService.save_stage_output(
                        workspace_id, stage_name, output_buffer
                    )
                    if saved:
                        yield f"data: [SAVED] {saved}\n\n"

                if has_error:
                    failed += 1
                    task.mark_failed("Stage completed with errors")
                    # 关键阶段失败时中断 pipeline
                    CRITICAL_STAGES = {"decompose", "model-select", "code-gen", "write", "pack"}
                    if stage_name in CRITICAL_STAGES:
                        yield f"data: [ERROR] 关键阶段 '{stage_name}' 失败，中断全流程。\n\n"
                        break
                    else:
                        yield f"data: [WARNING] 阶段 '{stage_name}' 有错误，继续执行下一阶段。\n\n"
                else:
                    completed += 1
                    task.mark_completed(output_buffer[:2000])
                    # 自动更新 workspace 阶段完成历史和粗粒度状态
                    mark_stage_completed(ws, stage_name)
                    session.add(ws)
                    session.commit()

                TaskService.update_task(task)

            except Exception as e:
                failed += 1
                task.mark_failed(str(e))
                TaskService.update_task(task)
                yield f"data: [ERROR] Stage '{stage_name}' 异常: {str(e)}\n\n"
                yield f"data: [INFO] 跳过，继续执行下一阶段。\n\n"

        # 最终总结
        yield f"data: \n\n"
        yield f"data: ════════════════════════════════════════\n\n"
        yield f"data: [COMPLETE] 全流程执行完毕！\n\n"
        yield f"data: [SUMMARY] 成功: {completed}, 失败: {failed}, 跳过: {skipped}, 总计: {len(stage_list)}\n\n"

        final_status = ws.status
        yield f"data: [STATUS] Workspace 状态: {final_status}\n\n"
        yield f"data: {json.dumps({'completed': completed, 'failed': failed, 'skipped': skipped, 'total': len(stage_list), 'status': final_status}, ensure_ascii=False)}\n\n"

    return StreamingResponse(run_all_generator(), media_type="text/event-stream")


@router.post("/{workspace_id}/approve")
async def approve_stage(workspace_id: str, session: Session = Depends(get_session)):
    """
    人工审批通过当前阶段 → 更新 workspace 状态到下一阶段。
    用于人工审核暂停机制。
    """
    ws = session.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # 找到最近一次已完成的任务
    recent_tasks = TaskService.get_workspace_tasks(workspace_id, limit=5)
    latest = next((t for t in recent_tasks if t.status == "COMPLETED"), None)
    if not latest:
        raise HTTPException(status_code=422, detail="没有已完成的任务可审批。")

    # 更新 workspace 阶段完成历史和粗粒度状态
    mark_stage_completed(ws, latest.stage)
    session.add(ws)
    session.commit()
    session.refresh(ws)

    return {
        "message": f"阶段 '{latest.stage}' 已审批通过",
        "workspace_status": ws.status,
        "task_id": latest.id,
    }


@router.post("/{workspace_id}/reject")
async def reject_stage(
    workspace_id: str,
    feedback: str = "",
    session: Session = Depends(get_session),
):
    """
    人工拒绝当前阶段 → 标记任务为失败，提供反馈。
    """
    ws = session.get(Workspace, workspace_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    recent_tasks = TaskService.get_workspace_tasks(workspace_id, limit=5)
    latest = next((t for t in recent_tasks if t.status == "COMPLETED"), None)
    if not latest:
        raise HTTPException(status_code=422, detail="没有已完成的任务可拒绝。")

    latest.status = "REJECTED"
    latest.error_message = feedback or "人工拒绝"
    TaskService.update_task(latest)

    return {
        "message": f"阶段 '{latest.stage}' 已拒绝",
        "feedback": feedback,
        "task_id": latest.id,
    }


@router.get("/stages")
async def list_stages():
    """列出所有支持的 Pipeline 阶段及依赖关系。"""
    stages_info = [
        {"name": "ingest", "description": "数据导入（Excel/CSV → JSON）", "ai_required": False, "depends_on": []},
        {"name": "audit", "description": "合规性审查（身份泄露检测）", "ai_required": False, "depends_on": []},
        {"name": "preprocess", "description": "数据预处理（缺失值/异常值/标准化）", "ai_required": True, "depends_on": ["ingest"]},
        {"name": "decompose", "description": "赛题拆解", "ai_required": True, "depends_on": []},
        {"name": "model-select", "description": "模型推荐", "ai_required": True, "depends_on": ["decompose"]},
        {"name": "paper-ref", "description": "获奖范文检索", "ai_required": False, "depends_on": ["decompose"]},
        {"name": "code-gen", "description": "代码生成", "ai_required": True, "depends_on": ["model-select"]},
        {"name": "figure-gen", "description": "图表生成（AI 生成 + 沙箱执行）", "ai_required": True, "depends_on": ["code-gen"]},
        {"name": "write", "description": "论文写作（自动编译）", "ai_required": True, "depends_on": ["model-select"]},
        {"name": "compile", "description": "LaTeX 编译（后处理 + xelatex）", "ai_required": False, "depends_on": ["write"]},
        {"name": "review", "description": "红蓝对抗审查（可配置轮数）", "ai_required": True, "depends_on": ["write"]},
        {"name": "format-check", "description": "格式检查", "ai_required": True, "depends_on": ["write"]},
        {"name": "claim-audit", "description": "数值声明审计（LLM 交叉验证）", "ai_required": True, "depends_on": ["write"]},
        {"name": "citation-audit", "description": "参考文献审计（LLM 交叉验证）", "ai_required": True, "depends_on": ["write"]},
        {"name": "figure-audit", "description": "图表质量审计（LLM 审查）", "ai_required": True, "depends_on": ["figure-gen"]},
        {"name": "auto-improve", "description": "自动改进循环", "ai_required": True, "depends_on": ["review"]},
        {"name": "validate", "description": "敏感性分析", "ai_required": False, "depends_on": ["code-gen"]},
        {"name": "figures", "description": "图表审计（基础检查）", "ai_required": False, "depends_on": ["code-gen"]},
        {"name": "pack", "description": "提交打包", "ai_required": False, "depends_on": ["write", "format-check"]},
        {"name": "archive", "description": "赛后知识沉淀（LLM 归档）", "ai_required": True, "depends_on": ["pack"]},
        {"name": "knowledge-archive", "description": "赛后知识沉淀（LLM 归档）", "ai_required": True, "depends_on": ["pack"]},
    ]
    return {"stages": stages_info}
