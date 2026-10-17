"""
PaperReferenceService — 获奖范文检索

在 docs/ 目录下按题型搜索获奖论文，提取结构骨架、术语表、图表规范。
对应 skill: skills-mathmodel/paper-reference/SKILL.md
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional


# 范文数据库根目录
PAPER_DB_TYPED = Path("docs/1.国赛：高教社杯全国大学生数学建模竞赛优秀论文【数学建模老哥】/数学建模典型题目优秀论文")
PAPER_DB_YEARLY = Path("docs/1.国赛：高教社杯全国大学生数学建模竞赛优秀论文【数学建模老哥】")

# 题型关键词映射
TYPE_KEYWORDS = {
    "优化类": ["优化", "规划", "调度", "分配", "路径", "最大", "最小", "最优"],
    "评价类": ["评价", "评估", "排名", "等级", "综合"],
    "预测类": ["预测", "预报", "趋势", "演变", "时间序列"],
    "机理分析类": ["机理", "传导", "物理", "化学", "过程"],
    "统计分析类": ["分析", "相关性", "因素", "影响", "聚类", "回归"],
    "图论网络类": ["网络", "图", "流", "连通", "最短路径"],
    "环境经济学": ["碳排放", "气候", "环境", "经济", "政策"],
    "交通流": ["交通", "拥堵", "车辆", "流"],
    "图像增强": ["指纹", "图像", "增强", "识别"],
}

# 高分术语库
HIGH_SCORE_TERMS = {
    "模型构建": [
        "本文建立了...模型",
        "基于...理论",
        "采用...方法",
        "引入...变量",
        "构建...指标体系",
    ],
    "求解": [
        "通过...求解器求得最优解",
        "迭代收敛于...",
        "最优解为...",
        "采用...算法进行求解",
    ],
    "分析": [
        "灵敏度分析表明...",
        "模型的鲁棒性通过...验证",
        "结果表明...",
        "对比分析显示...",
    ],
    "结论": [
        "综合考量...",
        "相较于...方案...",
        "本文提出的...具有...优势",
        "基于以上分析，建议...",
    ],
}


class PaperReferenceService:

    @staticmethod
    def search_papers(problem_type: str, keywords: str = "") -> Dict:
        """
        按题型搜索匹配的获奖论文。

        返回: 匹配论文列表 + 结构骨架 + 术语表 + 图表规范
        """
        matched_papers = []

        # 1. 从分类库搜索
        if PAPER_DB_TYPED.exists():
            for subdir in sorted(PAPER_DB_TYPED.iterdir()):
                if not subdir.is_dir():
                    continue
                dirname = subdir.name
                # 匹配题型
                if PaperReferenceService._matches_type(dirname, problem_type, keywords):
                    papers = PaperReferenceService._scan_directory(subdir)
                    matched_papers.extend(papers)

        # 2. 如果分类库没找到，从年度库搜索
        if not matched_papers and PAPER_DB_YEARLY.exists():
            for year_dir in sorted(PAPER_DB_YEARLY.iterdir()):
                if not year_dir.is_dir():
                    continue
                for subdir in year_dir.iterdir():
                    if not subdir.is_dir():
                        continue
                    if PaperReferenceService._matches_type(subdir.name, problem_type, keywords):
                        papers = PaperReferenceService._scan_directory(subdir)
                        matched_papers.extend(papers)

        # 3. 构建报告
        report = PaperReferenceService._build_report(matched_papers, problem_type)
        return report

    @staticmethod
    def search_by_year(year: str, question_id: str = "") -> Dict:
        """按年份和题号搜索论文。"""
        matched_papers = []
        if PAPER_DB_YEARLY.exists():
            for year_dir in PAPER_DB_YEARLY.iterdir():
                if year in year_dir.name:
                    for subdir in year_dir.iterdir():
                        if not subdir.is_dir():
                            continue
                        if question_id and question_id not in subdir.name:
                            continue
                        papers = PaperReferenceService._scan_directory(subdir)
                        matched_papers.extend(papers)

        return PaperReferenceService._build_report(matched_papers, f"{year}-{question_id}")

    @staticmethod
    def get_writing_guidelines(problem_type: str) -> Dict:
        """获取写作规范指南（基于题型）。"""
        guidelines = {
            "structure": [
                "1. 目录（第1页）",
                "2. 摘要 — 三段式（背景目标20% + 核心建模50% + 结果结论30%）",
                "3. 问题重述与分析",
                "4. 数据探索与预处理",
                "5. 模型假设（5-8条）",
                "6. 符号说明（三线表）",
                "7. 模型建立与求解（≥3种模型对比）",
                "8. 灵敏度分析（≥4维度）",
                "9. 模型评价与改进",
                "10. 参考文献（≥5条）",
                "11. 附录（≥8页完整代码）",
            ],
            "terminology": HIGH_SCORE_TERMS,
            "table_format": "三线表（\\toprule/\\midrule/\\bottomrule）",
            "figure_format": "DPI≥300, 字号≥10pt, colorblind-safe 色板",
            "abstract_formula": "背景目标(20%) + 核心建模(50%) + 结果结论(30%)，含≥3个具体数值",
        }

        # 根据题型添加特殊指南
        if problem_type == "优化类":
            guidelines["special_requirements"] = [
                "必须对比≥3种优化算法",
                "灵敏度分析必须覆盖关键约束参数",
                "收敛曲线图必须包含",
            ]
        elif problem_type == "评价类":
            guidelines["special_requirements"] = [
                "权重确定方法必须有依据（AHP/熵权法等）",
                "必须做一致性检验",
                "排名结果必须附对比分析",
            ]
        elif problem_type == "预测类":
            guidelines["special_requirements"] = [
                "必须有训练集/测试集划分",
                "预测误差指标（RMSE/MAPE/R²）必须齐全",
                "置信区间必须标注",
            ]

        return guidelines

    @staticmethod
    def _matches_type(dirname: str, problem_type: str, keywords: str) -> bool:
        """判断目录名是否匹配目标题型。"""
        dirname_lower = dirname.lower()
        # 直接匹配题型名
        if problem_type in dirname:
            return True
        # 关键词匹配
        type_kws = TYPE_KEYWORDS.get(problem_type, [])
        for kw in type_kws:
            if kw in dirname_lower:
                return True
        if keywords:
            for kw in keywords.split(","):
                if kw.strip() and kw.strip() in dirname_lower:
                    return True
        return False

    @staticmethod
    def _scan_directory(directory: Path) -> List[Dict]:
        """扫描目录中的论文文件。"""
        papers = []
        # 提取年份和题号
        dir_name = directory.name
        year_match = re.search(r"(\d{4})", dir_name)
        question_match = re.search(r"([A-Z]\d?)", dir_name)

        paper_info = {
            "directory": str(directory),
            "name": dir_name,
            "year": year_match.group(1) if year_match else "未知",
            "question": question_match.group(1) if question_match else "未知",
        }

        # 查找 .tex 和 .pdf 文件
        tex_files = list(directory.rglob("*.tex"))
        pdf_files = list(directory.rglob("*.pdf"))

        paper_info["tex_files"] = [str(f.relative_to(directory)) for f in tex_files[:5]]
        paper_info["pdf_files"] = [str(f.relative_to(directory)) for f in pdf_files[:5]]
        paper_info["has_tex"] = len(tex_files) > 0
        paper_info["has_pdf"] = len(pdf_files) > 0

        # 如果有 .tex 文件，尝试提取结构
        if tex_files:
            try:
                tex_content = tex_files[0].read_text(encoding="utf-8", errors="ignore")[:20000]
                paper_info["sections"] = PaperReferenceService._extract_sections(tex_content)
                paper_info["has_tables"] = "\\begin{tabular}" in tex_content or "\\toprule" in tex_content
                paper_info["has_figures"] = "\\includegraphics" in tex_content
                paper_info["reference_count"] = tex_content.count("\\bibitem") + tex_content.count("\\bibentry")
            except Exception:
                pass

        papers.append(paper_info)
        return papers

    @staticmethod
    def _extract_sections(tex_content: str) -> List[str]:
        """从 LaTeX 源码提取章节标题。"""
        sections = []
        patterns = [
            r"\\section\{(.+?)\}",
            r"\\subsection\{(.+?)\}",
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, tex_content):
                sections.append(match.group(1))
        return sections[:20]  # 最多 20 个

    @staticmethod
    def _build_report(papers: List[Dict], problem_type: str) -> Dict:
        """构建范文参考报告。"""
        report = {
            "status": "success",
            "problem_type": problem_type,
            "papers_found": len(papers),
            "papers": papers[:10],  # 最多返回 10 篇
            "high_score_terminology": HIGH_SCORE_TERMS,
            "structure_skeleton": [
                "1. 问题重述（1-2页，简洁）",
                "2. 模型假设（逐条列出 + 依据说明）",
                "3. 符号说明（三线表）",
                "4. 模型建立与求解（分问题展开）",
                "5. 灵敏度分析（参数扫描 ±20%）",
                "6. 模型评价与改进",
            ],
            "table_format": "三线表（\\toprule / \\midrule / \\bottomrule）",
            "figure_format": "tab10 / Set2 / colorblind-safe 色板",
        }

        if not papers:
            report["status"] = "warning"
            report["message"] = f"未找到匹配'{problem_type}'的范文。请检查 docs/ 目录。"

        return report
