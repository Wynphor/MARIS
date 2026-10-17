"""
Model Knowledge Base — 31 章数学建模方法结构化目录。

基于 docs/math_model-main/模型总结/ 的 31 章 PDF，
提取每种模型的名称、适用题型、Python 实现库、典型应用场景。
用于 model-select stage 的精准推荐。
"""
from typing import Dict

MODEL_CATALOG = [
    {
        "id": 1, "name": "线性规划", "name_en": "Linear Programming",
        "category": "规划优化",
        "keywords": ["资源分配", "生产计划", "运输", "配料", "最优"],
        "python_lib": "scipy.optimize.linprog, PuLP, cvxpy",
        "typical_problems": ["2003A SARS传播", "2005B DVD租赁"],
        "when_to_use": "目标函数和约束都是线性关系时",
        "output": "最优解、影子价格、灵敏度分析",
    },
    {
        "id": 2, "name": "整数规划", "name_en": "Integer Programming",
        "category": "规划优化",
        "keywords": ["选址", "排班", "0-1决策", "组合优化"],
        "python_lib": "PuLP, scipy.optimize.milp, OR-Tools",
        "typical_problems": ["2017B 电影院选址"],
        "when_to_use": "决策变量必须取整数（如是否选择、数量分配）",
    },
    {
        "id": 3, "name": "非线性规划", "name_en": "Nonlinear Programming",
        "category": "规划优化",
        "keywords": ["非线性优化", "曲线拟合", "参数估计"],
        "python_lib": "scipy.optimize.minimize, CVXPY",
        "typical_problems": ["2012B 机器人避障"],
        "when_to_use": "目标函数或约束包含非线性项",
    },
    {
        "id": 4, "name": "动态规划", "name_en": "Dynamic Programming",
        "category": "规划优化",
        "keywords": ["多阶段决策", "最短路径", "背包", "资源分配"],
        "python_lib": "自定义递推, networkx",
        "typical_problems": ["2019B 同步碎纸机"],
        "when_to_use": "问题可分解为相互关联的多阶段子问题",
    },
    {
        "id": 5, "name": "图论与网络", "name_en": "Graph Theory & Networks",
        "category": "规划优化",
        "keywords": ["最短路径", "最大流", "最小生成树", "网络流", "TSP"],
        "python_lib": "networkx, igraph",
        "typical_problems": ["2011B 交巡警平台", "2020B 穿越沙漠"],
        "when_to_use": "问题涉及节点、边、路径、连通性",
    },
    {
        "id": 6, "name": "排队论", "name_en": "Queueing Theory",
        "category": "机理分析",
        "keywords": ["排队", "等待时间", "服务率", "到达率", "M/M/1"],
        "python_lib": "scipy.stats, 自定义仿真",
        "typical_problems": ["2009B 眼科病床安排"],
        "when_to_use": "分析服务系统的等待时间和利用率",
    },
    {
        "id": 7, "name": "博弈论", "name_en": "Game Theory",
        "category": "机理分析",
        "keywords": ["策略", "纳什均衡", "竞争", "合作", "博弈"],
        "python_lib": "nashpy, 自定义矩阵博弈",
        "typical_problems": ["2010B 世博会影响力"],
        "when_to_use": "多方决策者相互影响的策略选择问题",
    },
    {
        "id": 8, "name": "层次分析法 (AHP)", "name_en": "Analytic Hierarchy Process",
        "category": "评价方法",
        "keywords": ["权重", "层次", "一致性", "评价", "决策"],
        "python_lib": "numpy矩阵运算, 自定义AHP",
        "typical_problems": ["2010B 世博会影响力评价"],
        "when_to_use": "多准则决策，需要确定各指标权重",
    },
    {
        "id": 9, "name": "插值与拟合", "name_en": "Interpolation & Fitting",
        "category": "数据处理",
        "keywords": ["曲线拟合", "插值", "回归", "最小二乘"],
        "python_lib": "scipy.interpolate, numpy.polyfit, sklearn",
        "typical_problems": ["2004A 奥运会临时超市"],
        "when_to_use": "需要从离散数据点构建连续函数",
    },
    {
        "id": 10, "name": "统计分析", "name_en": "Statistical Analysis",
        "category": "数据分析",
        "keywords": ["假设检验", "方差分析", "相关性", "置信区间"],
        "python_lib": "scipy.stats, statsmodels",
        "typical_problems": ["2014A 嫦娥三号"],
        "when_to_use": "需要从数据中得出统计结论",
    },
    {
        "id": 11, "name": "方差分析 (ANOVA)", "name_en": "Analysis of Variance",
        "category": "数据分析",
        "keywords": ["方差", "因素", "显著性", "多组比较"],
        "python_lib": "scipy.stats.f_oneway, statsmodels",
        "when_to_use": "比较多组数据均值是否有显著差异",
    },
    {
        "id": 12, "name": "回归分析", "name_en": "Regression Analysis",
        "category": "预测方法",
        "keywords": ["线性回归", "多元回归", "逐步回归", "R²", "残差"],
        "python_lib": "sklearn.linear_model, statsmodels",
        "typical_problems": ["2007A 人口增长预测"],
        "when_to_use": "建立因变量与自变量之间的定量关系",
    },
    {
        "id": 13, "name": "微分方程建模", "name_en": "ODE Modeling",
        "category": "机理分析",
        "keywords": ["动态变化", "速率", "微分方程", "传播模型", "增长模型"],
        "python_lib": "scipy.integrate.odeint, solve_ivp",
        "typical_problems": ["2003A SARS传播", "2020A 体温计"],
        "when_to_use": "描述变量随时间连续变化的动态过程",
    },
    {
        "id": 14, "name": "稳态模型", "name_en": "Steady-State Models",
        "category": "机理分析",
        "keywords": ["平衡", "稳态", "代数方程"],
        "python_lib": "scipy.optimize, sympy",
        "when_to_use": "系统达到平衡状态时的分析",
    },
    {
        "id": 15, "name": "差分方程", "name_en": "Difference Equations",
        "category": "机理分析",
        "keywords": ["离散动态", "递推", "迭代", "离散时间"],
        "python_lib": "numpy递推",
        "when_to_use": "变量按离散时间步变化的动态过程",
    },
    {
        "id": 16, "name": "马尔可夫链", "name_en": "Markov Chains",
        "category": "预测方法",
        "keywords": ["状态转移", "概率", "稳态分布", "马尔可夫"],
        "python_lib": "numpy矩阵幂, scipy.linalg",
        "typical_problems": ["2011B 交巡警平台"],
        "when_to_use": "系统状态按概率转移，且满足无记忆性",
    },
    {
        "id": 17, "name": "变分法", "name_en": "Calculus of Variations",
        "category": "机理分析",
        "keywords": ["泛函极值", "欧拉方程", "最优控制"],
        "python_lib": "自定义数值方法",
        "when_to_use": "寻找使某个泛函取极值的函数",
    },
    {
        "id": 18, "name": "神经网络", "name_en": "Neural Networks",
        "category": "预测方法",
        "keywords": ["深度学习", "BP神经网络", "CNN", "RNN", "LSTM"],
        "python_lib": "PyTorch, TensorFlow, sklearn.neural_network",
        "typical_problems": ["2014B 创意平板折叠"],
        "when_to_use": "数据量大、模式复杂、传统方法难以建模",
    },
    {
        "id": 19, "name": "偏微分方程数值解", "name_en": "PDE Numerical Methods",
        "category": "机理分析",
        "keywords": ["有限差分", "有限元", "热传导", "波动"],
        "python_lib": "FEniCS, scipy, 自定义差分",
        "when_to_use": "涉及空间和时间两个维度的连续变化",
    },
    {
        "id": 20, "name": "目标规划", "name_en": "Goal Programming",
        "category": "规划优化",
        "keywords": ["多目标", "优先级", "偏差变量"],
        "python_lib": "PuLP, 自定义",
        "when_to_use": "有多个目标且按优先级排序",
    },
    {
        "id": 21, "name": "模糊数学", "name_en": "Fuzzy Mathematics",
        "category": "评价方法",
        "keywords": ["模糊", "隶属度", "模糊综合评价", "模糊聚类"],
        "python_lib": "skfuzzy, 自定义",
        "typical_problems": ["2010B 世博会影响力"],
        "when_to_use": "评价指标具有模糊性或不确定性",
    },
    {
        "id": 22, "name": "现代优化算法", "name_en": "Metaheuristic Optimization",
        "category": "规划优化",
        "keywords": ["遗传算法", "模拟退火", "粒子群", "蚁群", "禁忌搜索"],
        "python_lib": "DEAP, pyswarm, 自定义",
        "typical_problems": ["2012B 机器人避障"],
        "when_to_use": "问题规模大、非凸、传统优化难以求解",
    },
    {
        "id": 23, "name": "时间序列分析", "name_en": "Time Series Analysis",
        "category": "预测方法",
        "keywords": ["ARIMA", "季节性", "趋势", "平稳性", "自相关"],
        "python_lib": "statsmodels.tsa, pmdarima",
        "typical_problems": ["2016C 电池放电预测"],
        "when_to_use": "数据按时间顺序排列，需要预测未来值",
    },
    {
        "id": 24, "name": "库存论", "name_en": "Inventory Theory",
        "category": "规划优化",
        "keywords": ["库存", "订货", "EOQ", "安全库存", "再订货点"],
        "python_lib": "scipy.optimize",
        "when_to_use": "涉及库存管理、订货策略优化",
    },
    {
        "id": 25, "name": "经济优化", "name_en": "Economic Optimization",
        "category": "规划优化",
        "keywords": ["成本", "收益", "利润最大化", "边际分析"],
        "python_lib": "scipy.optimize, numpy",
        "when_to_use": "以经济效益为目标的优化问题",
    },
    {
        "id": 26, "name": "运筹学", "name_en": "Operations Research",
        "category": "规划优化",
        "keywords": ["指派", "运输", "选址", "调度"],
        "python_lib": "PuLP, OR-Tools, scipy",
        "when_to_use": "资源分配、任务调度类问题",
    },
    {
        "id": 27, "name": "灰色系统", "name_en": "Grey Systems",
        "category": "预测方法",
        "keywords": ["灰色预测", "GM(1,1)", "灰色关联", "累加生成"],
        "python_lib": "自定义GM模型",
        "typical_problems": ["2007A 人口增长预测"],
        "when_to_use": "数据量少（4-10个点），需要短期预测",
    },
    {
        "id": 28, "name": "多元分析", "name_en": "Multivariate Analysis",
        "category": "数据分析",
        "keywords": ["PCA", "因子分析", "聚类", "判别分析", "主成分"],
        "python_lib": "sklearn.decomposition, sklearn.cluster",
        "typical_problems": ["2012A 葡萄酒评价"],
        "when_to_use": "变量多、需要降维或分类",
    },
    {
        "id": 29, "name": "偏最小二乘回归", "name_en": "PLS Regression",
        "category": "预测方法",
        "keywords": ["多重共线性", "PLS", "降维回归"],
        "python_lib": "sklearn.cross_decomposition",
        "when_to_use": "自变量高度相关且样本量小",
    },
    {
        "id": 30, "name": "蒙特卡洛模拟", "name_en": "Monte Carlo Simulation",
        "category": "机理分析",
        "keywords": ["随机模拟", "抽样", "概率分布", "仿真", "Bootstrap"],
        "python_lib": "numpy.random, scipy.stats",
        "typical_problems": ["2020B 穿越沙漠"],
        "when_to_use": "问题涉及随机性，需要通过大量模拟评估概率",
    },
    {
        "id": 31, "name": "TOPSIS-GRA 联合评价", "name_en": "TOPSIS-GRA Combined Evaluation",
        "category": "评价方法",
        "keywords": ["逼近理想解", "灰色关联", "综合评价", "多属性"],
        "python_lib": "自定义, numpy",
        "typical_problems": ["2026C 自驾景点优选"],
        "when_to_use": "需要同时考虑距离和趋势的综合评价",
    },
]

# 题型 → 推荐模型组合
TYPE_MODEL_COMBOS = {
    "优化类": {
        "must_have": ["线性规划或整数规划", "灵敏度分析"],
        "recommended": ["非线性规划", "动态规划", "遗传算法"],
        "加分项": ["Pareto前沿分析", "鲁棒优化"],
    },
    "评价类": {
        "must_have": ["权重确定方法(AHP/熵权法)", "综合评价模型"],
        "recommended": ["TOPSIS", "灰色关联", "因子分析"],
        "加分项": ["一致性检验", "灵敏度分析", "多种方法对比"],
    },
    "预测类": {
        "must_have": ["回归分析或时间序列", "误差评估(RMSE/MAPE/R²)"],
        "recommended": ["ARIMA", "灰色预测", "神经网络"],
        "加分项": ["置信区间", "交叉验证", "多模型对比"],
    },
    "机理分析类": {
        "must_have": ["微分方程或物理建模", "数值求解"],
        "recommended": ["蒙特卡洛模拟", "有限元", "排队论"],
        "加分项": ["参数标定", "模型验证", "灵敏度分析"],
    },
}

# 公式 → 模型映射（结构化索引）
FORMULA_INDEX = {
    "min Σc·x": ["线性规划", "整数规划"],
    "max Σw·s": ["TOPSIS", "综合评价"],
    "y = β₀ + β₁x": ["多元回归", "线性回归"],
    "AR(p) MA(q)": ["ARIMA", "时间序列"],
    "dx/dt = f(x,t)": ["微分方程", "动力学建模"],
    "P(A|B) = P(B|A)P(A)/P(B)": ["贝叶斯", "概率模型"],
    "R² = 1 - SS_res/SS_tot": ["回归分析", "拟合优度"],
    "RMSE = √(Σ(ŷ-y)²/n)": ["预测评估", "回归分析"],
    "MAPE = Σ|y-ŷ|/y/n": ["预测评估", "时间序列"],
    "χ² = Σ(O-E)²/E": ["卡方检验", "独立性检验"],
    "F = MS_between/MS_within": ["方差分析", "ANOVA"],
    "dijkstra": ["最短路径", "图论"],
    "min cut = max flow": ["最大流", "网络优化"],
    "遗传/选择/交叉/变异": ["遗传算法", "智能优化"],
    "蒙特卡洛": ["蒙特卡洛模拟", "随机仿真"],
    "TOPSIS距离": ["TOPSIS", "多属性决策"],
    "AHP判断矩阵": ["层次分析法", "AHP"],
    "熵权 H = -Σp·ln(p)": ["熵权法", "客观赋权"],
    "灰色 GM(1,1)": ["灰色预测", "少数据预测"],
    "BP神经网络": ["BP神经网络", "深度学习"],
    "SVM超平面": ["支持向量机", "分类"],
    "K-means聚类": ["K-means", "聚类分析"],
    "PCA特征值": ["主成分分析", "降维"],
    "马尔可夫转移矩阵": ["马尔可夫链", "随机过程"],
}

# 图表风格 → 推荐图表类型
CHART_STYLE_INDEX = {
    "折线图": {"models": ["ARIMA", "时间序列", "回归分析"], "use": "趋势展示"},
    "柱状图": {"models": ["TOPSIS", "综合评价", "AHP"], "use": "对比分析"},
    "热力图": {"models": ["相关分析", "聚类分析"], "use": "矩阵可视化"},
    "散点图": {"models": ["回归分析", "聚类分析"], "use": "关系展示"},
    "箱线图": {"models": ["统计分析", "异常检测"], "use": "分布展示"},
    "三维曲面": {"models": ["优化模型", "响应面"], "use": "参数空间"},
    "雷达图": {"models": ["TOPSIS", "综合评价"], "use": "多维度对比"},
    "桑基图": {"models": ["流程分析", "能源模型"], "use": "流量展示"},
    "等高线图": {"models": ["优化模型", "插值"], "use": "空间分布"},
    "Gantt图": {"models": ["调度优化", "项目管理"], "use": "时间安排"},
    "Pareto前沿": {"models": ["多目标优化", "遗传算法"], "use": "权衡分析"},
    "敏感性 tornado": {"models": ["敏感性分析", "鲁棒性"], "use": "参数影响"},
}


def get_model_by_id(model_id: int) -> Dict:
    """按 ID 获取模型详情。"""
    for m in MODEL_CATALOG:
        if m["id"] == model_id:
            return m
    return {}


def search_models(query: str) -> list:
    """按关键词搜索模型（支持模糊匹配和概念匹配）。"""
    results = []
    query_lower = query.lower().strip()
    query_terms = [t.strip() for t in query_lower.split() if t.strip()]

    if not query_terms:
        return results

    # Concept mapping: user-friendly terms → model keywords
    CONCEPT_MAP = {
        "预测": ["预测", "时间序列", "ARIMA", "LSTM", "回归", "forecast"],
        "分类": ["分类", "判别", "聚类", "SVM", "随机森林", "classification"],
        "优化": ["优化", "规划", "遗传算法", "模拟退火", "optimization", "线性规划"],
        "评价": ["评价", "评估", "TOPSIS", "AHP", "熵权", "灰色关联", "evaluation"],
        "拟合": ["拟合", "回归", "插值", "曲线", "curve fitting"],
        "仿真": ["仿真", "蒙特卡洛", "模拟", "Monte Carlo", "simulation"],
        "图论": ["图论", "最短路径", "网络", "Dijkstra", "graph"],
        "统计": ["统计", "假设检验", "方差分析", "回归分析", "statistics"],
        "机器学习": ["机器学习", "随机森林", "XGBoost", "神经网络", "ML", "深度学习"],
        "微分方程": ["微分方程", "ODE", "PDE", "动力学", "differential"],
    }

    # Expand query terms with concepts
    expanded_terms = set(query_terms)
    for term in query_terms:
        for concept, aliases in CONCEPT_MAP.items():
            if term in concept or concept in term:
                expanded_terms.update(aliases)
            for alias in aliases:
                if term in alias.lower() or alias.lower() in term:
                    expanded_terms.update(aliases)

    for m in MODEL_CATALOG:
        score = 0
        name_lower = m["name"].lower()
        name_en_lower = m.get("name_en", "").lower()
        keywords = [kw.lower() for kw in m.get("keywords", [])]
        when_lower = m.get("when_to_use", "").lower()

        for term in expanded_terms:
            # Exact name match (highest weight)
            if term in name_lower or term in name_en_lower:
                score += 10
            # Keyword exact match
            if any(term in kw for kw in keywords):
                score += 5
            # when_to_use match
            if term in when_lower:
                score += 3
            # Partial keyword match
            if any(term in kw or kw in term for kw in keywords if len(kw) >= 2):
                score += 2

        if score > 0:
            results.append({**m, "_score": score})

    results.sort(key=lambda x: x["_score"], reverse=True)
    return results


def recommend_for_type(problem_type: str) -> Dict:
    """根据题型推荐模型组合。"""
    for key, combo in TYPE_MODEL_COMBOS.items():
        if key in problem_type or problem_type in key:
            # 从 catalog 中找到对应的模型详情
            models = []
            for m in MODEL_CATALOG:
                if any(kw in m.get("keywords", []) for kw in
                       combo["must_have"] + combo["recommended"]):
                    models.append(m)
            return {
                "problem_type": key,
                "combo": combo,
                "models": models[:8],
            }
    return {
        "problem_type": problem_type,
        "combo": TYPE_MODEL_COMBOS.get("优化类", {}),
        "models": MODEL_CATALOG[:5],
    }


def search_by_formula(formula_query: str) -> list:
    """根据公式或数学表达式搜索匹配的模型。"""
    query_lower = formula_query.lower().strip()
    matches = []
    for formula, model_names in FORMULA_INDEX.items():
        if query_lower in formula.lower() or formula.lower() in query_lower:
            for name in model_names:
                model = next((m for m in MODEL_CATALOG if name in m["name"]), None)
                if model and model not in matches:
                    matches.append({**model, "_matched_formula": formula})
    return matches


def search_by_chart_style(chart_query: str) -> dict:
    """根据图表类型搜索推荐的模型和用途。"""
    query_lower = chart_query.lower().strip()
    for chart_name, info in CHART_STYLE_INDEX.items():
        if query_lower in chart_name.lower() or chart_name.lower() in query_lower:
            return {"chart": chart_name, **info}
    # Fuzzy match
    for chart_name, info in CHART_STYLE_INDEX.items():
        if any(c in chart_name for c in query_lower if len(c) > 1):
            return {"chart": chart_name, **info}
    return {}


def get_full_context(problem_type: str) -> dict:
    """获取完整的模型上下文（用于 prompt 注入）。"""
    type_rec = recommend_for_type(problem_type)
    return {
        "type_recommendation": type_rec,
        "formula_count": len(FORMULA_INDEX),
        "chart_types": list(CHART_STYLE_INDEX.keys()),
        "total_models": len(MODEL_CATALOG),
    }
