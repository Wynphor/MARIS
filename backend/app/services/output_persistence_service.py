"""
OutputPersistenceService — AI 输出自动落盘

每个 AI stage 完成后，自动将输出保存到 workspace 对应文件。
与 TaskService.wrap_sse_stream 配合，透明地捕获并保存 AI 输出。

Stage → 文件映射：
  decompose     → problem_decomposition.md
  model-select  → model_recommendation.md
  code-gen      → src/*.py（多个文件）
  write         → paper/main.tex
  format-check  → format_check_report.md
  claim-audit   → claim_audit_report.md
  citation-audit→ citation_audit_report.md
  review        → review_report.md
  preprocess    → processed/preprocessing_report.md

Manifest:
  manifest.json → 记录所有产物、完成时间、校验和
"""
import re
import json
import html
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
from ..core.config import settings


# Stage → 输出文件映射
STAGE_OUTPUT_MAP = {
    "decompose":       "problem_decomposition.md",
    "model-select":    "model_recommendation.md",
    "format-check":    "format_check_report.md",
    "claim-audit":     "claim_audit_report.md",
    "citation-audit":  "citation_audit_report.md",
    "review":          "review_report.md",
    "review-red-r1":   "review_red_team_r1.md",
    "review-red-r2":   "review_red_team_r2.md",
    "review-blue-r1":  "review_blue_team_r1.md",
    "review-blue-r2":  "review_blue_team_r2.md",
    "auto-fix":        None,  # 直接覆盖 main.tex，由 OrchestratorService 处理
    "fix-tex-errors":  None,
    "figure-gen":      None,  # 由 FigureService 直接写文件
    "paper-ref":       "paper_reference_report.md",
    "auto-improve":    "auto_improve_report.md",
    "validate":        "validation_report.md",
    "preprocess":      "preprocessing_report.md",
    "knowledge-archive": "knowledge_archive.md",
    "figure-audit":    "figure_audit_report.md",
    "audit":           "audit_report.md",
}


class OutputPersistenceService:

    @staticmethod
    def save_stage_output(
        workspace_id: str,
        stage: str,
        output_text: str,
    ) -> Optional[str]:
        """
        将 stage 的 AI 输出保存到 workspace 对应文件。

        返回保存的文件路径，如果该 stage 无需落盘则返回 None。
        """
        if not output_text or len(output_text.strip()) < 50:
            return None  # 输出太短，可能是错误信息

        ws_path = settings.DATA_DIR / workspace_id

        declared = OutputPersistenceService._save_declared_artifacts(ws_path, output_text)
        if declared:
            OutputPersistenceService.update_manifest(workspace_id, stage, declared)
            return declared

        # ── code-gen: 输出多个 .py 文件 ──
        if stage == "code-gen":
            result = OutputPersistenceService._save_code_files(ws_path, output_text)
            if result:
                OutputPersistenceService.update_manifest(workspace_id, stage, result)
            return result

        # ── write: 输出 LaTeX ──
        if stage == "write":
            result = OutputPersistenceService._save_latex(ws_path, output_text)
            if result:
                OutputPersistenceService.update_manifest(workspace_id, stage, result)
            return result

        # ── 通用 Markdown 报告 ──
        target_file = STAGE_OUTPUT_MAP.get(stage)
        if not target_file:
            return None

        file_path = ws_path / target_file
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 清理输出（去除 SSE 前缀、系统消息等）
        cleaned = OutputPersistenceService._clean_output(output_text)
        if cleaned:
            OutputPersistenceService._backup_if_exists(file_path)
            file_path.write_text(cleaned, encoding="utf-8")
            OutputPersistenceService.update_manifest(workspace_id, stage, str(file_path))
            return str(file_path)

        return None

    @staticmethod
    def _save_declared_artifacts(ws_path: Path, output_text: str) -> Optional[str]:
        """
        Save explicitly declared artifacts before falling back to heuristic extraction.

        Supported formats:
          1. JSON fenced block:
             ```json
             {"artifacts":[{"path":"src/solve_all.py","content":"..."}]}
             ```
          2. XML-ish blocks:
             <artifact path="paper/main.tex">...</artifact>
        """
        artifacts = []

        for json_block in re.findall(r"```json\s*\n(.*?)```", output_text, re.DOTALL):
            try:
                payload = json.loads(json_block)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and isinstance(payload.get("artifacts"), list):
                artifacts.extend(payload["artifacts"])

        for match in re.finditer(
            r"<artifact\s+path=[\"']([^\"']+)[\"']\s*>(.*?)</artifact>",
            output_text,
            re.DOTALL | re.IGNORECASE,
        ):
            artifacts.append({
                "path": match.group(1),
                "content": html.unescape(match.group(2).strip()),
            })

        saved = []
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            rel_path = str(artifact.get("path", "")).strip()
            content = artifact.get("content")
            if not rel_path or not isinstance(content, str):
                continue
            target = OutputPersistenceService._safe_artifact_path(ws_path, rel_path)
            if target is None:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            OutputPersistenceService._backup_if_exists(target)
            target.write_text(content, encoding="utf-8")
            saved.append(str(target))

        return saved[0] if saved else None

    @staticmethod
    def _safe_artifact_path(ws_path: Path, rel_path: str) -> Optional[Path]:
        """Validate artifact paths and keep writes inside the workspace."""
        rel_path = rel_path.replace("\\", "/").lstrip("/")
        if ".." in rel_path.split("/"):
            return None

        allowed_roots = {
            "src", "paper", "output", "processed", "raw", "docs",
            "problem_decomposition.md", "model_recommendation.md",
            "paper_reference_report.md", "format_check_report.md",
            "claim_audit_report.md", "citation_audit_report.md",
            "review_report.md", "auto_improve_report.md",
            "validation_report.md", "preprocessing_report.md",
            "knowledge_archive.md", "figure_audit_report.md", "audit_report.md",
        }
        first_part = rel_path.split("/", 1)[0]
        if first_part not in allowed_roots and rel_path not in allowed_roots:
            return None

        target = (ws_path / rel_path).resolve()
        ws_resolved = ws_path.resolve()
        if not str(target).startswith(str(ws_resolved)):
            return None

        if target.suffix.lower() not in {".py", ".tex", ".md", ".json", ".csv", ".txt"}:
            return None
        return target

    @staticmethod
    def _backup_if_exists(file_path: Path):
        """Keep one previous version for editor diff and manual recovery."""
        if file_path.exists() and file_path.is_file():
            backup = file_path.with_suffix(file_path.suffix + ".bak")
            shutil.copy2(file_path, backup)

    @staticmethod
    def _save_code_files(ws_path: Path, output_text: str) -> Optional[str]:
        """从 AI 输出中提取 Python 代码并保存到 src/。"""
        src_dir = ws_path / "src"
        src_dir.mkdir(parents=True, exist_ok=True)

        # 提取 ```python ... ``` 代码块
        code_blocks = re.findall(r"```python\s*\n(.*?)```", output_text, re.DOTALL)

        saved_files = []
        if code_blocks:
            for i, code in enumerate(code_blocks):
                code = code.strip()
                if not code or len(code) < 50:
                    continue

                # 尝试从 docstring 或注释中提取文件名
                filename = OutputPersistenceService._extract_filename(code)
                if not filename:
                    filename = f"solve_{i+1}.py" if i > 0 else "solve_all.py"

                file_path = src_dir / filename
                OutputPersistenceService._backup_if_exists(file_path)
                file_path.write_text(code, encoding="utf-8")
                saved_files.append(str(file_path))
        else:
            # 没有代码块，尝试将整个输出作为代码保存
            cleaned = output_text.strip()
            if "import" in cleaned or "def " in cleaned:
                file_path = src_dir / "solve_all.py"
                OutputPersistenceService._backup_if_exists(file_path)
                file_path.write_text(cleaned, encoding="utf-8")
                saved_files.append(str(file_path))

        return saved_files[0] if saved_files else None

    @staticmethod
    def _save_latex(ws_path: Path, output_text: str) -> Optional[str]:
        """从 AI 输出中提取 LaTeX 代码并保存到 paper/main.tex。"""
        paper_dir = ws_path / "paper"
        paper_dir.mkdir(parents=True, exist_ok=True)

        # 提取 ```latex ... ``` 或 ```tex ... ``` 代码块
        latex_match = re.search(
            r"```(?:latex|tex)\s*\n(.*?)```", output_text, re.DOTALL
        )
        if latex_match:
            latex_content = latex_match.group(1).strip()
        else:
            # 尝试提取 \documentclass 到 \end{document}
            doc_match = re.search(
                r"(\\documentclass.*?\\end\{document\})", output_text, re.DOTALL
            )
            if doc_match:
                latex_content = doc_match.group(1).strip()
            else:
                # 整个输出当作 LaTeX
                latex_content = output_text.strip()

        if "\\documentclass" in latex_content:
            tex_path = paper_dir / "main.tex"
            OutputPersistenceService._backup_if_exists(tex_path)
            tex_path.write_text(latex_content, encoding="utf-8")
            return str(tex_path)

        return None

    @staticmethod
    def _extract_filename(code: str) -> Optional[str]:
        """从代码注释或 docstring 中提取文件名。"""
        # 检查 # filename: xxx.py
        match = re.search(r"#\s*(?:filename|file)[:\s]+(\S+\.py)", code, re.IGNORECASE)
        if match:
            return match.group(1)
        # 检查 docstring 中的文件名
        match = re.search(r'"""[\s\S]*?(?:filename|file)[:\s]+(\S+\.py)', code, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _clean_output(text: str) -> str:
        """清理 AI 输出，去除 SSE 前缀和系统消息。"""
        lines = text.split("\n")
        cleaned = []
        # All known system/control prefixes
        _prefixes = (
            "[TASK]", "[STATS]", "[INFO]", "[DONE]", "[TASK_COMPLETE]",
            "[SAVED]", "[ERROR]", "[WARNING]", "[SUCCESS]", "[STEP",
            "[MISSING]", "[OUTLIER]", "[STD]", "[OUTPUT]", "[FIGURE]",
            "[RED TEAM]", "[BLUE TEAM]", "[ROUND", "[RESULT]",
            "[GRAPH]", "[SUMMARY]", "[STATUS]", "[COMPILE",
        )
        for line in lines:
            stripped = line.strip()
            if any(stripped.startswith(p) for p in _prefixes):
                continue
            cleaned.append(line)

        result = "\n".join(cleaned).strip()
        if len(result) < 50:
            return ""
        return result

    @staticmethod
    def get_output_path(workspace_id: str, stage: str) -> Optional[str]:
        """获取某个 stage 的输出文件路径（如果存在）。"""
        target_file = STAGE_OUTPUT_MAP.get(stage)
        if not target_file:
            return None
        file_path = settings.DATA_DIR / workspace_id / target_file
        if file_path.exists():
            return str(file_path)
        return None

    # ── Manifest 管理 ──

    @staticmethod
    def update_manifest(
        workspace_id: str,
        stage: str,
        file_path: str,
        *,
        input_files: list = None,
        source_urls: list = None,
        parameters: dict = None,
        run_time_seconds: float = None,
    ):
        """
        更新 workspace 的 manifest.json，记录 stage 产物和证据链。
        每次 save_stage_output 成功后自动调用。
        """
        ws_dir = settings.DATA_DIR / workspace_id
        manifest_path = ws_dir / "manifest.json"

        # Load existing manifest or create new
        manifest = {}
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except (json.JSONDecodeError, OSError):
                manifest = {}

        manifest.setdefault("workspace_id", workspace_id)
        manifest.setdefault("created_at", datetime.now().isoformat())
        manifest.setdefault("stages", {})

        # Record file info with evidence chain
        fpath = Path(file_path)
        file_info = {
            "path": str(fpath.relative_to(ws_dir)) if fpath.is_absolute() else file_path,
            "size_bytes": fpath.stat().st_size if fpath.exists() else 0,
            "completed_at": datetime.now().isoformat(),
        }

        # Compute checksum
        if fpath.exists() and fpath.is_file():
            try:
                content = fpath.read_bytes()
                file_info["md5"] = hashlib.md5(content).hexdigest()
            except OSError:
                pass

        # Evidence chain fields
        if input_files:
            file_info["input_files"] = input_files
        if source_urls:
            file_info["source_urls"] = source_urls
        if parameters:
            file_info["parameters"] = parameters
        if run_time_seconds is not None:
            file_info["run_time_seconds"] = round(run_time_seconds, 2)

        manifest["stages"][stage] = file_info
        manifest["updated_at"] = datetime.now().isoformat()

        # Count completed stages
        manifest["completed_count"] = len(manifest["stages"])

        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    @staticmethod
    def get_manifest(workspace_id: str) -> dict:
        """读取 workspace 的 manifest.json。"""
        manifest_path = settings.DATA_DIR / workspace_id / "manifest.json"
        if not manifest_path.exists():
            return {"workspace_id": workspace_id, "stages": {}, "completed_count": 0}
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"workspace_id": workspace_id, "stages": {}, "completed_count": 0}
