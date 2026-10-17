"""
AIService — AI 编排层

职责：
  - 接收 PipelineRequest，构建 prompt，分发到正确的 provider
  - CLI 模式: 调用本地 CLI (gemini/claude/aider 等)
  - API 模式: 调用 APIClientService 的真实 HTTP 流式接口
  - 自动选择 provider 和 model（基于 prompts.py 的 TASK_MODEL_MAP）
"""
import asyncio
import sys
import os
from typing import AsyncGenerator, Optional
from ..db.database import engine
from ..models.workspace import Workspace
from ..models.pipeline import PipelineRequest
from sqlmodel import Session
from .api_client_service import APIClientService
from ..core.cli_config import get_cli_command
from ..core.prompts import (
    get_model_for_stage,
    read_workspace_file,
    build_decompose_prompt,
    build_model_select_prompt,
    build_code_gen_prompt,
    build_write_prompt,
    build_format_check_prompt,
    build_claim_audit_prompt,
    build_citation_audit_prompt,
)


class AIService:

    # ----------------------------------------------------------
    # 主入口：Pipeline stage → prompt 构建 → 调用
    # ----------------------------------------------------------
    @staticmethod
    async def run_task(request: PipelineRequest, prompt: str) -> AsyncGenerator[str, None]:
        """
        Pipeline 路由调用此方法。

        - mode="CLI": 走本地 CLI 子进程
        - mode="API": 走 APIClientService 真实 HTTP 调用

        当 prompt 已由路由层构建好时，直接传入使用。
        """
        if request.mode == "CLI":
            async for chunk in AIService.run_cli_task(
                request.provider, prompt, request.workspace_id, request.stage
            ):
                yield chunk
        else:
            # API 模式：确定 provider 和 model
            stage_info = get_model_for_stage(request.stage)
            provider = request.provider if request.provider != "gemini" else stage_info["provider"]
            model = request.model_name or stage_info["model"]

            # 使用简单 system prompt（当路由层未提供结构化 prompt 时的 fallback）
            system_prompt = f"你是一个数学建模专家助手。当前任务阶段: {request.stage}。"
            user_prompt = prompt

            async for chunk in APIClientService.call_llm_stream(
                provider=provider,
                workspace_id=request.workspace_id,
                stage=request.stage,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model_name=model,
            ):
                yield chunk

            # 成功后更新 workspace 状态
            AIService._update_workspace_status(request.workspace_id, request.stage)

    # ----------------------------------------------------------
    # 结构化调用：使用 prompts.py 构建完整 prompt
    # ----------------------------------------------------------
    @staticmethod
    async def run_stage_with_prompts(
        request: PipelineRequest,
        system_prompt: str,
        user_prompt: str,
    ) -> AsyncGenerator[str, None]:
        """
        使用预构建的 system/user prompt 调用 LLM。
        由 pipeline 路由在构建好结构化 prompt 后调用。
        """
        if request.mode == "CLI":
            # CLI 模式下合并 system + user prompt
            full_prompt = f"System: {system_prompt}\n\nUser: {user_prompt}"
            async for chunk in AIService.run_cli_task(
                request.provider, full_prompt, request.workspace_id, request.stage
            ):
                yield chunk
        else:
            stage_info = get_model_for_stage(request.stage)
            provider = stage_info["provider"]
            model = request.model_name or stage_info["model"]

            async for chunk in APIClientService.call_llm_stream(
                provider=provider,
                workspace_id=request.workspace_id,
                stage=request.stage,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model_name=model,
            ):
                yield chunk

            AIService._update_workspace_status(request.workspace_id, request.stage)

    # ----------------------------------------------------------
    # 专用 stage 调用方法（从 workspace 读取文件 → 构建 prompt → 调用）
    # ----------------------------------------------------------
    @staticmethod
    async def run_decompose(request: PipelineRequest, problem_text: str) -> AsyncGenerator[str, None]:
        """Stage: decompose — 赛题拆解"""
        system, user = build_decompose_prompt(request.workspace_id, problem_text)
        async for chunk in AIService.run_stage_with_prompts(request, system, user):
            yield chunk

    @staticmethod
    async def run_model_select(request: PipelineRequest) -> AsyncGenerator[str, None]:
        """Stage: model-select — 模型推荐"""
        decomp = read_workspace_file(request.workspace_id, "problem_decomposition.md")
        if not decomp:
            yield "data: [ERROR] problem_decomposition.md 不存在，请先执行 decompose 阶段。\n\n"
            return
        system, user = build_model_select_prompt(request.workspace_id, decomp)
        async for chunk in AIService.run_stage_with_prompts(request, system, user):
            yield chunk

    @staticmethod
    async def run_code_gen(request: PipelineRequest) -> AsyncGenerator[str, None]:
        """Stage: code-gen — 代码生成"""
        rec = read_workspace_file(request.workspace_id, "model_recommendation.md")
        if not rec:
            yield "data: [ERROR] model_recommendation.md 不存在，请先执行 model-select 阶段。\n\n"
            return
        system, user = build_code_gen_prompt(
            request.workspace_id, rec,
            question_id=request.keywords or "C",
        )
        async for chunk in AIService.run_stage_with_prompts(request, system, user):
            yield chunk

    @staticmethod
    async def run_write(request: PipelineRequest) -> AsyncGenerator[str, None]:
        """Stage: write — 论文写作"""
        rec = read_workspace_file(request.workspace_id, "model_recommendation.md")
        if not rec:
            yield "data: [ERROR] model_recommendation.md 不存在。\n\n"
            return
        ref = read_workspace_file(request.workspace_id, "paper_reference_report.md") or ""
        system, user = build_write_prompt(request.workspace_id, rec, ref)
        async for chunk in AIService.run_stage_with_prompts(request, system, user):
            yield chunk

    @staticmethod
    async def run_format_check(request: PipelineRequest) -> AsyncGenerator[str, None]:
        """Stage: format-check — 格式检查"""
        tex = read_workspace_file(request.workspace_id, "paper/main.tex")
        if not tex:
            yield "data: [ERROR] paper/main.tex 不存在。\n\n"
            return
        system, user = build_format_check_prompt(request.workspace_id, tex)
        async for chunk in AIService.run_stage_with_prompts(request, system, user):
            yield chunk

    # ----------------------------------------------------------
    # CLI 模式（保留作为 fallback）
    # ----------------------------------------------------------
    @staticmethod
    async def run_cli_task(
        engine_name: str,
        prompt: str,
        workspace_id: str,
        stage: str,
    ) -> AsyncGenerator[str, None]:
        """通过本地 CLI 命令调用 AI。"""
        cmd = get_cli_command(engine_name, prompt)
        use_shell = sys.platform.startswith("win")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=os.getcwd(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            shell=use_shell,
        )
        yield f"data: [INFO] CLI Engine '{engine_name}' started...\n\n"
        yield f"data: [INFO] AI Thinking started...\n\n"

        while True:
            line = await process.stdout.readline()
            if not line:
                break
            decoded_line = line.decode("utf-8", errors="replace").strip()
            if decoded_line:
                yield f"data: {decoded_line}\n\n"

        await process.wait()

        if process.returncode == 0:
            AIService._update_workspace_status(workspace_id, stage)
            yield "data: [SUCCESS] Task completed successfully.\n\n"
        else:
            yield f"data: [ERROR] Task failed with exit code {process.returncode}.\n\n"

    # ----------------------------------------------------------
    # 辅助
    # ----------------------------------------------------------
    @staticmethod
    def _update_workspace_status(workspace_id: str, stage: str):
        """更新 workspace 的状态标记。"""
        status_map = {
            "decompose": "DECOMPOSED",
            "model-select": "MODELED",
            "code-gen": "CODED",
            "write": "WRITTEN",
            "review": "REVIEWED",
            "format-check": "CHECKED",
            "pack": "FINISHED",
        }
        new_status = status_map.get(stage, stage.upper())
        try:
            with Session(engine) as session:
                ws = session.get(Workspace, workspace_id)
                if ws:
                    ws.mark_stage_completed(stage)
                    progression = [
                        "INIT", "DECOMPOSED", "MODELED", "CODED", "WRITTEN",
                        "REVIEWED", "CHECKED", "IMPROVED", "PACKED", "FINISHED",
                    ]
                    current_idx = progression.index(ws.status) if ws.status in progression else -1
                    new_idx = progression.index(new_status) if new_status in progression else -1
                    if new_idx > current_idx:
                        ws.status = new_status
                    session.add(ws)
                    session.commit()
        except Exception:
            pass  # 状态更新失败不阻塞主流程
