"""
Paper Index Builder — 扫描 docs/ 下的获奖论文，构建可搜索索引。

索引 474 篇获奖论文 PDF + 31 章模型参考书，
按年份、题号、题型分类，生成 paper_index.json。

修复:
  - 索引到每个 PDF 级别（而非目录级）
  - 从文件名提取年份、题号、题型
  - 索引典型题目论文（已按类型分目录）
"""
import json
import re
from pathlib import Path
from typing import List, Dict


# 项目根目录（backend/ 的上级）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

TYPICAL_ROOT = _PROJECT_ROOT / "docs/1.国赛：高教社杯全国大学生数学建模竞赛优秀论文【数学建模老哥】/数学建模典型题目优秀论文"
YEARLY_ROOT = _PROJECT_ROOT / "docs/1.国赛：高教社杯全国大学生数学建模竞赛优秀论文【数学建模老哥】"

# 典型题目目录名 → 题型映射
_DIR_TYPE_MAP = {
    "优化": "优化类", "评价": "评价类", "预测": "预测类",
    "机理": "机理分析类", "统计": "统计分析类",
}

# 文件名关键词 → 题型推断
_NAME_TYPE_KEYWORDS = {
    "优化类": ["优化", "规划", "调度", "分配", "路径", "选址", "信贷", "出租车", "排班"],
    "评价类": ["评价", "评估", "排名", "等级", "影响力", "葡萄酒", "竞争力"],
    "预测类": ["预测", "人口", "增长", "趋势", "放电", "时间序列"],
    "机理分析类": ["机理", "服装", "道路", "交通", "设计", "传导", "仿真", "博弈"],
}

# 题号提取模式
_Q_PATTERN = re.compile(r"[A-E]\d{0,3}")
_YEAR_PATTERN = re.compile(r"(19|20)\d{2}")


def build_index() -> Dict:
    """扫描所有论文，构建 PDF 级索引。"""
    index = {
        "papers": [],
        "by_type": {},
        "by_year": {},
        "by_question": {},
        "stats": {},
    }

    total = 0

    # 1. 典型题目论文 (8 个子目录，38 篇 PDF)
    if TYPICAL_ROOT.exists():
        for cat_dir in sorted(TYPICAL_ROOT.iterdir()):
            if not cat_dir.is_dir():
                continue
            problem_type = _infer_type_from_dirname(cat_dir.name)

            # PDF 可能直接在分类目录下，也可能在子目录中
            pdfs = list(cat_dir.glob("*.pdf"))
            if pdfs:
                # 直接在分类目录下
                for pdf in sorted(pdfs):
                    paper = _make_paper_entry(
                        pdf, problem_type=problem_type, category="typical",
                        parent_name=cat_dir.name,
                    )
                    _add_to_index(index, paper)
                    total += 1
            else:
                # 在子目录中
                for paper_dir in sorted(cat_dir.iterdir()):
                    if not paper_dir.is_dir():
                        continue
                    sub_pdfs = list(paper_dir.glob("*.pdf"))
                    for pdf in sorted(sub_pdfs):
                        paper = _make_paper_entry(
                            pdf, problem_type=problem_type, category="typical",
                            parent_name=paper_dir.name,
                        )
                        _add_to_index(index, paper)
                        total += 1

    # 2. 年度论文 (按年份分目录，每个年份下有多个题号子目录)
    if YEARLY_ROOT.exists():
        for year_dir in sorted(YEARLY_ROOT.iterdir()):
            if not year_dir.is_dir():
                continue
            year = _extract_year(year_dir.name)
            if not year:
                continue

            # 年份目录下可能直接有 PDF，也可能有子目录
            pdfs_in_year = list(year_dir.glob("*.pdf"))
            if pdfs_in_year:
                # 直接包含 PDF 文件
                for pdf in sorted(pdfs_in_year):
                    paper = _make_paper_entry(
                        pdf, problem_type="其他", category="yearly",
                        year=year,
                    )
                    _add_to_index(index, paper)
                    total += 1
            else:
                # 包含子目录（题号子目录）
                for sub_dir in sorted(year_dir.iterdir()):
                    if not sub_dir.is_dir():
                        continue
                    # 跳过非题目目录
                    if sub_dir.name.startswith(".") or sub_dir.name.startswith("__"):
                        continue

                    # 子目录下可能直接有 PDF，也可能有更深层子目录
                    sub_pdfs = list(sub_dir.glob("*.pdf"))
                    if sub_pdfs:
                        q_id = _extract_question(sub_dir.name)
                        for pdf in sorted(sub_pdfs):
                            paper = _make_paper_entry(
                                pdf, problem_type="其他", category="yearly",
                                year=year, question=q_id,
                            )
                            _add_to_index(index, paper)
                            total += 1
                    else:
                        # 更深层：子目录/编号目录/PDF
                        for deep_dir in sorted(sub_dir.iterdir()):
                            if not deep_dir.is_dir():
                                continue
                            deep_pdfs = list(deep_dir.glob("*.pdf"))
                            for pdf in sorted(deep_pdfs):
                                paper = _make_paper_entry(
                                    pdf, problem_type="其他", category="yearly",
                                    year=year, question=_extract_question(sub_dir.name),
                                )
                                _add_to_index(index, paper)
                                total += 1

    # 3. 统计
    index["stats"] = {
        "total_papers": total,
        "by_type": {k: len(v) for k, v in index["by_type"].items()},
        "by_year": {k: len(v) for k, v in index["by_year"].items()},
        "by_question": {k: len(v) for k, v in index["by_question"].items()},
    }

    return index


def _make_paper_entry(pdf_path: Path, problem_type: str, category: str,
                       year: str = "", question: str = "",
                       parent_name: str = "") -> Dict:
    """从 PDF 路径构建论文条目。"""
    name = pdf_path.stem  # 文件名不含扩展名
    if not year:
        year = _extract_year(name)
    if not question:
        question = _extract_question(name)
    if problem_type == "其他":
        problem_type = _infer_type_from_name(name)

    size_kb = pdf_path.stat().st_size / 1024

    return {
        "name": name[:80],
        "path": str(pdf_path.relative_to(_PROJECT_ROOT)),
        "type": problem_type,
        "category": category,
        "year": year,
        "question": question,
        "size_kb": round(size_kb, 1),
    }


def _add_to_index(index: Dict, paper: Dict):
    """将论文添加到索引的各个分类中。"""
    index["papers"].append(paper)
    index["by_type"].setdefault(paper["type"], []).append(paper)
    if paper["year"]:
        index["by_year"].setdefault(paper["year"], []).append(paper)
    if paper["question"]:
        index["by_question"].setdefault(paper["question"], []).append(paper)


def _infer_type_from_dirname(dirname: str) -> str:
    """从目录名推断题型（去除不可见字符后匹配）。"""
    clean = re.sub(r'[‌‍‎‏﻿]', '', dirname)
    for keyword, ptype in _DIR_TYPE_MAP.items():
        if keyword in clean:
            return ptype
    return "其他"


def _infer_type_from_name(name: str) -> str:
    """从文件名推断题型。"""
    for ptype, keywords in _NAME_TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in name:
                return ptype
    return "其他"


def _extract_year(name: str) -> str:
    m = _YEAR_PATTERN.search(name)
    return m.group() if m else ""


def _extract_question(name: str) -> str:
    m = _Q_PATTERN.search(name)
    return m.group() if m else ""


# ── 公共 API ──

def save_index(output_path: str = None) -> Dict:
    """构建并保存索引。"""
    if output_path is None:
        output_path = str(_PROJECT_ROOT / "docs" / "paper_index.json")
    index = build_index()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    return index["stats"]


def load_index(index_path: str = None) -> Dict:
    """加载索引。"""
    if index_path is None:
        index_path = str(_PROJECT_ROOT / "docs" / "paper_index.json")
    p = Path(index_path)
    if not p.exists():
        return build_index()
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def search_by_type(problem_type: str, limit: int = 5) -> List[Dict]:
    """按题型搜索。"""
    index = load_index()
    papers = index.get("by_type", {}).get(problem_type, [])
    if not papers:
        for k, v in index.get("by_type", {}).items():
            if problem_type in k or k in problem_type:
                papers = v
                break
    return papers[:limit]


def search_by_year(year: str, question: str = "", limit: int = 10) -> List[Dict]:
    """按年份搜索。"""
    index = load_index()
    papers = index.get("by_year", {}).get(year, [])
    if question:
        papers = [p for p in papers if question in p.get("question", "")]
    return papers[:limit]


def get_model_recommendations(problem_type: str) -> Dict:
    """获取题型对应的常用模型和方法。"""
    from .model_knowledge_base import recommend_for_type
    return recommend_for_type(problem_type)


if __name__ == "__main__":
    stats = save_index()
    print(f"Paper index: {json.dumps(stats, ensure_ascii=False, indent=2)}")
