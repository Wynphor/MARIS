# Project Instructions

This file provides context for AI assistants working on this project.

## 项目定位

**将 ARIS (Auto-claude-code-research-in-sleep) 改造为数学建模竞赛自动化工具。**

本工作区包含两个子项目：

| 路径 | 角色 |
|------|------|
| `Auto-claude-code-research-in-sleep-main/` | **改造基座** — ARIS 框架，80+ skills，需适配到数学建模场景 |
| `src/`, `data/`, `output/`, `paper/` | **竞赛工作区** — 赛题求解、代码、数据、论文产出 |

## 改造目标

ARIS 的 skill 体系面向学术 ML 研究（实验迭代 → 论文投稿），数学建模竞赛的工作流不同：

```
读题 → 问题拆解 → 文献调研 → 建模 → 公式推导 → 编程求解 → 结果分析 → 论文写作 → 自审 → 定稿
```

### ARIS 现有能力 → 数学建模映射

> ARIS 提供 80 个 skill（含 Gemini/Claude/Codex 三个审查变体层）。skills-mathmodel 作为**编排层**调用 ARIS skill 完成原子任务，自身只保留竞赛特有的规则和映射表。

| 竞赛阶段 | ARIS Skill | 调用时机 | 配合的 mathmodel Skill | 驱动模型 |
|---------|-----------|---------|----------------------|---------|
| **读题拆解** | `research-lit` | 拆题前：检索类似赛题的学术文献作为参考 | `problem-decompose` | MiMo |
| | `exa-search` / `gemini-search` | 搜索赛题背景资料、数据源 | `problem-decompose` | MiMo |
| **文献调研** | `arxiv` / `semantic-scholar` / `deepxiv` / `openalex` | 第1天下午：检索类似模型论文 | 独立使用 | MiMo |
| | `comm-lit-review` | 结构化整理文献综述 | 独立使用 | MiMo |
| **建模构思** | `idea-creator` / `idea-discovery` | 构思建模创新方向 | `model-select` | V4 Pro |
| | `novelty-check` | 验证建模方案是否已有类似解法 | `model-select` | MiMo |
| | `research-wiki` | 查询历史赛题建模经验 | `model-select` | — (本地) |
| **方案细化** | `research-refine` | 模型推荐后：将建模方向细化为可执行的方法计划 | `model-select` → `code-template` 之间 | V4 Pro |
| **公式推导** | `formula-derivation` | 系统化推导模型公式 | 建模→写作之间 | V4 Pro |
| | `proof-writer` + `proof-checker` | 写证明→验证闭环 | 独立使用 | V4 Pro |
| **求解设计** | `experiment-plan` | 代码生成前：规划参数矩阵和求解方案 | `code-template` | V4 Pro |
| | `experiment-bridge` | idea→代码实现的桥接 | `code-template` | V4 Pro |
| **求解执行** | `run-experiment` | 管理脚本执行和结果追踪 | 代码→运行 | MiMo |
| | `experiment-queue` | 多参数扫描的作业队列 | `sensitivity-analysis` | — (本地) |
| **结果分析** | `analyze-results` | 统计检验+对比表 | `sensitivity-analysis` | MiMo |
| | `result-to-claim` | 数值结果→论文声明 | 写作前 | MiMo |
| **图表生成** | `paper-figure` | 数据驱动图表（折线/柱状/热力） | Phase 2 | V4 Pro |
| | `figure-spec` / `mermaid-diagram` | 架构图/流程图 | Phase 2 | MiMo |
| **图表审查** | `skills-codex-gemini-review/paper-figure` | Gemini 审查图表质量 | Phase 2 [人工] | Gemini |
| **范文检索** | `paper-reference`（新增） | 检索获奖范文结构/术语/图表风格 | Phase 2 | MiMo |
| **论文写作** | `paper-plan` → `paper-write` → `paper-compile` | 大纲→逐章生成→编译 PDF | Phase 2 | V4 Pro |
| | `shared-references/writing-principles.md` | 写作原则注入 | `paper-write` 全流程 | — |
| | `shared-references/venue-checklists.md` | CUMCM venue 检查清单 | 终稿前 | — |
| **论文审查** | `auto-review-loop`（3 变体） | 多轮审查循环 | 写作后 | V4 Pro + MiMo |
| | `skills-codex-gemini-review/auto-review-loop` | Gemini 驱动审查 | [人工] | Gemini |
| | `kill-argument` | 对抗性论点检验（MiMo攻击→V4 Pro防御） | 审查后 | V4 Pro + MiMo |
| | `auto-paper-improvement-loop` | 审查→修改→再审自动循环 | 审查后 | MiMo |
| | `paper-claim-audit` | 验证论文声明是否有数据支持 | 终稿前 | MiMo |
| | `citation-audit` | 验证参考文献真实性 | 终稿前 | MiMo |
| | **知识积累** | `research-wiki` | 赛后保存本次赛题建模经验 | 赛后 | — |
| **提交打包** | `submit-pack`（新增） | 论文+代码+数据→RAR 支撑材料 | 提交前 | — (纯脚本) |

### 两层架构：skills-mathmodel（编排层）→ ARIS Skills（能力层）

```
竞赛流程:   读题 → 拆解 → 文献 → 建模 → 推导 → 求解 → 分析 → 图表 → 写作 → 审查 → 打包

编排层:    problem-decompose   model-select  code-template   sensitivity   paper-ref   contest-format
              │                    │              │              │             │             │
能力层:    research-lit        idea-creator   experiment-plan  analyze-res   paper-plan   jurisdiction
(ARIS)     exa-search          novelty-check  run-experiment   results       paper-write   -format
           gemini-search       research-wiki  experiment-bridge result-to-claim paper-compile
           arxiv/semantic-scholar  formula-derivation  experiment-queue  paper-figure
           deepxiv/openalex     proof-writer                        figure-spec
           comm-lit-review      proof-checker                       mermaid-diagram

跨模型审查层 (Gemini/Claude/Codex 变体):
           skills-codex-gemini-review/*
           auto-review-loop (3 变体)  →  kill-argument  →  auto-paper-improvement-loop
           paper-claim-audit  →  citation-audit
```

- **编排层** (`skills-mathmodel/`)：定义竞赛流程、竞赛规则、题型映射表，不重复造轮子
- **能力层** (ARIS `skills/`)：执行原子任务——搜索、推导、写作、审查
- **跨模型审查层** (`skills-codex-gemini-review/`)：Gemini 驱动的交叉审查，竞赛期间人工切换网络后触发

### 数学建模专用 Skills（新建，模型分工标注）

#### 1. `problem-decompose` — 赛题拆解
- **驱动模型**: DeepSeek V4 Pro（需要深度语义理解）
- **输入**: 赛题 PDF / 题目描述
- **输出**: 子问题清单、各子问题的约束条件、优化目标、已知数据维度
- **复用 ARIS**: 无直接对应 skill，全新设计

#### 2. `model-select` — 模型推荐
- **驱动模型**: DeepSeek V4 Pro（需要跨领域知识检索）
- **输入**: 子问题特征（来自 `problem-decompose`）
- **输出**: 推荐模型列表（含优劣势对比）、选定模型的假设条件、求解算法建议
- **支持类型**: 线性规划、整数规划、非线性规划、多目标规划、微分方程、图论、统计回归、时间序列、聚类、分类、排队论、博弈论、环境经济学模型（Kaya恒等式/STIRPAT/LMDI分解）、交通流模型（LWR/跟驰模型/元胞自动机）、图像增强（CNN/GAN/传统滤波）
- **案例驱动**: 内置典型题目-模型映射表（从获奖论文反推建模路径），竞赛时优先匹配相似题型的历史解法
- **复用 ARIS**: 部分借鉴 `idea-creator` 的结构化推荐逻辑

#### 3. `code-template` — 代码骨架生成
- **驱动模型**: DeepSeek V4 Pro（代码生成主力）
- **输入**: 选定模型 + 参数说明（来自 `model-select`）
- **输出**: 可直接运行的 Python 脚本（含 docstring、数据加载、模型构建、求解、结果输出）
- **模板库**: LP(Numpy+Scipy/PuLP)、NLP(cvxpy)、多目标优化(Pyomo/NSGA-II)、ODE(scipy.integrate)、回归/聚类(sklearn)、图论(networkx)、图像增强(OpenCV/PyTorch/skimage)、交通流建模(LWR/跟驰/元胞自动机)
- **复用 ARIS**: `run-experiment` 的脚本管理逻辑

#### 4. `data-preprocess` — 数据预处理
- **驱动模型**: DeepSeek V4 Pro（需理解数据语义）
- **输入**: 原始数据文件 + 赛题对数据的描述
- **输出**: 清洗后数据、缺失值报告、标准化/归一化代码
- **数据采集**（附属于 data-preprocess，非独立 skill）：当赛题要求自行收集数据时（如 2025 C 题），负责从公开数据源（国家统计局、世界银行、各省统计年鉴等）自动获取或指导人工获取所需数据。该模块以脚本模板形式提供，非完全自动化。
- **复用 ARIS**: 无直接对应，全新设计

#### 5. `sensitivity-analysis` — 敏感性分析
- **驱动模型**: DeepSeek V4 Pro（计算密集型）+ MiMo V2.5（分析报告撰写）
- **输入**: 模型求解结果（来自 `code-template` 执行输出）
- **输出**: 参数扫描结果图表、模型鲁棒性结论
- **复用 ARIS**: `analyze-results` 的分析框架

#### 6. `contest-format` — 竞赛格式适配
- **驱动模型**: MiMo V2.5/Pro（格式检查，成本更低）
- **输入**: 论文初稿
- **输出**: 格式合规检查报告（目录、摘要分页、参考文献标注、身份信息屏蔽、页数检查）
- **复用 ARIS**: `paper-compile` 的 LaTeX 编译链，`auto-review-loop` 的检查逻辑

#### 7. `submit-pack` — 提交物打包（实用工具 skill）
- **驱动模型**: 无需 LLM，纯脚本工具（Python 自动化打包）
- **输入**: 论文 PDF + 源代码 + 数据文件
- **输出**: 符合竞赛规范的 RAR 支撑材料包（≤20MB）、最终提交检查清单
- **复用 ARIS**: 无直接对应，基于竞赛提交规范全新设计

#### 8. `paper-reference` — 获奖范文检索（新增）
- **驱动模型**: MiMo V2.5/Pro（语义匹配+结构提取，成本更低）
- **输入**: 赛题类型（优化/评价/预测/机理/统计/图论）+ 题目关键词
- **输出**: 
  - 匹配的国赛获奖范文（含年份、题号、获奖等级）
  - 范文结构骨架（章节组织、公式排版风格）
  - 高分术语表（如"灵敏度分析表明""模型的鲁棒性通过XX验证"）
  - 图表规范参考（三线表样式、配色方案、图题表题格式）
- **数据源**:
  - `docs/1.国赛：高教社杯全国大学生数学建模竞赛优秀论文【数学建模老哥】/数学建模典型题目优秀论文/` — 按题型分类的8道经典题40+篇范文
  - `docs/1.国赛：高教社杯全国大学生数学建模竞赛优秀论文【数学建模老哥】/` — 1992-2024年度论文库
- **复用 ARIS**: `paper-plan` 的结构化分析逻辑 + `research-lit` 的文献检索模式

## 技术栈（竞赛求解用）

- **语言**: Python 3.10+
- **建模/优化**: numpy, scipy, pulp / cvxpy, sympy
- **数据处理**: pandas, openpyxl
- **可视化**: matplotlib, seaborn
- **论文排版**: LaTeX → PDF

```bash
pip install numpy scipy pandas matplotlib seaborn sympy pulp openpyxl
```

## 目标大模型

适配以下大模型驱动自动化流程：

- **Gemini (Antigravity)** — 核心执行器 (Gemini CLI Headless) + 图像生成 (`figure-spec`/`mermaid-diagram`) 与对抗性 AI 审查 (`auto-review-loop`/`auto-paper-improvement-loop`/`paper-claim-audit`) 驱动模型。
- **DeepSeek V4 Pro** — 供手动深入推导与大块论文精细写作备用（通过 API 接入，成本较高）。
- **MiMo V2.5-Pro**（旗舰版）— 中等推理：查新判断 (`novelty-check`)、数值声明提取 (`result-to-claim`) 等。
- **MiMo V2.5**（全模态标准版）— 轻量执行：搜索 (`research-lit`/`arxiv` 等)、格式化、脚本运行、格式合规检查等。

### 模型分工映射表

| 驱动模型 | 适用任务 | 特征 |
|------|---------|------|
| **Gemini (Antigravity)** | 核心流程运行、`figure-spec`、`mermaid-diagram` (图像生成)、`auto-review-loop` (审稿人)、`auto-paper-improvement-loop` (攻击与防御自动修复)、`paper-claim-audit` (数据核验) | 拥有极强逻辑推理、图像生成规划与审查防御能力 |
| **MiMo V2.5-Pro** | `novelty-check`、`result-to-claim` | 需要一定推理和语义理解，比通用标准版更聪明 |
| **MiMo V2.5** | `research-lit`、`exa-search`、`arxiv`/`semantic-scholar`、`comm-lit-review`、`run-experiment`、`analyze-results`、`paper-reference`、`contest-format`、`citation-audit` | 纯执行任务：信息检索、数据统计、确定性计算、格式规范检查，额度极度充沛 |

## 竞赛规则要点（第三届山东省大学生数学建模竞赛）

- **竞赛时间**：2026年5月21日20:00 — 5月24日20:00（已结束；当前开发按赛后产品化与复盘迭代推进）
- **报名截止**：2026年5月21日12:00
- **官方系统**：http://47.99.94.74（队长缴纳120元报名费）
- **双渠道报名**：官方系统 + 山东省科协网站

从 `docs/` 下的章程和参赛规则 PDF 中提取的关键约束：

### 论文结构（强制顺序）
1. **目录**（第1页）
2. **摘要专用页**（第2页，含标题+关键词，单独一页，不超过一页）
3. **正文**（第3页起，尽量≤20页）
4. **附录**（页数不限，可放图表等）
5. **参考文献**（正文引用处用[1][2]标注，按引用次序列出）

### 提交物
- 电子版论文 PDF
- 支撑材料 RAR（≤20MB）：含所有源程序、数据（赛题原始数据除外）、中间结果图表、参考资料

### 评分标准
假设的合理性 > 建模的创造性 > 结果的正确性 > 文字表述的清晰程度

### 往届赛题分析（2024-2025 山东省赛）

#### 2025 年本科组真题（C/D/E）
| 题号 | 标题 | 类型 | 关键特征 |
|:---|:---|:---|:---|
| **C** | 基于经济发展与环境污染关系的中国气候变化政策优化 | 多目标优化+数据分析 | 碳排放最小化+GDP最大化双目标，**需自行收集数据**，区域差异化政策 |
| **D** | 潜在指纹增强问题 | 图像处理/ML | 720张指纹图像，训练集600+测试集120，rank-n识别率评价，**含附件数据** |
| **E** | 城市混合交通流拥堵效应与电动自行车管理策略 | 交通流建模+灵敏度分析 | 交通违规行为量化、限速策略评估、数值模拟 |

#### 2024 年题目
| 题号 | 类型 | 核心关键词 |
|:---|:---|:---|
| A题 | 工程优化 | 生产调度、设备约束 |
| B题 | 数据分析 | 新质生产力、因素分析 |
| C题 | 资源调度 | 乡村振兴、土地/物流配置 |

**核心结论**：
- **题型多样化超出预期**：除传统优化外，2025 年出现了环境经济学+政策分析、图像增强(ML)、交通流建模——覆盖面极广
- **数据采集是刚需**：C 题明确要求"收集并整理相关数据"，自动化流程必须具备从公开数据源获取数据的能力
- **图像/ML 不可忽视**：D 题是纯图像处理问题，需支持 OpenCV/PyTorch/scikit-image
- **地方特色**：题目常结合山东省政策背景（电动自行车管理、乡村振兴等），论文中需融入政策分析

### 通用题型分类（六大类，用于 skill 适配）

| 类型 | 典型场景 | 常用模型 |
|------|---------|---------|
| **优化类** | 资源分配、路径规划、调度排产 | 线性规划、整数规划、动态规划、遗传算法 |
| **评价类** | 综合评估、排名、风险评级 | AHP、TOPSIS、模糊综合评价、熵权法 |
| **预测类** | 趋势预测、数值预报 | 时间序列、回归分析、神经网络、灰色预测 |
| **机理分析类** | 物理/化学/生物过程建模 | 微分方程、差分方程、热传导方程 |
| **统计分析类** | 数据挖掘、关联分析 | 聚类、主成分分析、回归、假设检验 |
| **图论/网络类** | 路径优化、网络流、社区发现 | 最短路径、最大流、最小生成树 |

### 三天竞赛节奏（标准分工模板）

| 阶段 | 时间 | 核心任务 | 输出 |
|------|------|---------|------|
| **第1天·上午** | 4h | 读题、选适合的题目、确认题意理解 | 选定题目，初步思路 |
| **第1天·下午** | 6h | 文献查阅、问题拆解、确定建模方案 | 模型选型、参考文献清单 |
| **第2天·上午** | 4h | 模型建立与公式推导 | 数学模型表达式 |
| **第2天·下午** | 6h | 编程实现、求解、初步结果 | 可运行的代码 + 结果数据 |
| **第3天·上午** | 4h | 结果分析、图表制作、敏感性分析 | 分析结论、可视化图表 |
| **第3天·下午** | 6h | 论文写作（摘要最后写）、格式检查、提交 | 完整论文 PDF + RAR |

### 论文必含要素（按评分优先级）

1. **问题重述与分析**（简要、精准）
2. **模型假设**（合理、有依据）—— 评分权重最高
3. **符号说明**（清晰统一）
4. **模型建立与求解**（公式推导 + 算法设计）—— 核心部分
5. **模型检验与灵敏度分析**（证明鲁棒性）
6. **模型优缺点与改进方向**
7. **参考文献**（按引用顺序编号，正文用[1][2]标注）

### 摘要写作"黄金公式"（高分关键）

摘要必须单独一页，三段式结构：
1. **背景目标（20%）**：针对XX问题，建立XX模型，旨在XX
2. **核心建模（50%）**：模型名称 + 算法步骤 + 求解软件
3. **结果结论（30%）**：**必须包含具体数值结果**（如"成本降低了12.5%"）

严禁：第一人称、公式/图表入摘要、空话废话。用"本文"自称。

### 写作避坑要点

- **建模原则**：能用简单模型讲清楚的，绝不用复杂模型。小样本强行用深度学习 = 扣分
- **灵敏度分析**：改变关键参数，观察结果波动，这是证明模型鲁棒性的唯一方法，**高分必做**
- **数据清洗**：原始数据多有异常值，直接跑模型出废品。预处理不可跳过
- **论文手节奏**：从第1天就开始写框架，不能等最后一天。论文质量决定奖项上限
- **选题铁律**：纠结不超过6小时，中途换题是大忌
- **图表审查**：生成全部图表后，用 Gemini CLI 逐张审查——色板是否 colorblind-safe、三线表是否规范、字号是否与正文匹配（10pt）、标注是否完整。图表质量直接决定论文第一印象

### LaTeX 模板

- **已有模板**：`docs/2026国赛最新模版（Word+LaTeX）/数学建模国赛latex模板/` — 含 `example.tex` + `cumcmthesis.cls`
- **省赛适配要点**：
  - 使用 `\documentclass{cumcmthesis}`（不要用 `withoutpreface` 选项，省赛需要封面）
  - 添加目录页（省赛要求第1页为目录，与国赛不同）
  - 封面用 `pdfpages` 宏包插入官方 Word 转 PDF 封面
  - 引用标准：GB/T 7714
  - **表图规范**：全篇统一三线表，配色专业（拒绝 Excel 默认色）
  - 页码从摘要页开始（`\setcounter{page}{1}` 放在摘要页）
- **模型参考书**：`docs/math_model-main/模型总结/` — 31 章覆盖所有常用模型算法
- **获奖论文参考库**：
  - `docs/1.国赛：高教社杯全国大学生数学建模竞赛优秀论文【数学建模老哥】/数学建模典型题目优秀论文/` — 按题型分类的8道经典题40+篇国赛获奖范文，用于 `paper-reference` 和 `paper-write` 的范文注入
  - `docs/1.国赛：高教社杯全国大学生数学建模竞赛优秀论文【数学建模老哥】/` — 1992-2024 年度论文库，按年份/题号索引，用于补充检索
  - `docs/cumcm-past-questions-master/全国大学生数学建模竞赛(CUMCM)优秀论文/` — 2012-2021 年度论文（原有资源，可交叉参考）

### 关键约束
- **3天限时**，周末前后举行
- 3人一队，竞赛期间**禁止与队外任何人讨论**（含指导教师）
- 严禁抄袭，引用必须规范标注
- 论文正文和附录**不得出现任何身份信息**（学校、姓名等）
- 题组：专科 A/B、本科 C/D/E、研究生 F/G

## 目录约定

```
shuxuejianmo/
├── Auto-claude-code-research-in-sleep-main/
│   ├── skills/              # ARIS 现有 skills（只读参考，不直接修改）
│   ├── skills-mathmodel/    # 数学建模专用 skills（新增，改造产出）
│   └── tools/               # ARIS 工具脚本
├── src/                     # 竞赛求解脚本
│   └── problem_a/           # 每个赛题独立子目录
├── data/                    # 原始数据 & 预处理数据
├── output/
│   ├── figures/             # 图表
│   └── tables/              # 结果表
├── paper/                   # LaTeX 论文源文件
├── docs/                    # 竞赛规则、章程、往届赛题、获奖论文、模型参考书等
├── AGENTS.md
└── .gitignore
```

### docs/ 检索纪律

`docs/` 下资料按角色分三类，检索时必须遵守优先级：

| 角色 | 目录/文件 | 使用场景 | 优先级 |
|------|----------|---------|--------|
| **规则** | `山东省大学生数学建模竞赛参赛规则.pdf`、`章程.pdf`、`报名通知.pdf` | 查竞赛规则、提交要求、格式约束 | 🔴 最高，规则不可被参考材料覆盖 |
| **真题** | `2025年本科组真题/` | 当前竞赛的题目（省赛 C/D/E） | 🔴 最高，赛题内容是唯一真相源 |
| **范文** | `1.国赛：高教社杯.../` | 论文结构、术语、图表风格参考 | 🟡 参考，不可直接照搬国赛规则到省赛 |
| **范文** | `cumcm-past-questions-master/` | 同上（仅 2012-2021，已有更新更全版本，优先用前者） | 🟢 备用，与前一项重复时以前者为准 |
| **模板** | `2026国赛最新模版（Word+LaTeX）/` | LaTeX 模板 `cumcmthesis.cls` + `example.tex` | 🟡 工具，需适配省赛要求（目录页、封面） |
| **参考书** | `math_model-main/` | 模型公式和算法参考（31 章） | 🟢 按需查阅 |
| **研究** | `Competition_Research/` | 备赛指南，其中赛题分析 ⚠️ 已过时，**仅供非赛题部分参考** | 🟢 使用前核对 AGENTS.md |

**引用纪律**：
- 国赛范文 ≠ 省赛规则：范文用于学习论文写法，不用于判断竞赛规则（如页数限制、提交格式以省赛章程 PDF 为准）
- `SD_Math_Modeling_Guide.md` 的赛题分析过期，实际赛题以 AGENTS.md 和 `2025年本科组真题/` 为准
- 解题时优先读赛题 PDF 原文，不依赖任何二手描述

## 工作原则

### 对 ARIS 的改造策略
- **不直接修改 ARIS 原始 skills** — 在 `skills-mathmodel/` 下新建数学建模专用 skill
- **复用 ARIS 的工具基础设施** — `tools/` 下的 fetcher、renderer、wiki 等直接调用
- **数学建模 skills 遵循 ARIS 的 SKILL.md 格式** — 保持兼容，可回馈上游
- **`paper-write` / `paper-plan` 章节结构适配**：
  - ARIS 的 `paper-write` 面向学术 ML 论文（Abstract → Introduction → Related Work → Method → Experiments → Conclusion），**不能直接用于竞赛论文**
  - 适配方式：在 `skills-mathmodel/` 下创建章节模板覆盖配置，将输出结构强制为：目录 → 摘要 → 问题重述 → 模型假设 → 符号说明 → 模型建立与求解 → 灵敏度分析 → 模型优缺点 → 参考文献 → 附录
  - 结合 `paper-reference` 提取的获奖范文结构骨架作为风格约束，注入摘要"黄金公式"（背景目标 20% + 核心建模 50% + 结果结论 30%）
  - `paper-plan` 的 venue 参数覆写为 `CUMCM`（全国大学生数学建模竞赛论文规范）

### 竞赛求解规范
- 每个赛题在 `src/` 下建独立子目录（如 `src/problem_a/`）
- 数据通过相对路径引用 `../../data/xxx.csv`
- 图表输出到 `output/figures/`，结果表输出到 `output/tables/`
- 脚本顶部加 docstring：题目编号、模型名称、求解方法
- 关键推导写在论文中，代码只需实现逻辑

### 论文规范
- 最终提交：论文 PDF + 程序代码（含注释）+ 结果数据
- 代码可复现：`pip install -r requirements.txt` 后能直接跑
- 参考 `docs/` 中的竞赛章程，注意查重和引用要求

## 改造计划

### 当前开发语境
第三届山东省赛已于 2026 年 5 月 24 日 20:00 结束。后续改造策略从赛前抢修切换为：
- **产品化基线**：稳定 FastAPI + Vue/Tauri 工具链，保证测试、构建和本地数据隔离可靠
- **复盘验证**：用已完成的 2026 省赛/往届赛题做端到端回放，定位自动化链路短板
- **能力补齐**：按风险优先级完善状态机、结构化输出、格式审查、数据采集和提交打包

### 总体策略
- **效果优先**：skills 的输出质量是首要目标，宁可多迭代几次也要保证建模合理、论文达标
- **成本控制**：主力建模和写作任务用 DeepSeek V4 Pro（能力强），格式检查和简单审稿用 MiMo V2.5/Pro（更便宜）
- **时间账**：竞赛只有 3 天，自动化流程必须在**数小时内**完成从读题到定稿，给人留足决策和调试时间

### Phase 1: 基础建设 — 核心 Skill 链 + LaTeX 模板
- **目标**：实现 `problem-decompose` → `model-select` → `code-template` 三个核心 skill
- **交付物**：
  - `skills-mathmodel/problem-decompose/SKILL.md`
  - `skills-mathmodel/model-select/SKILL.md`
  - `skills-mathmodel/code-template/SKILL.md`
  - `paper/template.tex`（符合竞赛格式的 LaTeX 模板）
  - `requirements.txt`（Python 依赖清单）
- **验证**：取一道往届赛题，能完成"读题 → 拆解 → 推荐模型 → 生成可运行的 Python 脚本"

### Phase 2: 完整链路验证 — 端到端跑通一道赛题
- **目标**：用现有的 ARIS skills + Phase 1 的三件套，完整求解一道往届赛题
- **流程**：
  1. `problem-decompose` 拆题
  2. `model-select` 选模型
  3. `code-template` 生成代码
  4. 运行代码，产出结果
  5. `paper-figure` + `figure-spec` + `mermaid-diagram` 生成全部图表
  6. **[人工] Gemini CLI 图片审查**（需切换网络）：逐张检查 `output/figures/` 下所有图表，审查维度：可读性（字号与正文 10pt 匹配）、色板（colorblind-safe）、三线表规范、标注完整性、中英文混排协调性，反馈后回修
  7. `paper-reference` 检索同题型获奖范文，提取结构/术语/图表风格（新增）
  8. `paper-write` + `paper-compile` 产出论文初稿（复用 ARIS，注入范文风格）
- **验证**：论文 PDF 通过格式自检，所有代码可复现运行

### Phase 3: 补齐工具链
- **目标**：实现 `data-preprocess`、`sensitivity-analysis`、`contest-format`
- **交付物**：
  - `skills-mathmodel/data-preprocess/SKILL.md`
  - `skills-mathmodel/sensitivity-analysis/SKILL.md`
  - `skills-mathmodel/contest-format/SKILL.md`
- **验证**：
  - `data-preprocess` 能处理缺失值、异常值、标准化
  - `sensitivity-analysis` 能生成参数扫描图和结论
  - `contest-format` 能检查论文是否符合全部格式要求

### Phase 4: 自动化闭合 — 一键提交
- **目标**：完整自动化：读题 → 全套求解 → 论文 → 自审 → 格式检查 → 打包
- **交付物**：
  - `skills-mathmodel/submit-pack/SKILL.md`
  - `src/pipeline.py`（一键流程编排脚本）
  - 适配后的 `auto-review-loop` 调用方式（使用 MiMo V2.5/Pro 审稿）
- **验证**：输入赛题 PDF，输出合格的论文 PDF + RAR 支撑材料，全程无人工干预
