---
name: code-template
description: "根据选定模型生成可运行的 Python 求解脚本。包含 docstring、数据加载、模型构建、求解和结果输出。"
argument-hint: "<model_recommendation.md 路径> [--data <数据文件路径>]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# Code Template: 代码骨架生成

根据模型推荐生成可运行的 Python 脚本：**$ARGUMENTS**

## Constants

- **DRIVEN_MODEL = `deepseek-v4-pro`** — 代码生成主力
- **OUTPUT_DIR = `src/`** — 脚本输出目录
- **DATA_DIR = `data/`** — 数据目录（相对路径 `../../data/`）
- **FIG_DIR = `output/figures/`** — 图表输出目录
- **TABLE_DIR = `output/tables/`** — 结果表输出目录

## Inputs

1. `model_recommendation.md` — 来自 `model-select`（含 `research-refine` 细化后的方法计划）
2. 可选：数据文件路径（`--data` 参数）

## Outputs

输出 `src/problem_<题号>/` 下 Python 脚本，每个子问题至少 1 个主脚本 + 1 个对比实验脚本：

- 主脚本：数据加载→特征工程→首选模型训练→求解→结果输出
- **对比脚本（新增）**：≥3 种候选模型的横向对比 → 输出对比表和对比图
- **命令行参数支持**：关键假设和超参数（如模型系数、衰减率、权重等）**必须**通过 `argparse` 库定义为命令行参数（如 `--alpha`），以确保下游的 `sensitivity-analysis` 工具能够自动调用扫描。
- 每个脚本含 docstring、`if __name__ == "__main__"` 入口

## 模板库

按模型类型选择模板：

| 模型类型 | 模板 | 核心库 |
|---------|------|--------|
| 线性规划 (LP) | `lp_pulp.py.j2` | PuLP / scipy.optimize.linprog |
| 整数规划 (IP) | `ip_pulp.py.j2` | PuLP (CBC solver) |
| 非线性规划 (NLP) | `nlp_cvxpy.py.j2` | cvxpy |
| 多目标优化 | `multiobj_pyomo.py.j2` | Pyomo / NSGA-II (pymoo) |
| 微分方程 (ODE/PDE) | `ode_scipy.py.j2` | scipy.integrate |
| 回归分析 | `reg_sklearn.py.j2` | sklearn |
| 聚类/分类 | `cluster_sklearn.py.j2` | sklearn |
| 图论/网络 | `graph_networkx.py.j2` | networkx |
| 时间序列 | `ts_statsmodels.py.j2` | statsmodels / 自定义 |
| 图像增强 | `image_torch.py.j2` | PyTorch / OpenCV / skimage |
| 交通流建模 | `traffic_numpy.py.j2` | numpy (自定义数值模拟) |

## Workflow

### Step 1: 读取模型推荐

解析 `model_recommendation.md`，提取：
- 首选模型名称
- 模型假设
- 求解算法
- 推荐库

### Step 2: 选择模板

根据模型类型匹配模板库中的对应模板。
- **ARIS 调用**: `experiment-plan` 先规划参数矩阵、求解方案和计算预算，确保代码覆盖所有关键参数组合

### Step 3: 检测数据

- 若用户提供了 `--data` 参数，读取数据文件的前 30 行确定字段结构
- 若未提供，生成数据加载框架代码（占位 + TODO 注释）

### Step 4: 生成脚本

生成完整的 Python 脚本，包含：

1. **文件头 docstring**: 题目编号、子问题、模型名称、求解方法
2. **导入**: 仅导入模板需要的库
3. **数据加载**: 从 `data/` 相对路径读取，含异常处理（文件不存在、编码错误）
4. **数据预处理**: 缺失值检查 + 标准化（若模板需要）
5. **模型构建**: 决策变量定义、目标函数、约束条件
6. **求解**: 调用对应库的 solve 方法
7. **结果输出**: print 摘要 + 保存到 `output/`
8. **可视化**（若模板支持）: matplotlib/seaborn 生成图表
- **ARIS 调用**: `experiment-bridge` 桥接 idea→代码实现，确保实验方案正确映射到脚本结构；生成完毕后调用 `run-experiment` 管理脚本执行和结果追踪

### Step 5: 自检

- 脚本顶部 docstring 是否包含题目编号和模型信息？
- 数据加载路径是否正确（相对路径 `data/`）？
- 是否包含 `if __name__ == "__main__"` 入口？
- 是否添加了必要的注释说明关键步骤？

### Step 6: 大文件写入规范（新增）

当单文件 > 5KB 时**禁止一次性 write_file**，必须分批：

1. 首块 ≤4KB：文件头 + 核心结构
2. 后续块 ≤4KB：用 edit_file 逐块追加
3. 每块写入后立即编译检查，确保无语法错误