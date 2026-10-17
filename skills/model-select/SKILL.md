---
name: model-select
description: "为数学建模子问题推荐模型和求解算法。基于问题特征和历史题型解法，输出候选模型列表和推荐方案。"
argument-hint: "<problem_decomposition.md 路径>"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# Model Select: 模型推荐

根据子问题特征推荐数学模型：**$ARGUMENTS**

## Constants

- **DRIVEN_MODEL = `deepseek-v4-pro`** — 需要跨领域知识检索
- **OUTPUT_FILE = `model_recommendation.md`** — 输出文件，供下游 `code-template` 消费
- **MODEL_BOOK = `docs/math_model-main/模型总结/`** — 31 章模型参考书，按需查阅

## Inputs

1. `problem_decomposition.md` — 来自 `problem-decompose`
2. 可选：赛题类型的范文检索结果（来自 `paper-reference`）

## Outputs

输出 `model_recommendation.md`：

```markdown
# 模型推荐报告

## 子问题 1: [名称] — [类型]

### 候选模型对比
| 模型 | 优势 | 劣势 | 适用条件 | 推荐度 |
|------|------|------|---------|--------|
| ... | ... | ... | ... | ★★★ |
| ... | ... | ... | ... | ★★☆ |

### 推荐方案
- **首选模型**: ...
- **模型假设**: 1. ... 2. ...
- **求解算法**: ...
- **备选方案**: （若首选不收敛/数据不满足假设）
- **参考实现**: Python 库 `xxx`
```

## 典型题目-模型映射表（案例驱动）

优先匹配相似题型的历史解法：

| 题型 | 经典赛题 | 常用模型 | 求解工具 |
|------|---------|---------|---------|
| 优化类 | 2020C 信贷决策、2019C 机场出租车 | 线性规划、整数规划、多目标规划、动态规划 | PuLP, scipy.optimize, Pyomo |
| 评价类 | 2012A 葡萄酒评价、2010B 世博会影响力 | AHP层次分析、TOPSIS、模糊综合评价、熵权法 | numpy, 自定义实现 |
| 预测类 | 2007A 人口增长、2016C 电池放电 | 时间序列(ARIMA)、灰色预测GM(1,1)、回归分析、BP神经网络 | statsmodels, sklearn, 自定义 |
| 机理分析 | 2018A 高温服装、2016B 小区道路 | 微分方程、差分方程、热传导方程、有限元 | scipy.integrate, sympy |
| 统计分析 | — | 聚类、主成分分析、回归、假设检验、相关性分析 | sklearn, scipy.stats |
| 图论/网络 | 2019C 机场出租车 | 最短路径、最大流、最小生成树、网络流 | networkx |
| 环境经济学 | 2025C 气候变化政策 | Kaya恒等式、STIRPAT模型、LMDI分解 | statsmodels, 自定义 |
| 交通流 | 2025E 混合交通流 | LWR模型、跟驰模型、元胞自动机 | numpy, 自定义 |
| 图像增强 | 2025D 指纹增强 | CNN(U-Net)、GAN、传统滤波(直方图均衡化) | PyTorch, OpenCV, skimage |

## Workflow

### Step 1: 读取子问题

解析 `problem_decomposition.md`，提取每个子问题的类型、约束、目标和数据描述。

### Step 2: 案例匹配

1. 对照"典型题目-模型映射表"，找与当前子问题最相似的经典赛题
2. 如果相似度超过 80%，直接推荐该经典题的建模路径
3. 否则，按子问题类型从映射表中筛选候选模型
4. **ARIS 调用**: `research-wiki` 查询历史赛题的建模经验，`idea-creator` / `idea-discovery` 构思建模创新方向

### Step 3: 候选模型评估

对每个候选模型列出：
- 优势（为什么适合这个子问题）
- 劣势（为什么不选）
- 适用条件（数据量、分布假设、线性/非线性等）
- 推荐度（★★★首选 / ★★☆备选 / ★☆☆不推荐）
- **对比指标**：每个模型附预期性能估计和复杂度评级

### Step 4: 推荐首选方案

给出首选模型 + 备选方案 + 模型假设 + 求解算法 + Python 库。
- **ARIS 调用**: `research-refine` 细化方案
- **多模型要求**: 对比表至少含 3 个模型。选中模型必须附"为何选它而非其他"的论证

### Step 5: 自检 + 查新

- 模型假设是否与题目约束一致？
- 数据量是否满足模型要求？
- 是否有更简单的模型也能解决问题？（Occam 原则：能用简单模型不用复杂模型）
- 是否参考了同题型获奖论文的建模路径？
- **ARIS 调用**: `novelty-check` 验证推荐的首选建模方案是否已有类似解法，避免"创新"实为重复
