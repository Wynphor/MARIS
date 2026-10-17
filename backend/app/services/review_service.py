"""
ReviewService — 红蓝对抗审查（真实 LLM 调用）

Red Team (DeepSeek): 严苛审稿人，找论文中的所有问题
Blue Team (MiMo/Pro): 作者防御，逐条回应并修补

修复:
  - Blue Team 的修改方案会反馈到下一轮 Red Team 审查内容中
  - max_rounds=0 不再崩溃
  - P0 检测更健壮
"""
from typing import AsyncGenerator
import json
import re
from .api_client_service import APIClientService
from ..core.prompts import (
    build_review_prompt,
    read_workspace_file,
    get_model_for_stage,
)


# Broader P0 detection keywords
_P0_KEYWORDS = [
    "P0", "P1", "强制修改", "严重", "致命", "关键缺陷",
    "不可接受", "必须修复", "紧急", "S1", "FATAL",
]


class ReviewService:

    @staticmethod
    def _has_p0_issues(text: str) -> bool:
        """Robust P0 detection: check for severity markers in structured output."""
        # Check for explicit severity labels
        for kw in _P0_KEYWORDS:
            if kw in text:
                return True
        # Check for severity field patterns in JSON-like output
        if re.search(r'"severity"\s*:\s*"(HIGH|CRITICAL|P0)"', text, re.IGNORECASE):
            return True
        return False

    @staticmethod
    async def run_adversarial_review(
        workspace_id: str,
        stage_to_review: str = "all",
        max_rounds: int = 2,
    ) -> AsyncGenerator[str, None]:
        """
        运行红蓝对抗审查循环。

        流程：
          1. 读取论文内容
          2. Red Team (DeepSeek) 审查 → 输出问题列表
          3. Blue Team (MiMo) 逐条回应 → 输出修改方案
          4. 将修改方案反馈到下一轮审查内容中
          5. 如果无 P0 问题，循环收敛
        """
        # Guard against invalid max_rounds
        if max_rounds < 1:
            max_rounds = 1

        yield f"data: [INFO] 启动红蓝对抗审查 (workspace: {workspace_id}, max_rounds: {max_rounds})\n\n"

        # 1. 读取论文内容
        tex_content = read_workspace_file(workspace_id, "paper/main.tex")
        if not tex_content:
            for alt_file in ["main_article.tex", "paper.md", "output/report.md"]:
                tex_content = read_workspace_file(workspace_id, alt_file)
                if tex_content:
                    break
        if not tex_content:
            yield "data: [ERROR] 未找到论文文件（paper/main.tex）。请先执行 write 阶段。\n\n"
            return

        # 初始审查内容（会在每轮追加 Blue Team 修复方案）
        content_for_review = tex_content[:12000]
        accumulated_fixes = ""

        all_attacks = []
        all_defenses = []
        round_idx = 0

        for round_idx in range(1, max_rounds + 1):
            yield f"data: ══════════════════════════════════════\n\n"
            yield f"data: [ROUND {round_idx}/{max_rounds}] 开始审查轮次\n\n"

            # ── Red Team 审查 ──
            yield f"data: [RED TEAM] 审稿人开始审查...\n\n"
            red_system, red_user = build_review_prompt(
                workspace_id, content_for_review, role="red"
            )
            # 追加前一轮的修复方案到审查上下文
            if accumulated_fixes:
                red_user = (
                    f"{red_user}\n\n"
                    f"## 上一轮作者的修改方案（请检查是否已充分修复）\n"
                    f"{accumulated_fixes[:3000]}\n"
                )

            red_config = get_model_for_stage("red-team")
            red_response = ""

            async for chunk in APIClientService.call_llm_stream(
                provider=red_config["provider"],
                workspace_id=workspace_id,
                stage=f"review-red-r{round_idx}",
                system_prompt=red_system,
                user_prompt=red_user,
                model_name=red_config["model"],
                temperature=0.3,
            ):
                if chunk.startswith("data: ") and not chunk.startswith("data: ["):
                    red_response += chunk[6:].strip()
                yield chunk

            all_attacks.append(red_response)
            yield f"data: \n\n"
            yield f"data: [RED TEAM] 审查完成。\n\n"

            # ── 检查是否还有严重问题 ──
            has_p0 = ReviewService._has_p0_issues(red_response)
            if not has_p0 and round_idx > 1:
                yield f"data: [INFO] 无 P0 级问题，审查收敛。\n\n"
                break

            # ── Blue Team 防御 ──
            yield f"data: [BLUE TEAM] 作者开始回应...\n\n"
            blue_system, blue_user = build_review_prompt(
                workspace_id, content_for_review, role="blue"
            )
            blue_user_with_attacks = (
                f"{blue_user}\n\n"
                f"## 审稿人的审查意见\n{red_response}\n\n"
                "请逐条回应以上审查意见，给出具体的修改方案。"
                "请明确指出要修改的具体文本和替换内容。"
            )
            blue_config = get_model_for_stage("blue-team")
            blue_response = ""

            async for chunk in APIClientService.call_llm_stream(
                provider=blue_config["provider"],
                workspace_id=workspace_id,
                stage=f"review-blue-r{round_idx}",
                system_prompt=blue_system,
                user_prompt=blue_user_with_attacks,
                model_name=blue_config["model"],
                temperature=0.4,
            ):
                if chunk.startswith("data: ") and not chunk.startswith("data: ["):
                    blue_response += chunk[6:].strip()
                yield chunk

            all_defenses.append(blue_response)
            accumulated_fixes += f"\n\n## Round {round_idx} 修改方案\n{blue_response}"
            yield f"data: \n\n"
            yield f"data: [BLUE TEAM] 回应完成。\n\n"

        # ── 总结 ──
        summary = {
            "status": "success",
            "rounds_completed": round_idx,
            "red_team_attacks": len(all_attacks),
            "blue_team_defenses": len(all_defenses),
            "accumulated_fixes_length": len(accumulated_fixes),
        }
        yield f"data: [SUCCESS] 对抗审查完成。\n\n"
        yield f"data: {json.dumps(summary)}\n\n"

    @staticmethod
    async def run_single_review(
        workspace_id: str,
        role: str = "red",
    ) -> AsyncGenerator[str, None]:
        """
        单次审查（不做循环），可用于 Red 或 Blue 单独调用。
        """
        tex_content = read_workspace_file(workspace_id, "paper/main.tex")
        if not tex_content:
            yield "data: [ERROR] 未找到论文文件。\n\n"
            return

        system, user = build_review_prompt(
            workspace_id, tex_content[:12000], role=role
        )
        stage_key = "red-team" if role == "red" else "blue-team"
        config = get_model_for_stage(stage_key)

        async for chunk in APIClientService.call_llm_stream(
            provider=config["provider"],
            workspace_id=workspace_id,
            stage=f"review-{role}",
            system_prompt=system,
            user_prompt=user,
            model_name=config["model"],
        ):
            yield chunk

    @staticmethod
    def get_review_template(template_name: str) -> str:
        """获取审查模板（保留向后兼容）。"""
        templates = {
            "math_rigor": "Focus exclusively on variable definitions and unit consistency.",
            "code_safety": "Check for edge cases in simulations and numerical stability.",
            "paper_style": "Check for academic tone and LaTeX formatting compliance.",
        }
        return templates.get(template_name, "General review.")
