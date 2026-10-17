"""
Stage Registry — pipeline business logic extracted from routes.

Contains stage dependency graph, status mapping, stream generators,
and compile helpers used by the pipeline router.
"""
import json
from fastapi import HTTPException
from ..models.workspace import Workspace
from ..core.prompts import read_workspace_file

# ── Stage 依赖关系图（用于人工审核暂停机制） ──
STAGE_DEPENDENCIES = {
    "ingest": [],
    "audit": [],
    "decompose": [],
    "model-select": ["decompose"],
    "code-gen": ["model-select"],
    "preprocess": ["ingest", "decompose"],
    "write": ["model-select"],
    "figure-gen": ["code-gen"],
    "paper-ref": ["decompose"],
    "review": ["write"],
    "format-check": ["write"],
    "claim-audit": ["write", "code-gen"],
    "citation-audit": ["write"],
    "auto-improve": ["review"],
    "compile": ["write"],
    "validate": ["code-gen"],
    "figures": ["code-gen"],
    "figure-audit": ["figure-gen", "write"],
    "pack": ["write", "format-check"],
    "archive": ["pack"],
    "knowledge-archive": ["pack"],
}

# ── Stage 完成后 workspace 的目标状态 ──
STAGE_STATUS_MAP = {
    "decompose": "DECOMPOSED",
    "model-select": "MODELED",
    "preprocess": "MODELED",
    "paper-ref": "MODELED",
    "code-gen": "CODED",
    "validate": "CODED",
    "figures": "CODED",
    "write": "WRITTEN",
    "compile": "WRITTEN",
    "format-check": "CHECKED",
    "claim-audit": "CHECKED",
    "citation-audit": "CHECKED",
    "figure-audit": "CHECKED",
    "review": "REVIEWED",
    "auto-improve": "IMPROVED",
    "pack": "PACKED",
}

STATUS_PROGRESSION = [
    "INIT", "DECOMPOSED", "MODELED", "CODED", "WRITTEN",
    "REVIEWED", "CHECKED", "IMPROVED", "PACKED", "FINISHED",
]

# 默认全流程顺序（完整竞赛闭环）
DEFAULT_PIPELINE_ORDER = [
    "ingest",          # 0. 数据导入（自动检测 raw/ 中的数据文件）
    "decompose",       # 1. 赛题拆解
    "model-select",    # 2. 模型选择
    "preprocess",      # 3. 数据预处理 + EDA
    "paper-ref",       # 4. 范文参考检索
    "code-gen",        # 5. 代码生成 + 自动运行/修复
    "validate",        # 6. 敏感性分析/验证
    "figure-gen",      # 7. 图表生成（不是 figures/audit）
    "write",           # 8. 论文写作（含自动编译）
    "compile",         # 9. LaTeX 编译
    "format-check",    # 10. 格式检查
    "claim-audit",     # 11. 数值声明审计
    "citation-audit",  # 12. 引用审计
    "figure-audit",    # 13. 图表视觉审查
    "review",          # 14. 对抗审查
    "auto-improve",    # 15. 自动改进
    "pack",            # 16. 提交打包
]


def check_dependencies(ws: Workspace, stage: str):
    """检查前置阶段是否已完成（基于 workspace.status）。"""
    deps = STAGE_DEPENDENCIES.get(stage, [])
    if not deps:
        return  # 无依赖，直接通过
    for dep in deps:
        if not is_stage_completed(ws, dep):
            dep_status = STAGE_STATUS_MAP.get(dep, dep)
            raise HTTPException(
                status_code=422,
                detail=f"前置阶段 '{dep}' 未完成（当前状态: {ws.status}，需要: {dep_status}）。"
                       f"请先执行 '{dep}' 阶段。"
            )


def is_stage_completed(ws: Workspace, stage: str) -> bool:
    """Return whether a stage is complete using explicit history plus legacy status fallback."""
    if ws.has_stage_completed(stage):
        return True

    target_status = STAGE_STATUS_MAP.get(stage)
    if not target_status:
        return False
    current_idx = STATUS_PROGRESSION.index(ws.status) if ws.status in STATUS_PROGRESSION else -1
    target_idx = STATUS_PROGRESSION.index(target_status) if target_status in STATUS_PROGRESSION else -1
    return target_idx != -1 and target_idx <= current_idx


def mark_stage_completed(ws: Workspace, stage: str):
    """Mark explicit stage completion and advance coarse workspace status when appropriate."""
    ws.mark_stage_completed(stage)

    new_status = STAGE_STATUS_MAP.get(stage)
    if not new_status:
        return
    current_idx = STATUS_PROGRESSION.index(ws.status) if ws.status in STATUS_PROGRESSION else -1
    new_idx = STATUS_PROGRESSION.index(new_status) if new_status in STATUS_PROGRESSION else -1
    if new_idx > current_idx:
        ws.status = new_status


def get_completed_stages(stage_list: list, ws_status: str, completed_stages=None) -> set:
    """Compute the set of stages already satisfied by the current workspace status."""
    current_status_idx = STATUS_PROGRESSION.index(ws_status) if ws_status in STATUS_PROGRESSION else 0
    if isinstance(completed_stages, str):
        try:
            already_done = set(json.loads(completed_stages or "[]"))
        except json.JSONDecodeError:
            already_done = set()
    elif completed_stages:
        already_done = set(completed_stages)
    else:
        already_done = set()

    for s in stage_list:
        target_status = STAGE_STATUS_MAP.get(s)
        if target_status and target_status in STATUS_PROGRESSION:
            target_idx = STATUS_PROGRESSION.index(target_status)
            if target_idx <= current_status_idx:
                already_done.add(s)
    return already_done


async def _code_gen_with_auto_run(req, workspace_id: str):
    """code-gen + 自动运行 + 失败修复闭环（与 pipeline.py 单阶段逻辑一致）。"""
    from ..services.ai_service import AIService
    from ..services.python_runner import PythonRunner
    from ..core.config import settings
    from pathlib import Path
    import json

    ws_dir = Path(settings.DATA_DIR) / workspace_id

    # Phase 1: Generate code
    async for chunk in AIService.run_code_gen(req):
        yield chunk

    # Phase 2: Auto-run
    solve_script = ws_dir / "src" / "solve_all.py"
    if not solve_script.exists():
        yield "data: [WARNING] 未找到 solve_all.py，跳过自动运行。\n\n"
        return

    max_fix_attempts = 3
    for attempt in range(max_fix_attempts):
        yield f"data: [SYSTEM] 运行 solve_all.py (尝试 {attempt + 1}/{max_fix_attempts})...\n\n"
        run_output = []
        run_success = False
        exit_code = -1
        try:
            async for line in PythonRunner.run_solver(workspace_id, "solve_all.py", timeout=180):
                run_output.append(line)
                yield line
                if "[EXIT_CODE]" in line:
                    try:
                        exit_code = int(line.split("[EXIT_CODE]")[1].strip())
                    except ValueError:
                        pass
            output_text = "".join(run_output)
            has_error = "[ERROR]" in output_text or "Traceback" in output_text or exit_code != 0
            if not has_error:
                # 三重判定：无错误 + 有结果产物
                has_result_files = (
                    (ws_dir / "output" / "tables").exists() and any((ws_dir / "output" / "tables").glob("*.csv"))
                ) or (
                    (ws_dir / "output" / "figures").exists() and any((ws_dir / "output" / "figures").glob("*.png"))
                ) or (
                    (ws_dir / "output" / "results.json").exists()
                )
                if has_result_files:
                    run_success = True
                else:
                    run_success = False
                    yield "data: [WARNING] 无标准结果产物，触发修复...\n\n"
        except Exception as e:
            yield f"data: [ERROR] 运行异常: {str(e)}\n\n"

        if run_success:
            yield "data: [SUCCESS] solve_all.py 运行成功！\n\n"
            # 生成 results.json
            try:
                result_summary = {
                    "status": "success", "script": "solve_all.py",
                    "attempt": attempt + 1, "output_lines": len(run_output),
                    "has_tables": (ws_dir / "output" / "tables").exists(),
                    "has_figures": (ws_dir / "output" / "figures").exists(),
                }
                results_json = ws_dir / "output" / "results.json"
                results_json.parent.mkdir(parents=True, exist_ok=True)
                with open(results_json, "w", encoding="utf-8") as f:
                    json.dump(result_summary, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
            break

        if attempt < max_fix_attempts - 1:
            yield f"data: [SYSTEM] 运行失败，AI 修复中 (第 {attempt + 1} 次)...\n\n"
            current_code = ""
            try:
                current_code = solve_script.read_text(encoding="utf-8")
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
            async for chunk in AIService.run_stage_with_prompts(req, fix_system, fix_user):
                yield chunk
            yield "data: [SYSTEM] AI 修复完成，重新运行...\n\n"
        else:
            yield f"data: [WARNING] {max_fix_attempts} 次修复后仍未成功，请手动检查代码。\n\n"


def get_stage_stream(stage_name: str, req, workspace_id: str, problem_text: str):
    """根据 stage 名称获取对应的 SSE 流生成器。"""
    from ..services.ai_service import AIService
    from ..services.review_service import ReviewService
    from ..services.orchestrator_service import OrchestratorService
    from ..services.data_service import DataService
    from ..services.figure_service import FigureService
    from ..services.submission_service import SubmissionService
    from ..services.simulation_service import SimulationService
    from ..services.compliance_service import ComplianceService
    from ..services.figure_audit_service import FigureAuditService
    from ..services.knowledge_service import KnowledgeService
    from ..services.latex_service import LatexService
    from ..services.paper_reference_service import PaperReferenceService

    if stage_name == "decompose":
        # 读取赛题
        text = problem_text
        if not text:
            for candidate in ["problem.md", "problem.txt"]:
                content = read_workspace_file(workspace_id, candidate)
                if content:
                    text = content
                    break
        if not text:
            return None
        return AIService.run_decompose(req, text)

    elif stage_name == "model-select":
        return AIService.run_model_select(req)

    elif stage_name == "code-gen":
        return _code_gen_with_auto_run(req, workspace_id)

    elif stage_name == "write":
        return AIService.run_write(req)

    elif stage_name == "format-check":
        return AIService.run_format_check(req)

    elif stage_name == "review":
        rounds = req.review_rounds if req and req.review_rounds else 2
        return ReviewService.run_adversarial_review(workspace_id, "all", max_rounds=rounds)

    elif stage_name == "auto-improve":
        return OrchestratorService.run_improvement_loop(workspace_id)

    elif stage_name == "validate":
        return SimulationService.run_validation(workspace_id, "sensitivity")

    elif stage_name == "preprocess":
        return DataService.preprocess_data(workspace_id)

    elif stage_name == "figure-gen":
        return FigureService.generate_figures(workspace_id)

    elif stage_name == "paper-ref":
        problem_type = req.keywords if req and req.keywords else "优化类"
        async def _paper_ref_gen():
            result = PaperReferenceService.search_papers(problem_type)
            yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
        return _paper_ref_gen()

    # Previously unsupported stages — now wired up
    elif stage_name == "audit":
        async def _audit_gen():
            result = ComplianceService.audit_workspace(workspace_id)
            yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
        return _audit_gen()

    elif stage_name == "claim-audit":
        return ComplianceService.paper_claim_audit(workspace_id)

    elif stage_name == "citation-audit":
        return ComplianceService.paper_citation_audit(workspace_id)

    elif stage_name == "compile":
        async def _compile_gen():
            result = await LatexService.post_process_and_compile(workspace_id)
            yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
        return _compile_gen()

    elif stage_name == "pack":
        async def _pack_gen():
            result = SubmissionService.pack_submission(workspace_id)
            yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
        return _pack_gen()

    elif stage_name == "figures":
        return FigureAuditService.audit_figures(workspace_id)

    elif stage_name == "figure-audit":
        return FigureAuditService.audit_figures(workspace_id)

    elif stage_name == "archive":
        return KnowledgeService.archive_learnings(workspace_id)

    elif stage_name == "knowledge-archive":
        return KnowledgeService.archive_learnings(workspace_id)

    # Ingest: auto-detect data files in raw/
    elif stage_name == "ingest":
        from ..services.data_service import DataService
        from ..core.config import settings
        from pathlib import Path
        raw_dir = Path(settings.DATA_DIR) / workspace_id / "raw"
        if not raw_dir.exists():
            return None
        # Find first data file (csv, xlsx, xls)
        data_file = None
        for ext in ("*.csv", "*.xlsx", "*.xls"):
            found = sorted(raw_dir.glob(ext))
            if found:
                data_file = found[0].name
                break
        if not data_file:
            return None  # No data files found, skip ingest
        # Wrap dict return as async generator (run-all expects async stream)
        async def _ingest_gen():
            try:
                result = DataService.ingest_raw_data(workspace_id, data_file)
                yield f"data: [INFO] 数据导入完成: {data_file}\n\n"
                yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: [ERROR] 数据导入失败: {str(e)}\n\n"
        return _ingest_gen()

    return None


async def wrap_with_auto_compile(stream, workspace_id: str):
    """包装 SSE 流，write 完成后自动触发 LaTeX 编译。"""
    last_chunk = ""
    async for chunk in stream:
        last_chunk = chunk
        yield chunk
    # write 流结束后自动编译
    if last_chunk and "TASK_COMPLETE" in last_chunk:
        yield "data: [INFO] 论文生成完成，自动编译 LaTeX...\n\n"
        async for chunk in compile_latex_sse(workspace_id):
            yield chunk


async def compile_stream(task, workspace_id: str):
    """独立的编译 stage 流。"""
    yield f"data: [TASK] {task.id}\n\n"
    task.mark_running()
    from ..services.task_service import TaskService
    TaskService.update_task(task)
    result = {}
    async for chunk in compile_latex_sse(workspace_id):
        yield chunk
        if "[COMPILE_RESULT]" in chunk:
            try:
                result = json.loads(chunk.split("[COMPILE_RESULT] ")[1])
            except Exception:
                pass
    task.mark_completed(json.dumps(result, ensure_ascii=False)[:2000])
    TaskService.update_task(task)
    TaskService.mark_workspace_stage_completed(workspace_id, "compile")
    yield f"data: [TASK_COMPLETE] {task.id} ({task.status})\n\n"


async def compile_latex_sse(workspace_id: str):
    """执行 LaTeX 后处理 + 编译，以 SSE 格式输出结果。"""
    from ..services.latex_service import LatexService
    try:
        yield "data: [INFO] 执行 LaTeX 后处理（wrap tables + inject code + placeholder check）...\n\n"
        result = await LatexService.post_process_and_compile(workspace_id)
        if result.get("tables_wrapped", 0) > 0:
            yield f"data: [INFO] 已包裹 {result['tables_wrapped']} 个表格。\n\n"
        if result.get("placeholders_found"):
            yield f"data: [WARNING] 发现占位符: {', '.join(result['placeholders_found'])}\n\n"
        if result.get("errors"):
            yield f"data: [WARNING] 编译错误: {len(result['errors'])} 个。\n\n"
            for err in result["errors"][:3]:
                yield f"data: [TEX_ERROR] 行 {err.get('line', '?')}: {err.get('message', '')}\n\n"
        if result.get("pdf_generated"):
            yield "data: [SUCCESS] PDF 编译成功！\n\n"
        else:
            yield "data: [WARNING] PDF 未生成，可能存在编译错误。\n\n"
        yield f"data: [COMPILE_RESULT] {json.dumps(result, ensure_ascii=False)}\n\n"
    except Exception as e:
        yield f"data: [ERROR] 编译失败: {str(e)}\n\n"
