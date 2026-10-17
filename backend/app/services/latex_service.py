import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Tuple

from ..core.config import settings

DATA_DIR = settings.DATA_DIR


class LatexService:
    @staticmethod
    def wrap_tables_in_tex(content: str) -> Tuple[str, int]:
        pos = 0
        new_content = ""
        tables_wrapped = 0
        while True:
            idx = content.find(r"\begin{tabular}", pos)
            if idx == -1:
                idx = content.find(r"\begin{tabular*", pos)
            if idx == -1:
                new_content += content[pos:]
                break

            new_content += content[pos:idx]
            lookback = content[max(0, idx - 50) : idx]
            is_wrapped = r"\resizebox" in lookback

            is_starred = r"\begin{tabular*}" in content[idx : idx + 20]
            end_tag = r"\end{tabular*}" if is_starred else r"\end{tabular}"
            end_idx = content.find(end_tag, idx)

            if end_idx == -1:
                new_content += content[idx : idx + len(end_tag)]
                pos = idx + len(end_tag)
                continue

            tabular_block = content[idx : end_idx + len(end_tag)]
            if is_wrapped:
                new_content += tabular_block
            else:
                new_content += r"\resizebox{\textwidth}{!}{" + tabular_block + "}"
                tables_wrapped += 1

            pos = end_idx + len(end_tag)
        return new_content, tables_wrapped

    @staticmethod
    def check_placeholders(content: str) -> list:
        placeholders = ["此处省略", "推导略", "步骤略", "详见附录", "TODO", "placeholder"]
        found = [p for p in placeholders if p in content]
        return found

    @staticmethod
    def inject_appendix_code(workspace_id: str, tex_content: str) -> str:
        ws_path = DATA_DIR / workspace_id
        src_dir = ws_path / "src"

        py_files = list(src_dir.glob("solve_all.py"))
        if not py_files:
            py_files = list(src_dir.glob("*.py"))

        if not py_files:
            return tex_content

        with open(py_files[0], "r", encoding="utf-8") as f:
            code_content = f.read()

        pattern = r"(\\begin\{lstlisting\}(?:\[.*?\])?\n)(.*?)(\n\\end\{lstlisting\})"
        match = re.search(pattern, tex_content, re.DOTALL)
        if match:
            prefix = match.group(1)
            suffix = match.group(3)
            return (
                tex_content[: match.start()]
                + prefix
                + code_content.strip()
                + suffix
                + tex_content[match.end() :]
            )

        return tex_content

    @staticmethod
    def parse_latex_log(log_path: Path) -> list:
        errors = []
        if not log_path.exists():
            return errors

        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if line.startswith("!"):
                    error_msg = line[1:].strip()
                    context = lines[i + 1].strip() if i + 1 < len(lines) else ""
                    # Try to find line number
                    line_match = re.search(r"l\.(\d+)", context)
                    line_num = int(line_match.group(1)) if line_match else None
                    errors.append(
                        {"message": error_msg, "context": context, "line": line_num}
                    )
        return errors

    @staticmethod
    def auto_fix_compile(workspace_id: str, tex_filename: str = "main.tex") -> dict:
        """
        7.5 Auto-Fix for TeX
        Reads the .log file, extracts the error, and automatically applies a patch to main.tex.
        """
        # Validate tex_filename
        if ".." in tex_filename or "/" in tex_filename or "\\" in tex_filename:
            return {"status": "error", "message": "Invalid tex filename"}

        paper_dir = DATA_DIR / workspace_id / "paper"
        tex_path = paper_dir / tex_filename
        if not str(tex_path.resolve()).startswith(str(paper_dir.resolve())):
            return {"status": "error", "message": "Invalid tex filename"}
        ws_path = DATA_DIR / workspace_id
        paper_dir = ws_path / "paper"
        tex_path = paper_dir / tex_filename
        log_path = paper_dir / tex_filename.replace(".tex", ".log")

        if not log_path.exists() or not tex_path.exists():
            return {"status": "error", "message": "Missing .tex or .log file."}

        errors = LatexService.parse_latex_log(log_path)
        if not errors:
            return {"status": "success", "message": "No errors found to fix."}

        with open(tex_path, "r", encoding="utf-8") as f:
            content = f.read()

        fixes_applied = 0
        for err in errors:
            msg = err.get("message", "")
            ctx = err.get("context", "")
            
            # Common TeX Error 1: Missing $ inserted
            if "Missing $ inserted" in msg and ctx:
                # Naive fix: Wrap the offending context in $...$
                clean_ctx = ctx.split("l.")[0].strip() if "l." in ctx else ctx.strip()
                if clean_ctx and clean_ctx in content:
                    content = content.replace(clean_ctx, f"${clean_ctx}$", 1)
                    fixes_applied += 1
                    
            # Common TeX Error 2: Too many }'s
            elif "Too many }" in msg and ctx:
                clean_ctx = ctx.split("l.")[0].strip() if "l." in ctx else ctx.strip()
                if clean_ctx and "}" in clean_ctx:
                    fixed_ctx = clean_ctx.replace("}", "", 1)
                    if clean_ctx in content:
                        content = content.replace(clean_ctx, fixed_ctx, 1)
                        fixes_applied += 1

        if fixes_applied > 0:
            with open(tex_path, "w", encoding="utf-8") as f:
                f.write(content)
            # Recompile
            subprocess.run(
                ["xelatex", "-interaction=nonstopmode", tex_filename],
                cwd=paper_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=sys.platform.startswith("win"),
            )
            return {"status": "success", "fixes_applied": fixes_applied, "recompiled": True}

        return {"status": "failed", "message": "Could not automatically fix the errors.", "errors": errors}

    @staticmethod
    async def post_process_and_compile(
        workspace_id: str, tex_filename: str = "main.tex"
    ) -> dict:
        ws_path = DATA_DIR / workspace_id
        paper_dir = ws_path / "paper"

        # Validate tex_filename: must be a simple filename, no path traversal
        if ".." in tex_filename or "/" in tex_filename or "\\" in tex_filename:
            return {"status": "error", "message": "Invalid tex filename"}

        tex_path = paper_dir / tex_filename
        # Verify resolved path stays within paper_dir
        if not str(tex_path.resolve()).startswith(str(paper_dir.resolve())):
            return {"status": "error", "message": "Invalid tex filename"}

        if not tex_path.exists():
            return {"status": "error", "message": f"TeX file {tex_filename} not found"}

        with open(tex_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 1. Clean bibliography
        bib_start = content.find(r"\begin{thebibliography}")
        if bib_start != -1:
            bib_end = content.find(r"\end{thebibliography}", bib_start)
            if bib_end != -1:
                bib_segment = content[bib_start:bib_end]
                if r"\bottomrule" in bib_segment:
                    content = (
                        content[:bib_start]
                        + bib_segment.replace(r"\bottomrule", "")
                        + content[bib_end:]
                    )

        # 2. Wrap tables
        content, wrapped_count = LatexService.wrap_tables_in_tex(content)

        # 3. Inject code
        content = LatexService.inject_appendix_code(workspace_id, content)

        # 4. Final placeholder check
        bad_words = LatexService.check_placeholders(content)

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(content)

        # 5. Compile
        success = True
        for _ in range(2):
            res = subprocess.run(
                ["xelatex", "-interaction=nonstopmode", tex_filename],
                cwd=paper_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=sys.platform.startswith("win"),
            )
            if res.returncode != 0:
                success = False

        pdf_path = tex_path.with_suffix(".pdf")
        log_path = tex_path.with_suffix(".log")

        compilation_errors = []
        if not success or not pdf_path.exists():
            compilation_errors = LatexService.parse_latex_log(log_path)

        return {
            "status": "success" if pdf_path.exists() else "failed",
            "tables_wrapped": wrapped_count,
            "placeholders_found": bad_words,
            "pdf_generated": pdf_path.exists(),
            "errors": compilation_errors,
        }
