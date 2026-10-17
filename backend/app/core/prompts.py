"""
Prompt 模板系统 — 集中管理所有 Pipeline Stage 的 System/User Prompt

迁移自 src/mimo_client.py 的 SYSTEM_PROMPTS，并根据 skills-mathmodel/*.md 扩展为
完整的 prompt 构建函数。每个函数返回 (system_prompt, user_prompt) 元组。

设计原则:
  - 所有 prompt 纯字符串，不依赖外部 I/O（文件读取由调用方负责传入）
  - 模板化参数用 {变量} 占位，由 build_* 函数填充
  - paper-write-override 内容硬编码注入，确保 AI 无法绕过竞赛规范
"""
from pathlib import Path
from typing import Optional
from .config import settings


# ============================================================
# 1. 基础 System Prompts（迁移自 mimo_client.py）
# ============================================================

SYSTEM_PROMPTS = {
    "auto-review-loop": (
        "你是数学建模竞赛审稿人。按四维度打分（1-10），每项附理由："
        "1.假设合理性 2.建模创造性 3.结果正确性 4.表述清晰度。最后给150字总评。直接输出。"
    ),
    "paper-claim-audit": (
        "你是论文数据核验员。逐条检查数值声明与源数据是否匹配。"
        "输出格式：[PASS/FAIL] 声明 → 证据文件 → 实际值 → 是否一致。直接输出。"
    ),
    "contest-format": (
        "你是数学建模竞赛论文格式检查员。逐行检查LaTeX源码，以下为强制规则："
        "1.表格必须三线表(\\toprule/\\midrule/\\bottomrule)，禁止竖线(|)和\\hline"
        "2.参考文献标注必须用[1][2]格式(natbib numbers)"
        "3.正文和附录不得出现学校、姓名等身份信息"
        "4.目录\\tableofcontents在第1页"
        "5.摘要单独一页(\\begin{abstract}...\\end{abstract})"
        "6.正文≤20页(从第3页起算)"
        "7.页码\\setcounter{page}{1}放在摘要前"
        "8.封面用\\includepdf插入"
        "9.图表编号：图1/表1分别编号"
        "10.公式重要者右对齐编号"
        "逐条对照检查，只列违规项（附行号）。全部合规回复'格式合规，无问题'。直接输出。"
    ),
    "citation-audit": (
        "你是参考文献核验员。逐条验证文献真实性和引用正确性。"
        "输出：[OK/FAIL] 文献N → 结果。直接输出。"
    ),
    "result-to-claim": (
        "你是数据分析员。从数值结果提取论文声明。"
        "每条格式：[声明] xxx（支撑数据：yyy）。输出3-5条。直接输出。"
    ),
}


# ============================================================
# 2. Provider → 模型路由表（迁移自 mimo_client.py TASK_MODEL）
# ============================================================

TASK_MODEL_MAP = {
    # 轻量执行任务 → MiMo V2.5（成本低，额度充沛）
    "research-lit":         {"provider": "mimo",      "model": "mimo-v2.5"},
    "exa-search":           {"provider": "mimo",      "model": "mimo-v2.5"},
    "arxiv":                {"provider": "mimo",      "model": "mimo-v2.5"},
    "semantic-scholar":     {"provider": "mimo",      "model": "mimo-v2.5"},
    "comm-lit-review":      {"provider": "mimo",      "model": "mimo-v2.5"},
    "run-experiment":       {"provider": "mimo",      "model": "mimo-v2.5"},
    "analyze-results":      {"provider": "mimo",      "model": "mimo-v2.5"},
    "paper-reference":      {"provider": "mimo",      "model": "mimo-v2.5"},
    "contest-format":       {"provider": "mimo",      "model": "mimo-v2.5"},
    "citation-audit":       {"provider": "mimo",      "model": "mimo-v2.5"},
    "format-check":         {"provider": "mimo",      "model": "mimo-v2.5"},

    # 中等推理任务 → MiMo V2.5-Pro
    "novelty-check":        {"provider": "mimo",      "model": "mimo-v2.5-pro"},
    "result-to-claim":      {"provider": "mimo",      "model": "mimo-v2.5-pro"},

    # 图像/图表 → Gemini Flash
    "figure-spec":          {"provider": "gemini",    "model": "gemini-2.5-flash"},
    "mermaid-diagram":      {"provider": "gemini",    "model": "gemini-2.5-flash"},

    # 核心推理 & 审查 → DeepSeek（主力推理）/ Gemini Pro
    "decompose":            {"provider": "deepseek",  "model": "deepseek-chat"},
    "model-select":         {"provider": "deepseek",  "model": "deepseek-chat"},
    "code-gen":             {"provider": "deepseek",  "model": "deepseek-chat"},
    "write":                {"provider": "deepseek",  "model": "deepseek-chat"},
    "sensitivity":          {"provider": "deepseek",  "model": "deepseek-chat"},
    "paper-claim-audit":    {"provider": "gemini",    "model": "gemini-2.5-pro"},
    "auto-review-loop":     {"provider": "gemini",    "model": "gemini-2.5-pro"},
    "review":               {"provider": "deepseek",  "model": "deepseek-chat"},

    # 对抗审查
    "red-team":             {"provider": "deepseek",  "model": "deepseek-chat"},
    "blue-team":            {"provider": "mimo",      "model": "mimo-v2.5-pro"},

    # 补充 stage 映射
    "preprocess":           {"provider": "mimo",      "model": "mimo-v2.5"},
    "figure-gen":           {"provider": "mimo",      "model": "mimo-v2.5-pro"},
    "figure-audit":         {"provider": "mimo",      "model": "mimo-v2.5-pro"},
    "claim-audit":          {"provider": "deepseek",  "model": "deepseek-chat"},
    "auto-improve":         {"provider": "deepseek",  "model": "deepseek-chat"},
    "archive":              {"provider": "mimo",      "model": "mimo-v2.5-pro"},
    "knowledge-archive":    {"provider": "mimo",      "model": "mimo-v2.5-pro"},
    "chat":                 {"provider": "deepseek",  "model": "deepseek-chat"},
}


def get_model_for_stage(stage: str) -> dict:
    """根据 stage 名返回推荐的 provider 和 model。"""
    return TASK_MODEL_MAP.get(stage, {"provider": "deepseek", "model": "deepseek-chat"})


# ============================================================
# 3. Paper-Write Override（硬编码，确保 AI 无法绕过）
# ============================================================

PAPER_WRITE_OVERRIDE = r"""
# 竞赛论文强制章节顺序与规范（不可跳过）

## 强制章节顺序
1. 目录
2. 摘要 — 三段式（背景目标20% + 核心建模50% + 结果结论30%），含≥3个具体数值
3. 问题重述与分析 — 数据概览表（必含）
4. 数据探索与预处理 — 分布图+箱线图+相关热力图+缺失值报告
5. 模型假设（5-8条，各附合理性说明）
6. 符号说明（三线表）
7. 模型建立与求解 — ≥3种模型对比 + 公式推导 + 算法伪代码
8. 灵敏度分析 — ≥4维度扫描
9. 模型评价与改进（5优+5缺）
10. 参考文献 — ≥5条，[1][2]格式
11. 附录 — ≥8页（完整代码+中间结果+补充图表）

## 绝对禁令
- 严禁出现"此处省略"、"推导略"、"步骤略"、"TODO"、"placeholder"
- 严禁第一人称（用"本文"自称）
- 严禁公式/图表入摘要
- 所有表格必须三线表（\toprule/\midrule/\bottomrule）
- 正文和附录不得出现学校、姓名等身份信息

## 模型建立与求解关键规范
- 至少对比3种模型，对比指标≥4个（准确率、精确率、召回率、F1等）
- 三线表呈现，明确标注最优值
- 必须解释选择理由（综合可解释性、计算效率、鲁棒性）
- 必须包含"试错与探索链"：Baseline → 线性模型 → 高级模型 → 最终选择

## 自检（生成后逐条输出）
| # | 检查项 | 状态 | 证据 |
每条 PASS/FAIL，FAIL 项必须立即修复。
"""


# ============================================================
# 4. Pipeline Stage Prompt 构建函数
# ============================================================

def build_decompose_prompt(workspace_id: str, problem_text: str) -> tuple[str, str]:
    """
    Stage: decompose — 赛题拆解
    对应 skill: skills-mathmodel/problem-decompose
    注入实战拆解示例。
    """
    from ..services.few_shot_service import get_few_shot_for_prompt
    few_shot = get_few_shot_for_prompt("decompose")

    system = (
        "你是数学建模竞赛专家，擅长将复杂赛题拆解为可求解的子问题。\n\n"
        "## 工作流程\n"
        "1. 识别题目中明确的问题数量\n"
        "2. 提取每个问题的核心目标（最大化/最小化/评价/预测/模拟）\n"
        "3. 提取显式约束条件和引用的数据\n"
        "4. 判定子问题类型\n\n"
        "## 类型判定特征信号\n"
        "| 特征信号 | 判定类型 |\n"
        "|---------|----------|\n"
        "| 含'最大/最小/最优/分配/调度/路径' | 优化类 |\n"
        "| 含'评价/排名/综合评估/优劣/等级' | 评价类 |\n"
        "| 含'预测/预报/趋势/未来/演变' | 预测类 |\n"
        "| 含'机理/过程/物理/化学/生物/传导' | 机理分析类 |\n"
        "| 含'分析/相关性/因素/影响/显著性' | 统计分析类 |\n"
        "| 含'图/网络/流/连通/最短路径' | 图论网络类 |\n\n"
        "## 输出格式\n"
        "严格按 Markdown 结构输出，每个子问题必须包含：类型、约束条件、优化目标、已知数据。"
        f"{few_shot}"
    )
    user = (
        f"请拆解以下数学建模赛题（workspace: {workspace_id}）：\n\n"
        f"---\n{problem_text}\n---\n\n"
        "输出到 problem_decomposition.md，参照上方示例的格式和详细程度。"
    )
    return system, user


def build_model_select_prompt(workspace_id: str, decomposition_text: str) -> tuple[str, str]:
    """
    Stage: model-select — 模型推荐
    对应 skill: skills-mathmodel/model-select
    注入模型知识库（31章）和获奖论文参考。
    """
    # 从拆解结果推断题型
    problem_type = _infer_problem_type(decomposition_text)
    model_context = _get_model_context(problem_type)
    paper_context = _get_paper_context(problem_type)

    # 注入历史竞赛知识
    knowledge_context = _get_knowledge_context(decomposition_text)

    system = (
        "你是数学建模领域的资深专家，精通各类数学模型和求解算法。\n\n"
        "## 典型题目-模型映射（案例驱动）\n"
        "| 题型 | 常用模型 | 求解工具 |\n"
        "|------|---------|----------|\n"
        "| 优化类 | 线性规划、整数规划、多目标规划、动态规划 | PuLP, scipy.optimize |\n"
        "| 评价类 | AHP、TOPSIS、模糊综合评价、熵权法 | numpy |\n"
        "| 预测类 | ARIMA、灰色预测GM(1,1)、回归分析、BP神经网络 | statsmodels, sklearn |\n"
        "| 机理分析 | 微分方程、差分方程、热传导方程 | scipy.integrate, sympy |\n"
        "| 统计分析 | 聚类、PCA、回归、假设检验 | sklearn, scipy.stats |\n"
        "| 图论/网络 | 最短路径、最大流、最小生成树 | networkx |\n\n"
        f"{model_context}\n\n"
        f"{paper_context}\n\n"
        f"{knowledge_context}\n\n"
        "## 输出要求\n"
        "每个子问题必须：\n"
        "1. 列出≥3个候选模型的对比表（含优势、劣势、适用条件、推荐度★）\n"
        "2. 给出首选模型 + 模型假设 + 求解算法 + Python库\n"
        "3. 给出备选方案（首选不收敛时的回退）\n"
        "4. 说明为何选它而非其他（Occam原则：能用简单模型不用复杂模型）"
    )
    user = (
        f"根据以下赛题拆解结果（workspace: {workspace_id}），推荐数学模型：\n\n"
        f"---\n{decomposition_text}\n---\n\n"
        "输出到 model_recommendation.md。"
    )
    return system, user


def _infer_problem_type(text: str) -> str:
    """从文本推断题型。"""
    type_signals = {
        "优化类": ["优化", "规划", "调度", "分配", "路径", "最大", "最小", "最优"],
        "评价类": ["评价", "评估", "排名", "等级", "综合评估"],
        "预测类": ["预测", "预报", "趋势", "演变", "时间序列"],
        "机理分析类": ["机理", "传导", "物理", "微分方程", "仿真"],
        "统计分析类": ["分析", "相关性", "因素", "影响", "聚类", "回归"],
    }
    for ptype, keywords in type_signals.items():
        if any(kw in text for kw in keywords):
            return ptype
    return "优化类"


def _get_model_context(problem_type: str) -> str:
    """从模型知识库获取题型对应的推荐模型。"""
    try:
        from ..services.model_knowledge_base import recommend_for_type
        rec = recommend_for_type(problem_type)
        if not rec.get("models"):
            return ""
        lines = [f"## {problem_type} 推荐模型（知识库）"]
        for m in rec["models"][:5]:
            lines.append(f"- **{m['name']}** ({m.get('name_en', '')}): {', '.join(m.get('keywords', [])[:3])} | 库: {m.get('python_lib', 'N/A')}")
        combo = rec.get("combo", {})
        if combo.get("must_have"):
            lines.append(f"\n**必选**: {', '.join(combo['must_have'])}")
        if combo.get("recommended"):
            lines.append(f"**推荐**: {', '.join(combo['recommended'])}")
        return "\n".join(lines)
    except Exception:
        return ""


def _get_paper_context(problem_type: str) -> str:
    """从获奖论文索引获取同类型论文参考。"""
    try:
        from ..services.paper_index_builder import search_by_type, get_model_recommendations
        papers = search_by_type(problem_type, limit=3)
        if not papers:
            return ""
        lines = ["## 同类型获奖论文参考"]
        for p in papers:
            year = p.get("year", "?")
            name = p.get("name", "")[:40]
            sections = p.get("sections", [])
            sec_str = " → ".join(sections[:5]) if sections else ""
            lines.append(f"- [{year}] {name}")
            if sec_str:
                lines.append(f"  结构: {sec_str}")

        # 添加题型模型推荐
        model_rec = get_model_recommendations(problem_type)
        if model_rec.get("typical_methods"):
            lines.append(f"\n**获奖论文常用方法**: {', '.join(model_rec['typical_methods'])}")
        if model_rec.get("figure_types"):
            lines.append(f"**获奖论文常用图表**: {', '.join(model_rec['figure_types'])}")

        return "\n".join(lines)
    except Exception:
        return ""


def _get_knowledge_context(query_text: str) -> str:
    """从历史竞赛知识归档中检索相关内容。"""
    try:
        from ..services.knowledge_service import KnowledgeService
        summary = KnowledgeService.get_knowledge_summary(max_archives=3, max_chars=2000)
        if not summary:
            return ""

        context = "## 历史竞赛经验（知识归档）\n"
        context += "以下是从过往竞赛中归档的经验教训，请参考：\n\n"
        context += summary

        # Also add relevant knowledge edges
        edges = KnowledgeService.get_knowledge_edges(max_edges=10)
        if edges:
            context += "\n\n### 知识关联\n"
            for edge in edges:
                context += f"- {edge.get('from', '?')} → {edge.get('to', '?')} ({edge.get('type', 'related')})\n"

        return context
    except Exception:
        return ""


def build_code_gen_prompt(workspace_id: str, recommendation_text: str,
                          question_id: str, data_info: str = "") -> tuple[str, str]:
    """
    Stage: code-gen — 代码骨架生成
    对应 skill: skills-mathmodel/code-template
    注入真实竞赛解题代码作为 few-shot 示例。
    """
    from ..services.few_shot_service import get_few_shot_for_prompt
    few_shot = get_few_shot_for_prompt("code-gen")

    system = (
        "你是 Python 科学计算专家，擅长为数学建模生成可运行的求解脚本。\n\n"
        "## 模板库\n"
        "| 模型类型 | 核心库 |\n"
        "|---------|--------|\n"
        "| 线性/整数规划 | PuLP / scipy.optimize |\n"
        "| 非线性规划 | cvxpy |\n"
        "| 多目标优化 | Pyomo / pymoo (NSGA-II) |\n"
        "| 微分方程 | scipy.integrate |\n"
        "| 回归/聚类/分类 | sklearn |\n"
        "| 图论 | networkx |\n"
        "| 时间序列 | statsmodels |\n\n"
        "## 输出规范\n"
        "1. 文件头 docstring：题目编号、子问题、模型名称、求解方法\n"
        "2. 数据加载：相对路径 data/，含异常处理\n"
        "3. 关键超参数必须通过 argparse 定义为命令行参数\n"
        "4. 结果输出到 output/ 目录\n"
        "5. 含 if __name__ == '__main__' 入口\n"
        "6. 每个脚本可直接 python 运行\n"
        "7. 另外生成一个对比脚本：≥3种候选模型横向对比\n"
        "8. 优先使用 artifact 协议输出文件：\n"
        "<artifact path=\"src/solve_all.py\">\n完整 Python 代码\n</artifact>\n"
        "<artifact path=\"src/compare_models.py\">\n完整 Python 代码\n</artifact>\n"
        f"{few_shot}"
    )
    data_section = f"\n\n## 可用数据信息\n{data_info}" if data_info else ""
    user = (
        f"根据以下模型推荐（workspace: {workspace_id}，题号: {question_id}），"
        f"生成 Python 求解脚本到 data/{workspace_id}/src/ 目录：\n\n"
        f"---\n{recommendation_text}\n---{data_section}\n\n"
        "输出完整的 Python 代码，可直接运行。"
    )
    return system, user


def build_write_prompt(workspace_id: str, recommendation_text: str,
                       reference_text: str = "", competition_type: str = "国赛") -> tuple[str, str]:
    """
    Stage: write — 论文写作
    对应 skill: skills-mathmodel/paper-write (注入 paper-write-override)
    """
    # Competition-specific format rules
    format_rules = _get_competition_format(competition_type)

    # Inject paper structure references from real award-winning papers
    paper_structure = _get_paper_structure_reference(competition_type)

    # Inject real paper structure few-shot example
    from ..services.few_shot_service import get_few_shot_for_prompt
    write_example = get_few_shot_for_prompt("write")

    system = (
        "你是数学建模竞赛论文写作专家。严格按照竞赛规范撰写论文。\n\n"
        f"{PAPER_WRITE_OVERRIDE}\n\n"
        f"{format_rules}\n\n"
        f"{paper_structure}\n\n"
        f"{write_example}\n\n"
        "## 摘要黄金公式\n"
        "三段式结构：\n"
        "1. 背景目标（20%）：针对XX问题，建立XX模型，旨在XX\n"
        "2. 核心建模（50%）：模型名称 + 算法步骤 + 求解软件\n"
        "3. 结果结论（30%）：必须包含具体数值结果\n\n"
        "## 输出格式\n"
        "优先使用 artifact 协议输出完整 LaTeX 源码：\n"
        "<artifact path=\"paper/main.tex\">\n"
        "\\documentclass 到 \\end{document} 的完整源码\n"
        "</artifact>\n"
        "内容必须可直接 xelatex 编译。"
    )
    ref_section = f"\n\n## 获奖范文参考\n{reference_text}" if reference_text else ""
    user = (
        f"根据以下模型推荐报告（workspace: {workspace_id}），"
        f"撰写完整 LaTeX 论文到 data/{workspace_id}/paper/main.tex：\n\n"
        f"---\n{recommendation_text}\n---{ref_section}\n\n"
        "输出完整 LaTeX 源码。"
    )
    return system, user


def _get_competition_format(competition_type: str) -> str:
    """Get competition-specific LaTeX format rules from format profiles."""
    from .format_profiles import get_format_profile, format_profile_to_prompt
    profile = get_format_profile(competition_type)
    return format_profile_to_prompt(profile)


def build_review_prompt(workspace_id: str, content_text: str,
                        role: str = "red") -> tuple[str, str]:
    """
    Stage: review — 对抗性审查
    对应 skill: skills-mathmodel/auto-review-adaptation
    role: 'red' = 审稿人攻击, 'blue' = 作者防御
    """
    if role == "red":
        from ..services.few_shot_service import get_few_shot_for_prompt
        review_example = get_few_shot_for_prompt("review-red")

        system = (
            "你是严苛的数学建模竞赛审稿人（Red Team）。你的任务是找出论文中的所有问题。\n\n"
            "## 审查维度（按权重排序）\n"
            "1. **假设的合理性**（最高权重）：每条假设是否有依据？是否过强？\n"
            "2. **建模的创造性**：是否超出课本方法？是否有'试错与探索链'？\n"
            "3. **结果的正确性**：数值是否具体？是否有数据支撑？\n"
            "4. **文字表述与图表**：LaTeX格式、三线表、图表质量\n\n"
            "## 输出格式\n"
            "逐条列出问题，每条标注：\n"
            "- 严重度: P0(强制修改) / P1(建议修改) / P2(可选)\n"
            "- 位置: 章节名\n"
            "- 问题描述\n"
            "- 修改建议\n\n"
            "最后给出150字总评和1-10分评分。"
            f"{review_example}"
        )
    else:  # blue
        system = (
            "你是数学建模论文的作者（Blue Team）。审稿人指出了以下问题，"
            "你需要逐条回应：接受并修改、反驳并给出理由、或部分接受。\n\n"
            "## 回应格式\n"
            "对每条攻击：\n"
            "- [接受/反驳/妥协] 原因说明\n"
            "- 如果接受：给出具体修改方案（LaTeX 代码片段）\n"
            "- 如果反驳：给出学术论据\n\n"
            "## 修改原则\n"
            "- 保持论文整体结构不变\n"
            "- 只修改有问题的部分\n"
            "- 修改后的 LaTeX 代码可直接替换原文"
        )
    user = (
        f"以下是需要审查的论文内容（workspace: {workspace_id}）：\n\n"
        f"---\n{content_text}\n---"
    )
    return system, user


def build_format_check_prompt(workspace_id: str, tex_content: str) -> tuple[str, str]:
    """
    Stage: format-check — 竞赛格式检查
    对应 skill: skills-mathmodel/contest-format
    """
    system = SYSTEM_PROMPTS["contest-format"]
    user = (
        f"请检查以下 LaTeX 论文的竞赛格式合规性（workspace: {workspace_id}）：\n\n"
        f"---\n{tex_content[:8000]}\n---\n\n"
        "逐项检查并输出格式检查报告。"
    )
    return system, user


def build_claim_audit_prompt(workspace_id: str, tex_content: str,
                             data_summary: str) -> tuple[str, str]:
    """
    Stage: paper-claim-audit — 论文声明审计
    对应 skill: skills-mathmodel/auto-review-adaptation 中的 paper-claim-audit
    """
    system = SYSTEM_PROMPTS["paper-claim-audit"]
    user = (
        f"请核验以下论文中的数值声明（workspace: {workspace_id}）：\n\n"
        f"## 论文内容\n{tex_content[:6000]}\n\n"
        f"## 实际数据/结果\n{data_summary[:4000]}\n\n"
        "逐条检查声明是否有数据支撑。"
    )
    return system, user


def build_citation_audit_prompt(workspace_id: str, tex_content: str) -> tuple[str, str]:
    """
    Stage: citation-audit — 参考文献审计
    """
    system = SYSTEM_PROMPTS["citation-audit"]
    user = (
        f"请验证以下论文中的参考文献（workspace: {workspace_id}）：\n\n"
        f"---\n{tex_content[:8000]}\n---\n\n"
        "逐条验证文献真实性和引用正确性。"
    )
    return system, user


def build_triage_prompt(problems_info: list[dict], team_skills: list[str]) -> tuple[str, str]:
    """
    Stage: triage — 多赛题初筛与决策（7.1）
    """
    system = (
        "你是数学建模竞赛选题顾问。分析多道赛题的数据需求、所需技能、难度，"
        "并结合团队技能给出选题建议。\n\n"
        "## 输出格式\n"
        "结构化 JSON 决策矩阵，包含：\n"
        "- 每道题的数据需求、所需技能、难度评级、与团队匹配度\n"
        "- 最终推荐题目及理由"
    )
    problems_desc = "\n".join(
        f"- {p.get('id', '?')}: {p.get('title', '未知')} (类型: {p.get('type', '未知')})"
        for p in problems_info
    )
    skills_desc = ", ".join(team_skills) if team_skills else "未指定"
    user = (
        f"## 候选赛题\n{problems_desc}\n\n"
        f"## 团队技能\n{skills_desc}\n\n"
        "请给出选题决策矩阵和推荐。"
    )
    return system, user


# ============================================================
# 5. 辅助函数
# ============================================================

def get_system_prompt(task: str) -> str:
    """获取指定任务的 system prompt（用于兼容 mimo_client 的 SYSTEM_PROMPTS 接口）。"""
    return SYSTEM_PROMPTS.get(task, "")


def _get_paper_structure_reference(competition_type: str) -> str:
    """从获奖论文索引中提取论文结构参考。"""
    try:
        from ..services.paper_index_builder import search_by_type
        # 根据竞赛类型搜索参考论文
        type_map = {"国赛": "优化类", "CUMCM": "优化类", "美赛": "评价类", "MCM": "评价类"}
        search_type = type_map.get(competition_type, "优化类")
        papers = search_by_type(search_type, limit=3)

        if not papers:
            return ""

        lines = ["## 获奖论文结构参考（来自真实获奖论文）"]
        for p in papers:
            sections = p.get("sections", [])
            if sections:
                lines.append(f"\n### [{p.get('year', '?')}] {p.get('name', '')[:40]}")
                for i, sec in enumerate(sections[:8], 1):
                    lines.append(f"  {i}. {sec}")
        return "\n".join(lines)
    except Exception:
        return ""


def read_workspace_file(workspace_id: str, relative_path: str) -> Optional[str]:
    """读取 workspace 目录下的文件内容（含路径遍历防护）。"""
    # Reject path traversal
    if ".." in relative_path:
        return None
    ws_dir = settings.DATA_DIR.resolve() / workspace_id
    file_path = (ws_dir / relative_path).resolve()
    if not str(file_path).startswith(str(ws_dir)):
        return None
    if not file_path.exists():
        return None
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception:
        return None
