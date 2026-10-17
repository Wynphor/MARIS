"""
Contest Format Profiles — LaTeX 格式规则配置化

每个竞赛类型定义：
  - 页面结构
  - 章节顺序
  - 参考文献格式
  - 附录要求
  - LaTeX preamble 模板
  - 禁止事项
"""

FORMAT_PROFILES = {
    "国赛": {
        "name": "全国大学生数学建模竞赛 (CUMCM)",
        "language": "zh",
        "max_pages": 20,
        "page_structure": [
            "第1页：论文标题、摘要、关键词（单独一页）",
            "第2页起：正文",
            "最后：参考文献",
            "附录：代码和数据",
        ],
        "section_order": [
            "一、问题重述",
            "二、问题分析",
            "三、模型假设",
            "四、符号说明",
            "五、模型建立与求解",
            "六、模型检验（灵敏度分析）",
            "七、模型评价与改进",
            "八、参考文献",
            "附录",
        ],
        "reference_format": "GB/T 7714",
        "reference_examples": [
            "[1] 作者. 书名[M]. 出版地: 出版社, 年份.",
            "[2] 作者. 论文名[J]. 期刊名, 年份, 卷(期): 起止页码.",
        ],
        "latex_preamble": (
            "\\documentclass[12pt,a4paper]{article}\n"
            "\\usepackage{cumcmthesis}\n"
            "\\usepackage[utf8]{inputenc}\n"
            "\\usepackage{amsmath,amssymb}\n"
            "\\usepackage{graphicx}\n"
            "\\usepackage{booktabs}\n"
            "\\usepackage{listings}\n"
            "\\usepackage{xcolor}\n"
            "\\usepackage[fontset=windows]{ctex}\n"
        ),
        "code_format": (
            "代码使用 listings 宏包，等宽字体，带行号：\n"
            "\\lstset{language=Python, basicstyle=\\ttfamily\\small, "
            "numbers=left, frame=single, breaklines=true}"
        ),
        "forbidden": [
            "不得出现学校名、学生姓名、指导教师姓名等身份信息",
            "不得在正文中出现大段代码（代码放附录）",
            "不得使用英文摘要（除非美赛）",
        ],
        "abstract_rules": [
            "摘要必须单独一页",
            "摘要包含：问题概述、方法、结果、关键词（3-5个）",
            "关键词用分号分隔",
        ],
        "notes": "国赛强调模型创新性和实用性，格式必须严格遵守。",
    },
    "MCM_ICM": {
        "name": "Mathematical Contest in Modeling (MCM/ICM)",
        "language": "en",
        "max_pages": 25,
        "page_structure": [
            "Page 1: Summary Sheet (team control number only)",
            "Page 2+: Main paper",
            "References at end",
            "Appendix: code and data",
        ],
        "section_order": [
            "1. Summary",
            "2. Introduction / Problem Restatement",
            "3. Assumptions",
            "4. Model Development",
            "5. Results and Analysis",
            "6. Sensitivity Analysis",
            "7. Strengths and Weaknesses",
            "8. Conclusion",
            "References",
            "Appendix",
        ],
        "reference_format": "APA or Chicago",
        "reference_examples": [
            "[1] Author, A. (Year). Title. Journal, volume(issue), pages.",
        ],
        "latex_preamble": (
            "\\documentclass[12pt]{article}\n"
            "\\usepackage[margin=1in]{geometry}\n"
            "\\usepackage{amsmath,amssymb}\n"
            "\\usepackage{graphicx}\n"
            "\\usepackage{booktabs}\n"
            "\\usepackage{natbib}\n"
            "\\usepackage{hyperref}\n"
        ),
        "code_format": "Use monospace font, include in Appendix.",
        "forbidden": [
            "Do not include team member names or school name in the paper",
            "Only team control number on the summary sheet",
            "No AI tool acknowledgments",
        ],
        "abstract_rules": [
            "Summary sheet is separate from the main paper",
            "Include: problem, method, results, key findings",
        ],
        "notes": "MCM/ICM emphasizes clear communication and creative modeling.",
    },
    "省赛": {
        "name": "省级数学建模竞赛",
        "language": "zh",
        "max_pages": 20,
        "page_structure": [
            "第1页：摘要、关键词",
            "第2页起：正文",
            "参考文献",
            "附录",
        ],
        "section_order": [
            "一、问题重述与分析",
            "二、模型假设与符号说明",
            "三、模型建立",
            "四、模型求解",
            "五、结果分析",
            "六、模型评价与改进",
            "七、参考文献",
            "附录",
        ],
        "reference_format": "GB/T 7714",
        "reference_examples": [
            "[1] 作者. 书名[M]. 出版地: 出版社, 年份.",
        ],
        "latex_preamble": (
            "\\documentclass[12pt,a4paper]{article}\n"
            "\\usepackage[utf8]{inputenc}\n"
            "\\usepackage{amsmath,amssymb}\n"
            "\\usepackage{graphicx}\n"
            "\\usepackage{booktabs}\n"
            "\\usepackage[fontset=windows]{ctex}\n"
        ),
        "code_format": "代码放附录，等宽字体，带注释。",
        "forbidden": [
            "不得出现身份信息",
        ],
        "abstract_rules": [
            "摘要包含方法和主要结果",
        ],
        "notes": "省赛规则参照国赛，略有简化。",
    },
    "研赛": {
        "name": "研究生数学建模竞赛",
        "language": "zh",
        "max_pages": 30,
        "page_structure": [
            "封面页",
            "摘要",
            "正文",
            "参考文献",
            "附录",
        ],
        "section_order": [
            "一、问题背景与重述",
            "二、问题分析",
            "三、模型假设",
            "四、符号约定",
            "五、模型建立与求解",
            "六、模型验证与灵敏度分析",
            "七、模型评价与推广",
            "八、参考文献",
            "附录",
        ],
        "reference_format": "GB/T 7714",
        "latex_preamble": (
            "\\documentclass[12pt,a4paper]{article}\n"
            "\\usepackage[utf8]{inputenc}\n"
            "\\usepackage{amsmath,amssymb,amsfonts}\n"
            "\\usepackage{graphicx}\n"
            "\\usepackage{booktabs}\n"
            "\\usepackage{algorithm}\n"
            "\\usepackage{algorithmic}\n"
            "\\usepackage[fontset=windows]{ctex}\n"
        ),
        "code_format": "代码放附录，推荐使用 algorithm 宏包描述算法。",
        "forbidden": [
            "不得出现身份信息",
            "论文应体现较强的数学功底",
        ],
        "abstract_rules": [
            "摘要突出创新点和方法论贡献",
        ],
        "notes": "研赛要求更高的数学深度和创新性。",
    },
    "generic": {
        "name": "通用竞赛",
        "language": "zh",
        "max_pages": 20,
        "page_structure": ["摘要", "正文", "参考文献", "附录"],
        "section_order": [
            "一、问题重述",
            "二、模型建立",
            "三、模型求解",
            "四、结果分析",
            "五、参考文献",
            "附录",
        ],
        "reference_format": "统一格式",
        "latex_preamble": "\\documentclass[12pt,a4paper]{article}\n\\usepackage{amsmath}\n",
        "code_format": "代码放附录。",
        "forbidden": [],
        "abstract_rules": ["摘要单独一页"],
        "notes": "请根据实际竞赛调整格式。",
    },
}


def get_format_profile(competition_type: str) -> dict:
    """获取竞赛格式配置，支持模糊匹配。"""
    # Direct match
    if competition_type in FORMAT_PROFILES:
        return FORMAT_PROFILES[competition_type]

    # Fuzzy match
    ct_lower = competition_type.lower()
    for key, profile in FORMAT_PROFILES.items():
        if key in ct_lower or ct_lower in key:
            return profile

    # Match by keywords
    if any(k in ct_lower for k in ("cumcm", "国赛", "全国")):
        return FORMAT_PROFILES["国赛"]
    if any(k in ct_lower for k in ("mcm", "icm", "美赛")):
        return FORMAT_PROFILES["MCM_ICM"]
    if any(k in ct_lower for k in ("省赛", "省级")):
        return FORMAT_PROFILES["省赛"]
    if any(k in ct_lower for k in ("研赛", "研究生")):
        return FORMAT_PROFILES["研赛"]

    return FORMAT_PROFILES["generic"]


def format_profile_to_prompt(profile: dict) -> str:
    """将格式配置转换为 prompt 字符串。"""
    lines = [f"# {profile['name']} 格式要求\n"]

    lines.append("## 页面结构")
    for item in profile["page_structure"]:
        lines.append(f"- {item}")

    lines.append("\n## 章节顺序")
    for item in profile["section_order"]:
        lines.append(f"- {item}")

    lines.append(f"\n## 参考文献格式: {profile['reference_format']}")
    for ex in profile.get("reference_examples", []):
        lines.append(f"  {ex}")

    lines.append(f"\n## LaTeX Preamble\n```latex\n{profile['latex_preamble']}\n```")

    if profile.get("code_format"):
        lines.append(f"\n## 代码格式\n{profile['code_format']}")

    if profile.get("forbidden"):
        lines.append("\n## 禁止事项")
        for item in profile["forbidden"]:
            lines.append(f"- ❌ {item}")

    if profile.get("abstract_rules"):
        lines.append("\n## 摘要要求")
        for item in profile["abstract_rules"]:
            lines.append(f"- {item}")

    if profile.get("notes"):
        lines.append(f"\n> {profile['notes']}")

    return "\n".join(lines)


def check_latex_compliance(tex_content: str, competition_type: str) -> dict:
    """
    正则检查 LaTeX 是否符合竞赛格式规范。
    返回 {passed: bool, issues: [{level, rule, detail}]}
    """
    import re

    profile = get_format_profile(competition_type)
    issues = []

    # 1. 必需结构检查
    if "\\documentclass" not in tex_content:
        issues.append({"level": "ERROR", "rule": "缺少 \\documentclass", "detail": "LaTeX 文件必须以 \\documentclass 开头"})
    if "\\begin{document}" not in tex_content:
        issues.append({"level": "ERROR", "rule": "缺少 \\begin{document}", "detail": "文档必须有 begin/end document"})
    if "\\end{document}" not in tex_content:
        issues.append({"level": "ERROR", "rule": "缺少 \\end{document}", "detail": "文档必须正确关闭"})

    # 2. 摘要检查
    if "abstract" not in tex_content.lower() and "\\begin{abstract}" not in tex_content:
        issues.append({"level": "WARN", "rule": "缺少摘要", "detail": "论文应包含 abstract 环境"})

    # 3. 参考文献检查
    if "\\bibliography" not in tex_content and "\\begin{thebibliography}" not in tex_content and "\\begin{references}" not in tex_content:
        issues.append({"level": "WARN", "rule": "缺少参考文献", "detail": "论文应包含参考文献部分"})

    # 4. 身份信息检查（国赛/省赛）
    if competition_type in ("国赛", "省赛"):
        identity_patterns = [
            (r'[我咱]校', "出现'我校'"),
            (r'[我咱]院', "出现'我院'"),
            (r'[我咱]们?学', "出现'我们学'"),
            (r'指导教师', "出现'指导教师'"),
            (r'指导老师', "出现'指导老师'"),
        ]
        for pattern, desc in identity_patterns:
            if re.search(pattern, tex_content):
                issues.append({"level": "ERROR", "rule": "身份信息泄露", "detail": f"检测到: {desc}"})

    # 5. 代码格式检查（应使用 listings 或 verbatim）
    code_blocks = re.findall(r'\\begin\{(lstlisting|verbatim|minted)\}', tex_content)
    if not code_blocks and "listings" not in tex_content:
        # 检查是否有附录代码但没用 listings
        if "\\begin{appendices}" in tex_content or "附录" in tex_content:
            issues.append({"level": "WARN", "rule": "代码格式", "detail": "附录中的代码应使用 listings 宏包"})

    # 6. 页数粗略估算（基于 \newpage 或 \clearpage 数量）
    page_breaks = len(re.findall(r'\\(newpage|clearpage)', tex_content))
    max_pages = profile.get("max_pages", 20)
    if page_breaks > max_pages + 5:  # 粗略估算，允许误差
        issues.append({"level": "WARN", "rule": "页数可能超限", "detail": f"检测到 {page_breaks} 个分页符，限制 {max_pages} 页"})

    # 7. 关键宏包检查
    required_packages = ["amsmath", "graphicx"]
    for pkg in required_packages:
        if f"usepackage{{{pkg}}}" not in tex_content and f"usepackage[{pkg}" not in tex_content:
            issues.append({"level": "INFO", "rule": f"建议加载 {pkg}", "detail": f"竞赛论文通常需要 {pkg} 宏包"})

    passed = not any(i["level"] == "ERROR" for i in issues)
    return {"passed": passed, "issues": issues, "competition_type": competition_type, "profile_name": profile.get("name", "")}
