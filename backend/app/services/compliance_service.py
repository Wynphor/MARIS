"""
ComplianceService — 合规审查（身份脱敏 + 语义审计）

7.4 Claim Audit: LLM 驱动的数值声明交叉验证
7.1 Identity Leak: 正则扫描论文/代码中的个人信息泄露
"""
import re
import json
from pathlib import Path
from typing import Dict, AsyncGenerator

from .api_client_service import APIClientService
from ..core.prompts import read_workspace_file, get_model_for_stage
from ..core.config import settings


class ComplianceService:
    # Patterns that shouldn't appear in a double-blind submission
    FORBIDDEN_PATTERNS = [
        r"姓名[:：]\s*\w+",
        r"学校[:：]\s*\w+",
        r"学号[:：]\s*\d+",
        r"University",
        r"College",
        r"Team\s*ID[:：]?\s*\d+",
    ]

    @staticmethod
    def audit_workspace(workspace_id: str) -> Dict:
        """Scans code and paper for identity leaks."""
        ws_path = settings.DATA_DIR / workspace_id
        issues = []

        # Files to scan
        files_to_scan = []
        paper_dir = ws_path / "paper"
        src_dir = ws_path / "src"
        if paper_dir.exists():
            files_to_scan.extend(paper_dir.glob("*.tex"))
        if src_dir.exists():
            files_to_scan.extend(src_dir.glob("*.py"))

        for file_path in files_to_scan:
            try:
                content = file_path.read_text(encoding="utf-8")
                for pattern in ComplianceService.FORBIDDEN_PATTERNS:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        issues.append({
                            "file": file_path.name,
                            "type": "Identity Leak",
                            "matches": matches
                        })
            except Exception:
                continue

        return {
            "compliant": len(issues) == 0,
            "issues": issues,
            "recommendation": "Remove personal info before final submission." if issues else "Passed double-blind check."
        }

    @staticmethod
    def anonymize_file(file_path: Path):
        """Redacts sensitive patterns from a file."""
        if not file_path.exists():
            return
        content = file_path.read_text(encoding="utf-8")
        for pattern in ComplianceService.FORBIDDEN_PATTERNS:
            content = re.sub(pattern, "[REDACTED]", content, flags=re.IGNORECASE)
        file_path.write_text(content, encoding="utf-8")

    @staticmethod
    async def paper_claim_audit(workspace_id: str) -> AsyncGenerator[str, None]:
        """
        7.4 Semantic & Claim Audit — LLM 驱动的数值声明交叉验证。
        让 LLM 提取论文中所有数值声明，与实际数据/代码输出交叉比对，
        检测幻觉数据、不一致的单位、夸大的结论。
        """
        tex_content = read_workspace_file(workspace_id, "paper/main.tex")
        if not tex_content:
            yield "data: [ERROR] No paper/main.tex found. Run 'write' stage first.\n\n"
            return

        # 收集数据文件
        ws_path = settings.DATA_DIR / workspace_id
        data_snippets = []

        # 读取 JSON 数据文件
        for json_file in ws_path.rglob("*.json"):
            if json_file.stat().st_size < 500_000:  # 只读小于 500KB 的
                try:
                    content = json_file.read_text(encoding="utf-8", errors="replace")
                    data_snippets.append(f"### {json_file.name}\n{content[:2000]}")
                except Exception:
                    pass
            if len(data_snippets) >= 5:
                break

        # 读取预处理报告
        report = read_workspace_file(workspace_id, "preprocessing_report.md") or ""
        if report:
            data_snippets.append(f"### Preprocessing Report\n{report[:2000]}")

        data_context = "\n\n".join(data_snippets) if data_snippets else "(no data files found)"

        # ── Deterministic numeric cross-check ──
        deterministic_results = ComplianceService._deterministic_claim_check(
            tex_content, ws_path
        )
        det_section = ""
        if deterministic_results:
            det_section = (
                "\n\n## 预检：确定性数值交叉比对结果\n"
                "以下数值已从论文中提取并与结果文件自动比对：\n"
            )
            for dr in deterministic_results:
                det_section += (
                    f"- 论文声称: `{dr['claim']}` | "
                    f"结果文件值: `{dr['file_value']}` | "
                    f"差异: `{dr['diff']}` | "
                    f"状态: **{dr['status']}**\n"
                )
            det_section += (
                "\n请重点验证上述比对结果，特别关注 MISMATCH 和 NOT_FOUND 条目。\n"
            )

        # 读取代码中的输出结果
        code_output = ""
        output_dir = ws_path / "output"
        if output_dir.exists():
            for txt_file in output_dir.glob("*.txt"):
                try:
                    code_output += txt_file.read_text(encoding="utf-8", errors="replace")[:1000]
                except Exception:
                    pass

        system_prompt = (
            "You are a rigorous fact-checker for a math modeling competition paper.\n\n"
            "Your task:\n"
            "1. Extract ALL numerical claims from the paper (percentages, ratios, measurements, "
            "model accuracy, R-squared values, p-values, growth rates, etc.)\n"
            "2. Cross-reference each claim against the provided data files and code outputs\n"
            "3. Flag any claims that are:\n"
            "   - Not supported by the data (potential hallucination)\n"
            "   - Inconsistent with code output (rounding error, wrong formula)\n"
            "   - Exaggerated beyond what the data supports\n"
            "   - Missing units or ambiguous precision\n\n"
            "Output format:\n"
            "```json\n"
            '[{"claim": "text from paper", "location": "section/chapter", '
            '"status": "VERIFIED"|"UNVERIFIED"|"FALSIFIED", '
            '"evidence": "what data says", "severity": "LOW"|"MEDIUM"|"HIGH", '
            '"fix": "suggested correction"}]\n'
            "```\n"
            "Be thorough. Every number in the paper must have a source."
        )

        user_prompt = (
            f"## Paper Content (LaTeX)\n{tex_content[:8000]}\n\n"
            f"## Data Files\n{data_context[:4000]}\n\n"
            f"## Code Output\n{code_output[:2000]}\n"
            f"{det_section}\n"
            "Please extract and verify all numerical claims. "
            "Pay special attention to the deterministic pre-check results above."
        )

        config = get_model_for_stage("claim-audit")

        yield f"data: [INFO] Starting claim audit (workspace: {workspace_id})\n\n"

        response_text = ""
        async for chunk in APIClientService.call_llm_stream(
            provider=config["provider"],
            workspace_id=workspace_id,
            stage="claim-audit",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=config["model"],
            temperature=0.1,
        ):
            if chunk.startswith("data: ") and not chunk.startswith("data: ["):
                response_text += chunk[6:].strip()
            yield chunk

        # 解析结果
        claims = []
        try:
            json_match = re.search(r"\[.*\]", response_text, re.DOTALL)
            if json_match:
                claims = json.loads(json_match.group())
        except (json.JSONDecodeError, Exception):
            pass

        verified = sum(1 for c in claims if c.get("status") == "VERIFIED")
        falsified = sum(1 for c in claims if c.get("status") == "FALSIFIED")
        unverified = sum(1 for c in claims if c.get("status") == "UNVERIFIED")

        summary = {
            "status": "success",
            "claims_extracted": len(claims),
            "verified": verified,
            "unverified": unverified,
            "falsified": falsified,
            "details": claims,
            "recommendation": (
                f"Fix {falsified} falsified claims before submission."
                if falsified > 0
                else "All claims grounded in data."
            ),
        }

        yield f"data: \n\n"
        yield f"data: [RESULT] Verified: {verified}, Unverified: {unverified}, Falsified: {falsified}\n\n"
        yield f"data: {json.dumps(summary, ensure_ascii=False)}\n\n"

    @staticmethod
    def _deterministic_claim_check(tex_content: str, ws_path: Path) -> list:
        """
        确定性数值交叉比对：从 LaTeX 提取数字，与结果文件比对。
        返回 [{claim, file_value, diff, status}] 列表。
        """
        import csv
        import io

        # 1. Extract numbers from LaTeX with context
        # Match patterns like: 93.5%, R^2 = 0.87, p < 0.05, 准确率为 95.2%
        number_patterns = [
            # Percentage
            r'(\d+\.?\d*)\s*%',
            # R²/R-squared
            r'[Rr]²?\s*[=≈]\s*(\d+\.?\d*)',
            # p-value
            r'[pP]\s*[<>=≤≥]\s*(\d+\.?\d*(?:e[+-]?\d+)?)',
            # General "= number" pattern
            r'[=≈]\s*(\d+\.?\d*(?:e[+-]?\d+)?)',
            # Chinese percentage
            r'(?:为|达到|约|约为|是)\s*(\d+\.?\d*)\s*%',
        ]

        extracted_numbers = set()
        for pattern in number_patterns:
            for match in re.finditer(pattern, tex_content):
                try:
                    val = float(match.group(1))
                    extracted_numbers.add(val)
                except (ValueError, IndexError):
                    pass

        if not extracted_numbers:
            return []

        # 2. Build result file lookup table
        result_values = {}  # value -> source_file

        # Parse JSON result files
        for json_file in ws_path.rglob("*.json"):
            if json_file.stat().st_size > 500_000:
                continue
            try:
                content = json_file.read_text(encoding="utf-8", errors="replace")
                data = json.loads(content)
                ComplianceService._extract_numbers_from_data(
                    data, str(json_file.relative_to(ws_path)), result_values
                )
            except (json.JSONDecodeError, OSError):
                pass

        # Parse CSV files
        for csv_file in ws_path.rglob("*.csv"):
            if csv_file.stat().st_size > 500_000:
                continue
            try:
                content = csv_file.read_text(encoding="utf-8", errors="replace")
                reader = csv.DictReader(io.StringIO(content))
                for row in reader:
                    for k, v in row.items():
                        try:
                            num = float(v)
                            result_values[num] = f"{csv_file.relative_to(ws_path)}:{k}"
                        except (ValueError, TypeError):
                            pass
            except Exception:
                pass

        # Parse output text files for numbers
        output_dir = ws_path / "output"
        if output_dir.exists():
            for txt_file in output_dir.glob("*.txt"):
                try:
                    content = txt_file.read_text(encoding="utf-8", errors="replace")
                    for match in re.finditer(r'(\d+\.?\d+)', content):
                        try:
                            num = float(match.group(1))
                            result_values[num] = str(txt_file.relative_to(ws_path))
                        except ValueError:
                            pass
                except Exception:
                    pass

        if not result_values:
            return []

        # 3. Compare with tolerance
        results = []
        tolerance_pct = 0.02  # 2% relative tolerance

        result_keys = sorted(result_values.keys())
        for paper_num in sorted(extracted_numbers):
            # Find closest match in result files
            best_match = None
            best_diff = float('inf')

            for result_num in result_keys:
                if paper_num == 0 and result_num == 0:
                    diff = 0
                elif paper_num == 0:
                    diff = abs(result_num)
                else:
                    diff = abs(paper_num - result_num) / abs(paper_num)

                if diff < best_diff:
                    best_diff = diff
                    best_match = result_num

            if best_match is not None:
                claim_str = f"{paper_num}"
                file_val_str = f"{best_match} (from {result_values[best_match]})"

                if best_diff <= tolerance_pct:
                    status = "MATCH"
                elif best_diff <= 0.1:  # Within 10%
                    status = "CLOSE"
                else:
                    status = "MISMATCH"

                results.append({
                    "claim": claim_str,
                    "file_value": file_val_str,
                    "diff": f"{best_diff*100:.2f}%",
                    "status": status,
                })

        return results

    @staticmethod
    def _extract_numbers_from_data(data, source: str, result_values: dict, depth: int = 0):
        """Recursively extract numbers from nested JSON data."""
        if depth > 5:
            return
        if isinstance(data, (int, float)):
            result_values[float(data)] = source
        elif isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (int, float)):
                    result_values[float(v)] = f"{source}:{k}"
                elif isinstance(v, (dict, list)):
                    ComplianceService._extract_numbers_from_data(v, source, result_values, depth + 1)
        elif isinstance(data, list):
            for item in data:
                ComplianceService._extract_numbers_from_data(item, source, result_values, depth + 1)

    @staticmethod
    async def paper_citation_audit(workspace_id: str) -> AsyncGenerator[str, None]:
        """
        参考文献审计 — LLM 驱动的引用一致性验证。
        检查：引用是否在参考文献列表中、参考文献格式、引用完整性。
        """
        tex_content = read_workspace_file(workspace_id, "paper/main.tex")
        if not tex_content:
            yield "data: [ERROR] No paper/main.tex found.\n\n"
            return

        system_prompt = (
            "You are a citation/reference auditor for a math modeling competition paper.\n\n"
            "Check:\n"
            "1. Every \\cite{} command has a matching \\bibitem{} in the bibliography\n"
            "2. Every \\bibitem{} is cited at least once in the text\n"
            "3. Reference format is consistent (author, title, journal/year, etc.)\n"
            "4. No placeholder references like [?], [ref], [TBD]\n"
            "5. URLs are properly formatted with \\url{}\n\n"
            "Output JSON array:\n"
            '[{"type": "missing_bib"|"uncited_ref"|"bad_format"|"placeholder"|..., '
            '"reference": "cite_key or text", "location": "where found", '
            '"fix": "suggested correction"}]\n'
        )

        user_prompt = (
            f"## Paper Content (LaTeX)\n{tex_content[:10000]}\n\n"
            "Please audit all citations and references."
        )

        config = get_model_for_stage("citation-audit")

        yield f"data: [INFO] Starting citation audit (workspace: {workspace_id})\n\n"

        response_text = ""
        async for chunk in APIClientService.call_llm_stream(
            provider=config["provider"],
            workspace_id=workspace_id,
            stage="citation-audit",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=config["model"],
            temperature=0.1,
        ):
            if chunk.startswith("data: ") and not chunk.startswith("data: ["):
                response_text += chunk[6:].strip()
            yield chunk

        # Parse results
        issues = []
        try:
            json_match = re.search(r"\[.*\]", response_text, re.DOTALL)
            if json_match:
                issues = json.loads(json_match.group())
        except (json.JSONDecodeError, Exception):
            pass

        summary = {
            "status": "success",
            "issues_found": len(issues),
            "details": issues,
            "recommendation": (
                f"Fix {len(issues)} citation issues before submission."
                if issues
                else "All citations are consistent."
            ),
        }

        yield f"data: \n\n"
        yield f"data: [RESULT] Issues found: {len(issues)}\n\n"
        yield f"data: {json.dumps(summary, ensure_ascii=False)}\n\n"
