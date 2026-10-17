"""
Few-Shot Example Service — 从实战数据中提取的训练示例。

每个 stage 的 prompt 注入真实的竞赛案例，让 AI 参照高质量输出。
数据来源：
  - C题解题代码 (1580 行, TOPSIS-GRA + Monte Carlo + Sobol)
  - DeepSeek 10 轮对抗审查 (数学论证 + 代码引用)
  - MIMO 解题代码 (景点特征分析 + 优化行程)
  - 真实竞赛数据 CSV (景点信息、车程矩阵、权重)
"""
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


# ============================================================
# Code-gen few-shot: 真实解题代码模式
# ============================================================

CODE_GEN_EXAMPLE = '''```python
# === 竞赛解题代码示例 ===
# 来源: 2026省赛C题 TOPSIS-GRA 评价模型 (已验证可运行)

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False
import os

# 数据加载（相对路径，可直接运行）
DATA_DIR = "data"
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def solve_problem_1():
    """问题一：熵权法 + TOPSIS-GRA 联合评价"""
    # 构建指标矩阵
    X = df[["游览耗时", "通勤距离", "拥堵敏感度", "喜好度"]].values
    n, m = X.shape

    # 极值标准化（区分正向/逆向指标）
    X_norm = np.zeros_like(X)
    X_norm[:, 0] = (X[:, 0] - X[:, 0].min()) / (X[:, 0].max() - X[:, 0].min())  # 正向
    X_norm[:, 1] = (X[:, 1].max() - X[:, 1]) / (X[:, 1].max() - X[:, 1].min())  # 逆向
    X_norm[:, 2] = (X[:, 2].max() - X[:, 2]) / (X[:, 2].max() - X[:, 2].min())  # 逆向
    X_norm[:, 3] = (X[:, 3] - X[:, 3].min()) / (X[:, 3].max() - X[:, 3].min())  # 正向

    # 熵权法
    p = X_norm / np.sum(X_norm, axis=0)
    e = -(1.0 / np.log(n)) * np.sum(p * np.log(p + 1e-12), axis=0)
    d = 1.0 - e
    w = d / np.sum(d)

    # TOPSIS 评分
    V = X_norm * w
    V_plus = np.max(V, axis=0)
    V_minus = np.min(V, axis=0)
    D_plus = np.sqrt(np.sum((V - V_plus)**2, axis=1))
    D_minus = np.sqrt(np.sum((V - V_minus)**2, axis=1))
    C = D_minus / (D_plus + D_minus)

    # 灰色关联度 (GRA)
    rho = 0.5
    delta = np.abs(X_norm - np.max(X_norm, axis=0))
    grc = (np.min(delta) + rho * np.max(delta)) / (delta + rho * np.max(delta))
    w_grg = np.sum(grc * w, axis=1)

    # 联合评价 (1:1 融合)
    joint_score = 0.5 * C + 0.5 * w_grg
    df["综合排名"] = pd.Series(joint_score).rank(ascending=False).astype(int)

    # 输出结果
    df.to_csv(os.path.join(OUTPUT_DIR, "evaluation.csv"), index=False)
    print(f"权重: {dict(zip(cols, w.round(4)))}")
    print(f"排名: {df.sort_values('综合排名')[['名称','综合排名']].to_string(index=False)}")
```'''


# ============================================================
# Review few-shot: 真实对抗审查模式
# ============================================================

REVIEW_RED_EXAMPLE = '''## 审查示例（来自 DeepSeek 真实审查，已验证数学论证有效）

### 攻击点格式要求：
每个攻击必须包含：
1. **攻击目标**: 具体到论文章节或代码函数名
2. **攻击点**: 一句话概括问题
3. **详细论证**: 数学推导或代码行号引用
4. **结论**: 严重程度判定

### 示例攻击（真实案例摘录）:

**ATTACK: Sobol敏感性分析误用**
- **目标**: 论文第5.4节 + 代码 `evaluate_scheme_stochastic` 函数
- **问题**: 声称使用Sobol全局敏感性分析，实际实现的是OAT（单因子扰动法）
- **论证**:
  - Sobol核心: 同时扰动所有参数，计算条件方差 V(E[Y|Xi])
  - 代码实现: 仅分别关闭交通噪声/排队噪声，计算 var_t/var_all
  - 这是OAT而非Sobol，OAT贡献率之和可远大于100%
  - 论文报告 η_T=132.26% 并用"非线性耦合"解释，实际是方法错误
- **结论**: P0 — 概念性错误，必须修正方法名称和实现

**ATTACK: 首日时间线矛盾**
- **目标**: 论文假设6 + 代码 `check_day_schedule` day_num=1
- **问题**: 模型假设11:30开始游览，但甘特图显示08:30出发
- **论证**:
  - 假设: 7:00出发 + 4h自驾 + 0.5h入住 = 11:30开始
  - 甘特图: 第1天显示 08:00-08:30 通勤前往景点
  - 两者矛盾，说明求解器未遵守自己设定的首日约束
- **结论**: P1 — 内部逻辑不一致
'''


# ============================================================
# Write few-shot: 真实论文结构
# ============================================================

WRITE_STRUCTURE_EXAMPLE = '''## 获奖论文结构示例（来自 CUMCM 2026 省赛 C 题实战）

### 摘要（三段式，250字以内）
第一段（背景目标）: 针对"五一"五日自驾景点优选与行程规划问题，本文建立了基于熵权TOPSIS-GRA联合评价的景点优选模型、时窗约束动态预计算的行程优化模型和蒙特卡洛随机动力学仿真模型。
第二段（核心建模）: 对问题一，构建四维指标体系，采用熵权法客观赋权，TOPSIS-GRA联合评价...；对问题二，设计回溯剪枝算法...；对问题三，引入交通拥堵和排队时长随机扰动...
第三段（结果结论）: 结果表明：A3滨海浴场综合排名第一（评分0.8234）；最优行程5天游览6个景点，总满意度47.3；拥堵敏感度权重54.96%为最关键因素...

### 正文章节
1. 问题重述（1页，用自己的话概括，不照抄原题）
2. 问题分析（定性分析，画流程图，不涉及具体公式）
3. 模型假设（6-8条，每条有依据）
4. 符号说明（三线表，含单位和取值范围）
5. 模型建立与求解
   5.1 问题一：景点优选（熵权法 → TOPSIS → GRA → 联合评分）
   5.2 问题二：行程规划（时窗预计算 → 回溯剪枝 → 多方案生成）
   5.3 问题三：随机仿真（蒙特卡洛10000次 → 方差分解 → 敏感性分析）
6. 灵敏度分析（权重扰动±20%、排队分布参数、拥堵延时系数）
7. 模型评价与改进（优缺点各3条 + 改进方向）
8. 参考文献（≥8条，GB/T 7714格式）
9. 附录（完整Python代码，listings宏包渲染）
'''


# ============================================================
# Decompose few-shot: 真实拆解模式
# ============================================================

DECOMPOSE_EXAMPLE = '''## 赛题拆解示例（2026省赛C题 "五一"五日自驾景点优选与行程规划）

### 题目概述
为三口之家规划五一5天自驾游，从10个景点中选择并安排行程。

### 子问题清单

**子问题1: 景点优选**
- 类型: 评价类
- 目标: 从10个景点中筛选高优先级景点
- 约束: 综合考虑喜好度、通勤距离、拥堵敏感度、游览耗时
- 已知数据: 景点信息表（10行7列）、车程矩阵（10×10）
- 推荐模型: 熵权法 + TOPSIS + 灰色关联分析

**子问题2: 行程规划**
- 类型: 优化类
- 目标: 安排5天行程，最大化总满意度
- 约束: 每天≤2景点、开放时间窗、午餐时间、驾驶疲劳、首日到达时间、末日返程时间
- 已知数据: 子问题1的优选结果、车程矩阵、开放时间
- 推荐模型: 时窗预计算 + 回溯剪枝 + 多目标优化

**子问题3: 鲁棒性评估**
- 类型: 机理分析类
- 目标: 评估行程在随机扰动下的稳定性
- 约束: 交通拥堵随机性、排队时长随机性
- 已知数据: 拥堵延时规则、排队分布参数
- 推荐模型: 蒙特卡洛仿真（≥10000次）+ 方差分解敏感性分析

### 子问题依赖关系
子问题1 → 子问题2 → 子问题3（串行依赖）
'''


# ============================================================
# 公共 API
# ============================================================

FEW_SHOT_MAP = {
    "code-gen": CODE_GEN_EXAMPLE,
    "review-red": REVIEW_RED_EXAMPLE,
    "write": WRITE_STRUCTURE_EXAMPLE,
    "decompose": DECOMPOSE_EXAMPLE,
}


def get_few_shot(stage: str) -> str:
    """获取指定 stage 的 few-shot 示例。"""
    return FEW_SHOT_MAP.get(stage, "")


def get_few_shot_for_prompt(stage: str) -> str:
    """获取格式化后的 few-shot 示例，可直接注入 prompt。"""
    example = FEW_SHOT_MAP.get(stage, "")
    if not example:
        return ""
    return f"\n\n## 实战示例（来自真实竞赛获奖方案）\n\n{example}\n"
