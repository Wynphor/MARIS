"""
FigureService — 图表生成与审查

功能：
  - generate_figures: 调 AI 生成 matplotlib/seaborn 图表代码，沙箱执行
  - audit_figures: 审查已有图表的合规性（色板、字号、格式）

对应 skill: skills-mathmodel/sensitivity-analysis (图表部分)
"""
import json
import asyncio
from pathlib import Path
from typing import AsyncGenerator, Dict, List
from .api_client_service import APIClientService
from .python_runner import PythonRunner
from ..core.prompts import get_model_for_stage
from ..core.config import settings


class FigureService:

    @staticmethod
    async def generate_figures(
        workspace_id: str,
        figure_type: str = "auto",
    ) -> AsyncGenerator[str, None]:
        """
        根据求解结果自动生成图表代码并执行。

        figure_type: auto / sensitivity / comparison / distribution
        """
        ws_path = settings.DATA_DIR / workspace_id
        src_dir = ws_path / "src"
        fig_dir = ws_path / "output" / "figures"
        fig_dir.mkdir(parents=True, exist_ok=True)

        # 1. 读取求解结果
        yield f"data: [INFO] 分析 workspace 中的求解结果...\n\n"
        result_files = list(src_dir.glob("*.py"))
        data_file = ws_path / "c_data.json"

        data_preview = ""
        if data_file.exists():
            try:
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if data:
                    data_preview = json.dumps(data[:3], indent=2, ensure_ascii=False)
            except Exception:
                pass

        # 2. 构建图表生成 prompt
        system_prompt = (
            "你是 Python 数据可视化专家。根据数据和求解结果生成 matplotlib/seaborn 图表代码。\n\n"
            "## 规范\n"
            "- 使用 matplotlib + seaborn\n"
            "- 设置 MPLBACKEND=Agg（非交互式）\n"
            "- 色板使用 colorblind-safe（如 'viridis', 'cividis', 'Set2'）\n"
            "- 字号 >= 10pt（plt.rcParams.update({'font.size': 10})）\n"
            "- 图表保存到 output/figures/ 目录，DPI=300\n"
            "- 使用三线表风格的表格（如有）\n"
            "- 每个图表有清晰的标题、坐标轴标签、图例\n\n"
            "## 输出\n"
            "只输出可直接运行的 Python 代码，不要解释。\n"
            "代码必须包含 if __name__ == '__main__' 入口。\n"
            "保存图表时使用: plt.savefig('output/figures/xxx.png', dpi=300, bbox_inches='tight')"
        )

        user_prompt = (
            f"## 数据预览\n{data_preview[:2000]}\n\n"
            f"## 图表类型\n{figure_type}\n\n"
            f"## 可用脚本\n{', '.join(f.name for f in result_files)}\n\n"
            "请生成数据可视化 Python 代码。"
        )

        # 3. 调 AI 生成代码
        yield f"data: [INFO] 正在调用 AI 生成图表代码...\n\n"
        config = get_model_for_stage("code-gen")
        generated_code = ""

        async for chunk in APIClientService.call_llm_stream(
            provider=config["provider"],
            workspace_id=workspace_id,
            stage="figure-gen",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=config["model"],
            temperature=0.3,
        ):
            if chunk.startswith("data: ") and not chunk.startswith("data: ["):
                generated_code += chunk[6:]
            yield chunk

        # 4. 提取并保存 Python 代码
        if not generated_code or "import" not in generated_code:
            yield f"data: [ERROR] AI 未能生成有效的 Python 代码。\n\n"
            return

        # 提取代码块（```python ... ```）
        code = FigureService._extract_python_code(generated_code)
        if not code:
            yield f"data: [ERROR] AI 未生成有效的 Python 代码块。请重试。\n\n"
            return

        fig_script = src_dir / "generate_figures.py"
        fig_script.write_text(code, encoding="utf-8")
        yield f"data: [INFO] 图表代码已保存到 {fig_script}\n\n"

        # 5. 沙箱执行
        yield f"data: [INFO] 执行图表生成脚本...\n\n"
        async for chunk in PythonRunner.run_solver(workspace_id, "generate_figures.py", timeout=60):
            yield chunk

        # 6. 检查输出
        generated_figs = list(fig_dir.glob("*.png")) + list(fig_dir.glob("*.pdf"))
        if generated_figs:
            yield f"data: [SUCCESS] 生成了 {len(generated_figs)} 张图表:\n\n"
            for fig in generated_figs:
                yield f"data: [FIGURE] {fig.name} ({fig.stat().st_size / 1024:.1f} KB)\n\n"
        else:
            yield f"data: [WARNING] 未检测到输出图表。请检查脚本是否正确执行。\n\n"

        yield f"data: {json.dumps({'status': 'success', 'figures_generated': len(generated_figs)})}\n\n"

    @staticmethod
    def audit_figures(workspace_id: str) -> Dict:
        """
        审查已有图表的合规性。
        检查: 文件存在性、尺寸、命名规范。
        """
        ws_path = settings.DATA_DIR / workspace_id
        figures_dir = ws_path / "output" / "figures"

        if not figures_dir.exists():
            return {"status": "error", "message": "图表目录不存在。"}

        images = list(figures_dir.glob("*.png")) + list(figures_dir.glob("*.pdf"))
        if not images:
            return {"status": "warning", "message": "未找到图表文件。"}

        issues = []
        for img_path in images:
            file_name = img_path.name
            size_kb = img_path.stat().st_size / 1024

            # 检查文件大小
            if size_kb < 5:
                issues.append({
                    "figure": file_name,
                    "issue": f"文件过小 ({size_kb:.1f} KB)，可能是空白图。",
                    "severity": "WARNING",
                })
            elif size_kb > 5000:
                issues.append({
                    "figure": file_name,
                    "issue": f"文件过大 ({size_kb:.1f} KB)，建议降低 DPI。",
                    "severity": "INFO",
                })

            # 检查命名规范
            if " " in file_name:
                issues.append({
                    "figure": file_name,
                    "issue": "文件名含空格，建议用下划线。",
                    "severity": "INFO",
                })

        return {
            "status": "success",
            "figures_scanned": len(images),
            "issues_found": len(issues),
            "details": issues,
            "figures": [f.name for f in images],
            "overall_assessment": "PASS" if not issues else f"WARNING - {len(issues)} issue(s)",
        }

    @staticmethod
    def _extract_python_code(text: str) -> str:
        """从 AI 输出中提取 ```python ... ``` 代码块。"""
        import re
        pattern = r"```python\s*\n(.*?)```"
        matches = re.findall(pattern, text, re.DOTALL)
        if matches:
            return "\n\n".join(matches)
        return ""
