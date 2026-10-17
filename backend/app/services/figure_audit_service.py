"""
FigureAuditService — 基于 LLM 的图表质量审查

读取 workspace/output/figures/ 中的图片，
用 LLM 分析图表标题、代码上下文，检查：
- 色盲安全、字体大小、图例完整性、坐标轴标注、学术规范
"""
from pathlib import Path
from typing import Dict, AsyncGenerator
import json

from .api_client_service import APIClientService
from ..core.prompts import read_workspace_file, get_model_for_stage
from ..core.config import settings


class FigureAuditService:

    @staticmethod
    async def audit_figures(workspace_id: str) -> AsyncGenerator[str, None]:
        """
        7.6 Figure Audit — LLM 驱动的图表质量审查。
        读取图表生成代码和输出文件列表，由 LLM 逐张审查。
        """
        ws_path = settings.DATA_DIR / workspace_id
        figures_dir = ws_path / "output" / "figures"

        if not figures_dir.exists():
            yield "data: [ERROR] Figures directory not found.\n\n"
            return

        images = sorted(figures_dir.glob("*.png")) + sorted(figures_dir.glob("*.pdf"))
        if not images:
            yield "data: [WARNING] No figures found to audit.\n\n"
            return

        yield f"data: [INFO] Auditing {len(images)} figures...\n\n"

        # 读取图表生成代码作为上下文
        code_content = ""
        code_path = ws_path / "src" / "generate_figures.py"
        if code_path.exists():
            code_content = code_path.read_text(encoding="utf-8", errors="replace")[:5000]

        # 读取论文中图表引用
        paper = read_workspace_file(workspace_id, "paper/main.tex") or ""
        fig_refs = []
        for line in paper.split("\n"):
            if "\\begin{figure}" in line or "\\includegraphics" in line or "\\caption" in line:
                fig_refs.append(line.strip())
        fig_context = "\n".join(fig_refs[:30])

        # 构建文件清单 + 本地硬检查
        file_list = []
        local_issues = []
        for img in images:
            size_kb = img.stat().st_size / 1024
            file_list.append(f"- {img.name} ({size_kb:.1f} KB)")

            # 本地硬检查
            if img.suffix.lower() == ".png":
                try:
                    from PIL import Image
                    pil_img = Image.open(str(img))
                    w, h = pil_img.size
                    dpi = pil_img.info.get("dpi", (72, 72))

                    # 尺寸检查
                    if w < 300 or h < 200:
                        local_issues.append(f"[WARN] {img.name}: 尺寸过小 ({w}x{h})，建议 >= 600x400")

                    # DPI 检查
                    dpi_val = dpi[0] if isinstance(dpi, tuple) else dpi
                    if dpi_val < 150:
                        local_issues.append(f"[WARN] {img.name}: DPI={dpi_val}，建议 >= 300")

                    # 空白图检测（标准差过低 = 几乎纯色）
                    import numpy as np
                    arr = np.array(pil_img.convert("L"))  # 灰度
                    std = arr.std()
                    if std < 5:
                        local_issues.append(f"[FAIL] {img.name}: 疑似空白图（像素标准差={std:.1f}）")

                    # 文件大小检查
                    if size_kb < 5:
                        local_issues.append(f"[WARN] {img.name}: 文件过小 ({size_kb:.1f}KB)，可能内容不足")
                    elif size_kb > 5000:
                        local_issues.append(f"[WARN] {img.name}: 文件过大 ({size_kb:.0f}KB)，可能影响 PDF 体积")

                    pil_img.close()
                except ImportError:
                    pass  # PIL not installed, skip local checks
                except Exception as e:
                    local_issues.append(f"[INFO] {img.name}: 本地检查失败 ({str(e)[:50]})")

        system_prompt = (
            "You are a figure quality auditor for a math modeling competition paper.\n"
            "Analyze each figure and check for:\n"
            "1. **Colorblind safety**: Are colormaps colorblind-friendly (viridis, cividis, magma)? "
            "Avoid red-green only distinctions.\n"
            "2. **Font size**: All text (axis labels, tick labels, legends) must be >= 10pt.\n"
            "3. **Legend**: Every multi-series plot must have a clear legend.\n"
            "4. **Axis labels**: Both axes must be labeled with units if applicable.\n"
            "5. **Title/caption**: Figure must have a descriptive caption.\n"
            "6. **Resolution**: PNG figures should be >= 300 DPI for print.\n"
            "7. **Academic style**: No decorative elements, clean background, proper margins.\n\n"
            "Output a JSON array with one object per figure:\n"
            '[{"figure": "filename.png", "status": "PASS"|"WARN"|"FAIL", "issues": [...], "fix": "..."}]\n'
            "Be specific and actionable in fixes."
        )

        user_prompt = (
            f"## Figures to audit ({len(images)} files)\n"
            f"{chr(10).join(file_list)}\n\n"
        )

        # 注入本地硬检查结果
        if local_issues:
            user_prompt += f"## 本地预检发现的问题\n{chr(10).join(local_issues)}\n\n"

        user_prompt += (
            f"## Figure generation code\n```\n{code_content}\n```\n\n"
            f"## Figure references in paper\n{fig_context}\n\n"
            "Please audit each figure and return the JSON assessment."
        )

        config = get_model_for_stage("figure-audit")

        response_text = ""

        # Try multimodal vision API (send actual images)
        image_paths = [str(img) for img in images if img.suffix.lower() == ".png"]
        if image_paths:
            yield f"data: [INFO] 使用多模态视觉 API 审查 {len(image_paths)} 张图表...\n\n"
            vision_text = (
                f"你是数学建模论文图表质量审查专家。请审查以下 {len(images)} 张图表。\n\n"
                f"## 图表列表\n{chr(10).join(file_list)}\n\n"
                f"## 生成代码\n```\n{code_content[:3000]}\n```\n\n"
                f"## 论文引用\n{fig_context[:2000]}\n\n"
                "请审查每张图表，输出 JSON 数组：\n"
                '[{"figure": "filename.png", "status": "PASS"|"WARN"|"FAIL", '
                '"issues": ["具体问题"], "fix": "修复建议"}]\n'
                "审查要点：字号>=10pt、有图例、有坐标轴标签、配色色盲友好、无空白图、分辨率足够。"
            )
            async for chunk in APIClientService.call_llm_vision(
                system="You are a figure quality auditor for academic papers.",
                text=vision_text,
                image_paths=image_paths,
                temperature=0.2,
            ):
                if chunk.startswith("data: ") and not chunk.startswith("data: ["):
                    response_text += chunk[6:].strip()
                yield chunk
        else:
            # Fallback to text-only audit
            async for chunk in APIClientService.call_llm_stream(
                provider=config["provider"],
                workspace_id=workspace_id,
                stage="figure-audit",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model_name=config["model"],
                temperature=0.2,
            ):
                if chunk.startswith("data: ") and not chunk.startswith("data: ["):
                    response_text += chunk[6:].strip()
                yield chunk

        # 解析 LLM 输出
        import re
        issues = []
        try:
            json_match = re.search(r"\[.*\]", response_text, re.DOTALL)
            if json_match:
                issues = json.loads(json_match.group())
        except (json.JSONDecodeError, Exception):
            pass

        # 如果解析失败，生成文本摘要
        if not issues:
            issues = [{"figure": "all", "status": "REVIEW", "issues": ["See LLM review above"], "fix": ""}]

        pass_count = sum(1 for i in issues if i.get("status") == "PASS")
        fail_count = sum(1 for i in issues if i.get("status") == "FAIL")

        summary = {
            "status": "success",
            "figures_scanned": len(images),
            "passed": pass_count,
            "warnings": sum(1 for i in issues if i.get("status") == "WARN"),
            "failed": fail_count,
            "details": issues,
            "overall": "PASS" if fail_count == 0 else "FAIL - fix issues before submission",
        }

        yield f"data: \n\n"
        yield f"data: [RESULT] {summary['overall']}\n\n"
        yield f"data: {json.dumps(summary, ensure_ascii=False)}\n\n"

    @staticmethod
    def audit_figures_sync(workspace_id: str) -> Dict:
        """同步版本：仅做文件级别的基础检查（不调用 LLM）。"""
        ws_path = settings.DATA_DIR / workspace_id
        figures_dir = ws_path / "output" / "figures"

        if not figures_dir.exists():
            return {"status": "error", "message": "Figures directory not found."}

        images = list(figures_dir.glob("*.png")) + list(figures_dir.glob("*.pdf"))
        if not images:
            return {"status": "warning", "message": "No figures found to audit."}

        issues = []
        for img_path in images:
            size_kb = img_path.stat().st_size / 1024
            if size_kb < 10:
                issues.append({
                    "figure": img_path.name,
                    "issue": f"File too small ({size_kb:.1f}KB) — likely placeholder or corrupted.",
                    "recommendation": "Regenerate this figure.",
                })
            elif size_kb > 10240:
                issues.append({
                    "figure": img_path.name,
                    "issue": f"File very large ({size_kb/1024:.1f}MB) — may cause PDF bloat.",
                    "recommendation": "Reduce DPI or compress the image.",
                })

        return {
            "status": "success",
            "figures_scanned": len(images),
            "issues_found": len(issues),
            "details": issues,
            "overall_assessment": "FAIL" if issues else "PASS (basic check only; use LLM audit for full review)",
        }
