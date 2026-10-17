"""
OrchestratorService — 自动改进循环（真实 LLM 调用）

循环: Compile → Review → AI Fix → Recompile
对应 skills-mathmodel/auto-review-adaptation 中的 auto-paper-improvement-loop
"""
import asyncio
import json
from typing import AsyncGenerator
from .latex_service import LatexService
from .review_service import ReviewService
from .api_client_service import APIClientService
from ..core.prompts import read_workspace_file, get_model_for_stage
from ..core.config import settings


class OrchestratorService:

    @staticmethod
    async def run_improvement_loop(
        workspace_id: str,
        max_rounds: int = 3,
    ) -> AsyncGenerator[str, None]:
        """
        自动论文改进循环：

        每轮:
          1. 编译当前 LaTeX → 检查是否成功
          2. 对抗审查（Red Team → Blue Team）
          3. 如果有 P0 问题，AI 自动修复论文
          4. 重新编译

        终止条件:
          - 无 P0 问题（审查通过）
          - 达到最大轮次
          - 编译失败且无法自动修复
        """
        yield f"data: [INFO] 启动自动改进循环 (workspace: {workspace_id}, max_rounds: {max_rounds})\n\n"

        if max_rounds < 1:
            max_rounds = 1

        for round_idx in range(1, max_rounds + 1):
            yield f"data: ╔══════════════════════════════════════╗\n\n"
            yield f"data: ║  改进轮次 {round_idx}/{max_rounds}                          ║\n\n"
            yield f"data: ╚══════════════════════════════════════╝\n\n"

            # ── Step 1: 编译 ──
            yield f"data: [STEP 1] 编译 LaTeX...\n\n"
            comp_result = await LatexService.post_process_and_compile(workspace_id)

            if comp_result.get("status") == "failed":
                yield f"data: [WARNING] 编译失败。尝试自动修复...\n\n"
                fix_result = LatexService.auto_fix_compile(workspace_id)
                if fix_result.get("status") == "failed":
                    yield f"data: [ERROR] 自动修复失败。错误: {fix_result.get('errors', [])}\n\n"
                    yield f"data: [INFO] 尝试让 AI 修复 TeX 错误...\n\n"
                    # 让 AI 修复编译错误
                    async for chunk in OrchestratorService._ai_fix_tex_errors(
                        workspace_id, fix_result.get("errors", [])
                    ):
                        yield chunk
                    # 重新编译
                    comp_result = await LatexService.post_process_and_compile(workspace_id)

            tables_wrapped = comp_result.get("tables_wrapped", 0)
            placeholders = comp_result.get("placeholders_found", [])
            if tables_wrapped > 0:
                yield f"data: [INFO] 已自动包裹 {tables_wrapped} 个表格。\n\n"
            if placeholders:
                yield f"data: [WARNING] 发现占位符: {', '.join(placeholders)}\n\n"

            # ── Step 2: 对抗审查 ──
            yield f"data: [STEP 2] 运行对抗审查...\n\n"
            red_feedback = ""
            async for chunk in ReviewService.run_adversarial_review(
                workspace_id, "paper", max_rounds=1
            ):
                # 收集 Red Team 的反馈用于后续修复
                if "[RED TEAM]" in chunk and "[INFO]" not in chunk:
                    content = chunk.replace("data: ", "").strip()
                    if content and "审查完成" not in content:
                        red_feedback += content + "\n"
                yield chunk

            # ── Step 3: 判断是否需要 AI 修复 ──
            has_p0 = any(
                keyword in red_feedback
                for keyword in ["P0", "强制修改", "严重", "致命"]
            )

            if not has_p0 and round_idx > 1:
                yield f"data: [SUCCESS] ✅ 审查通过，无 P0 问题。改进循环结束。\n\n"
                break

            if round_idx < max_rounds:
                yield f"data: [STEP 3] AI 自动修复论文...\n\n"
                async for chunk in OrchestratorService._ai_fix_paper(
                    workspace_id, red_feedback
                ):
                    yield chunk

            yield f"data: [ROUND {round_idx}] 轮次完成。\n\n"

        # 最终统计
        final_comp = await LatexService.post_process_and_compile(workspace_id)
        final_result = {
            "status": "finished",
            "rounds_executed": round_idx,
            "pdf_generated": final_comp.get("pdf_generated", False),
            "tables_wrapped": final_comp.get("tables_wrapped", 0),
            "placeholders_remaining": final_comp.get("placeholders_found", []),
        }
        yield f"data: [SUCCESS] 自动改进循环完成。\n\n"
        yield f"data: {json.dumps(final_result)}\n\n"

    @staticmethod
    async def _ai_fix_paper(
        workspace_id: str,
        review_feedback: str,
    ) -> AsyncGenerator[str, None]:
        """让 AI 根据审查反馈修复论文。"""
        tex_content = read_workspace_file(workspace_id, "paper/main.tex")
        if not tex_content:
            yield "data: [ERROR] 无法读取 main.tex\n\n"
            return

        system_prompt = (
            "你是数学建模论文修改专家。审稿人指出了以下问题，"
            "你需要修改论文来解决这些问题。\n\n"
            "## 修改原则\n"
            "- 只修改有问题的部分，保持整体结构不变\n"
            "- 输出修改后的完整 LaTeX 代码\n"
            "- 严禁引入占位符（此处省略、推导略、TODO）\n"
            "- 保持三线表格式\n"
            "- 保持所有公式和引用完整"
        )
        user_prompt = (
            f"## 当前论文 (前8000字符)\n{tex_content[:8000]}\n\n"
            f"## 审稿人反馈\n{review_feedback[:4000]}\n\n"
            "请输出修改后的完整 LaTeX 代码。"
        )

        config = get_model_for_stage("write")
        fixed_content = ""

        async for chunk in APIClientService.call_llm_stream(
            provider=config["provider"],
            workspace_id=workspace_id,
            stage="auto-fix",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=config["model"],
            temperature=0.3,
        ):
            if chunk.startswith("data: ") and not chunk.startswith("data: ["):
                fixed_content += chunk[6:]
            yield chunk

        # 如果 AI 返回了修改后的内容，保存
        if fixed_content and len(fixed_content) > 1000:
            # 尝试提取 LaTeX 代码
            from pathlib import Path
            import difflib
            import shutil
            from datetime import datetime
            tex_path = settings.DATA_DIR / workspace_id / "paper" / "main.tex"
            # 简单判断：如果包含 \documentclass 则认为是完整 LaTeX
            if "\\documentclass" in fixed_content:
                # 提取 \documentclass 到 \end{document}
                start = fixed_content.find("\\documentclass")
                end = fixed_content.rfind("\\end{document}")
                if end > start:
                    new_tex = fixed_content[start:end + len("\\end{document}")]

                    # Backup before overwrite
                    backup_dir = settings.DATA_DIR / workspace_id / "paper" / "backups"
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = backup_dir / f"main_{timestamp}.tex"
                    if tex_path.exists():
                        shutil.copy2(tex_path, backup_path)

                    # Compute diff
                    old_lines = tex_content.splitlines(keepends=True)
                    new_lines = new_tex.splitlines(keepends=True)
                    diff = list(difflib.unified_diff(
                        old_lines, new_lines,
                        fromfile="main.tex (before)",
                        tofile="main.tex (after)",
                        n=3,
                    ))

                    # Apply
                    tex_path.write_text(new_tex, encoding="utf-8")
                    yield f"data: [INFO] AI 修复已应用到 main.tex ({len(new_tex)} 字符)。\n\n"
                    yield f"data: [INFO] 备份: paper/backups/{backup_path.name}\n\n"

                    # Report changes
                    if diff:
                        added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
                        removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
                        yield f"data: [INFO] 变更: +{added} 行, -{removed} 行\n\n"
                        # Show first 20 lines of diff
                        diff_preview = "".join(diff[:20])
                        if diff_preview:
                            yield f"data: [INFO] Diff 预览:\n{diff_preview}\n\n"
            else:
                yield f"data: [WARNING] AI 输出未包含完整 LaTeX，跳过自动应用。请人工审查。\n\n"

    @staticmethod
    async def _ai_fix_tex_errors(
        workspace_id: str,
        errors: list,
    ) -> AsyncGenerator[str, None]:
        """让 AI 修复 LaTeX 编译错误。"""
        tex_content = read_workspace_file(workspace_id, "paper/main.tex")
        if not tex_content:
            yield "data: [ERROR] 无法读取 main.tex\n\n"
            return

        errors_text = "\n".join(
            f"- 行 {e.get('line', '?')}: {e.get('message', '未知错误')} (上下文: {e.get('context', '')})"
            for e in errors[:10]
        )

        system_prompt = (
            "你是 LaTeX 编译错误修复专家。分析编译错误并修复 TeX 源码。\n"
            "输出修复后的完整 LaTeX 代码。"
        )
        user_prompt = (
            f"## 编译错误\n{errors_text}\n\n"
            f"## 当前 TeX 源码 (前6000字符)\n{tex_content[:6000]}\n\n"
            "请修复这些错误并输出完整的 LaTeX 代码。"
        )

        config = get_model_for_stage("write")
        fixed_content = ""

        async for chunk in APIClientService.call_llm_stream(
            provider=config["provider"],
            workspace_id=workspace_id,
            stage="fix-tex-errors",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=config["model"],
            temperature=0.2,
        ):
            if chunk.startswith("data: ") and not chunk.startswith("data: ["):
                fixed_content += chunk[6:]
            yield chunk

        if fixed_content and "\\documentclass" in fixed_content:
            from pathlib import Path
            tex_path = settings.DATA_DIR / workspace_id / "paper" / "main.tex"
            start = fixed_content.find("\\documentclass")
            end = fixed_content.rfind("\\end{document}")
            if end > start:
                new_tex = fixed_content[start:end + len("\\end{document}")]
                tex_path.write_text(new_tex, encoding="utf-8")
                yield f"data: [INFO] TeX 错误修复已应用。\n\n"
