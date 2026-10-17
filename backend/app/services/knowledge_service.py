"""
KnowledgeService — 竞赛知识归档（真实 LLM 驱动）

赛后复盘：用 LLM 总结建模方法、创新点、教训，
写入 Research_Wiki 并建立知识图谱边。
"""
import json
from pathlib import Path
from typing import Dict, AsyncGenerator
from datetime import datetime

from .api_client_service import APIClientService
from ..core.prompts import read_workspace_file, get_model_for_stage
from ..core.config import settings


class KnowledgeService:
    WIKI_DIR = Path("docs") / "Research_Wiki"

    @staticmethod
    def _ensure_wiki_structure():
        KnowledgeService.WIKI_DIR.mkdir(parents=True, exist_ok=True)
        (KnowledgeService.WIKI_DIR / "graph").mkdir(exist_ok=True)
        edges_file = KnowledgeService.WIKI_DIR / "graph" / "edges.jsonl"
        if not edges_file.exists():
            edges_file.touch()

    @staticmethod
    def add_edge(from_node: str, to_node: str, edge_type: str, evidence: str = ""):
        """
        7.11 Relational Knowledge Graph (ARIS Research Wiki style)
        Edge types: extends, contradicts, supports, invalidates, inspired_by.
        """
        KnowledgeService._ensure_wiki_structure()
        edges_file = KnowledgeService.WIKI_DIR / "graph" / "edges.jsonl"

        edge_data = {
            "from": from_node,
            "to": to_node,
            "type": edge_type,
            "evidence": evidence,
            "timestamp": datetime.now().isoformat()
        }

        with open(edges_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(edge_data) + "\n")

    @staticmethod
    async def archive_learnings(workspace_id: str) -> AsyncGenerator[str, None]:
        """
        用 LLM 总结竞赛建模过程，生成结构化归档文档。
        读取论文、代码、审查报告，提炼方法、创新点、教训。
        """
        KnowledgeService._ensure_wiki_structure()

        # 收集 workspace 内容
        paper = read_workspace_file(workspace_id, "paper/main.tex") or ""
        decompose = read_workspace_file(workspace_id, "problem_decomposition.md") or ""
        model_rec = read_workspace_file(workspace_id, "model_recommendation.md") or ""
        review = read_workspace_file(workspace_id, "review_report.md") or ""

        # 读取代码文件列表
        ws_path = settings.DATA_DIR / workspace_id / "src"
        code_files = []
        if ws_path.exists():
            for py_file in ws_path.glob("*.py"):
                content = py_file.read_text(encoding="utf-8", errors="replace")
                code_files.append(f"### {py_file.name}\n```python\n{content[:2000]}\n```")

        code_summary = "\n\n".join(code_files[:5]) if code_files else "(no code generated)"

        system_prompt = (
            "You are a post-competition knowledge archiver for a math modeling team. "
            "Analyze the competition materials and produce a structured archive in Markdown.\n\n"
            "Your output MUST include these sections:\n"
            "## 1. Problem Summary\n"
            "## 2. Modeling Approach (method name, mathematical formulation, why chosen)\n"
            "## 3. Key Innovations\n"
            "## 4. Code Architecture\n"
            "## 5. Lessons Learned (what worked, what failed)\n"
            "## 6. Knowledge Graph Nodes (JSON array of {id, type, description} for future reference)\n"
            "## 7. Suggested Graph Edges (JSON array of {from, to, type, evidence})\n\n"
            "Be specific and actionable. Reference actual model names, equations, and code patterns."
        )

        user_prompt = (
            f"## Problem Decomposition\n{decompose[:3000]}\n\n"
            f"## Model Recommendation\n{model_rec[:3000]}\n\n"
            f"## Paper (excerpt)\n{paper[:4000]}\n\n"
            f"## Code\n{code_summary[:3000]}\n\n"
            f"## Review Feedback\n{review[:2000]}"
        )

        config = get_model_for_stage("knowledge-archive")

        yield f"data: [INFO] 开始知识归档 (workspace: {workspace_id})\n\n"

        archive_content = ""
        async for chunk in APIClientService.call_llm_stream(
            provider=config["provider"],
            workspace_id=workspace_id,
            stage="knowledge-archive",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=config["model"],
            temperature=0.4,
        ):
            if chunk.startswith("data: ") and not chunk.startswith("data: ["):
                archive_content += chunk[6:].strip()
            yield chunk

        # 保存归档文档
        node_id = f"workspace:{workspace_id}"
        date_str = datetime.now().strftime("%Y-%m-%d")
        archive_file = KnowledgeService.WIKI_DIR / f"Archive_{workspace_id}.md"

        header = (
            f"# Post-Competition Knowledge Archive\n"
            f"**Workspace:** {workspace_id}\n"
            f"**Node ID:** {node_id}\n"
            f"**Date:** {date_str}\n\n"
        )
        with open(archive_file, "w", encoding="utf-8") as f:
            f.write(header + archive_content)

        # 尝试从 LLM 输出中提取知识图谱边
        try:
            import re
            edges_match = re.search(
                r"Suggested Graph Edges.*?```json\s*(\[.*?\])\s*```",
                archive_content, re.DOTALL
            )
            if edges_match:
                edges = json.loads(edges_match.group(1))
                for edge in edges[:10]:  # 最多 10 条边
                    KnowledgeService.add_edge(
                        edge.get("from", node_id),
                        edge.get("to", "unknown"),
                        edge.get("type", "related"),
                        edge.get("evidence", ""),
                    )
                yield f"data: [GRAPH] Added {len(edges[:10])} knowledge graph edges.\n\n"
        except Exception:
            pass  # 图谱边提取失败不影响归档

        yield f"data: [SUCCESS] Knowledge archived to {archive_file}\n\n"
        yield f"data: {json.dumps({'status': 'success', 'node_id': node_id, 'archive_path': str(archive_file)}, ensure_ascii=False)}\n\n"

    @staticmethod
    def get_knowledge_summary(max_archives: int = 5, max_chars: int = 3000) -> str:
        """
        读取最近的知识归档摘要，用于注入 prompt。
        返回最近 N 个归档的精简内容。
        """
        wiki_dir = settings.DATA_DIR.parent / "docs" / "Research_Wiki"
        if not wiki_dir.exists():
            return ""

        archives = sorted(wiki_dir.glob("Archive_*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not archives:
            return ""

        summaries = []
        total_chars = 0
        for archive in archives[:max_archives]:
            try:
                content = archive.read_text(encoding="utf-8", errors="replace")
                # Extract key sections (skip headers, take first 500 chars)
                lines = content.split("\n")
                key_lines = []
                for line in lines:
                    if line.startswith("# ") or line.startswith("## "):
                        key_lines.append(line)
                    elif any(k in line.lower() for k in ("创新", "教训", "方法", "结果", "模型", "关键", "lesson", "insight", "result")):
                        key_lines.append(line)

                summary = "\n".join(key_lines[:15])
                if len(summary) > 500:
                    summary = summary[:500] + "..."

                if total_chars + len(summary) > max_chars:
                    break

                summaries.append(f"### {archive.stem}\n{summary}")
                total_chars += len(summary)
            except Exception:
                pass

        return "\n\n".join(summaries) if summaries else ""

    @staticmethod
    def get_knowledge_edges(max_edges: int = 20) -> list:
        """
        读取知识图谱边，返回最近的边列表。
        """
        edges_file = settings.DATA_DIR.parent / "docs" / "Research_Wiki" / "graph" / "edges.jsonl"
        if not edges_file.exists():
            return []

        edges = []
        try:
            for line in edges_file.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line:
                    try:
                        edges.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass

        return edges[-max_edges:]

    @staticmethod
    def query_knowledge(query: str) -> str:
        """
        根据查询关键词搜索归档知识。
        返回匹配的知识片段。
        """
        wiki_dir = settings.DATA_DIR.parent / "docs" / "Research_Wiki"
        if not wiki_dir.exists():
            return ""

        query_lower = query.lower()
        matches = []

        for archive in wiki_dir.glob("Archive_*.md"):
            try:
                content = archive.read_text(encoding="utf-8", errors="replace")
                content_lower = content.lower()
                # Check if query terms appear in the archive
                if any(term in content_lower for term in query_lower.split()):
                    # Extract matching paragraphs
                    paragraphs = content.split("\n\n")
                    for para in paragraphs:
                        if any(term in para.lower() for term in query_lower.split()):
                            if len(para) > 20 and len(para) < 500:
                                matches.append(f"[{archive.stem}] {para.strip()}")
                                if len(matches) >= 5:
                                    break
            except Exception:
                pass

        return "\n".join(matches[:5]) if matches else ""
