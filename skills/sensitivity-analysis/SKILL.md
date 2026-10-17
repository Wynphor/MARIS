---
name: sensitivity-analysis
description: "对数学建模求解结果进行敏感性分析。参数扫描、鲁棒性检验，输出图表和结论。"
argument-hint: "<求解脚本路径> [--params <参数列表>] [--ranges <扫描范围>]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# Sensitivity Analysis: 敏感性分析

对模型求解结果进行灵敏度检验：**$ARGUMENTS**

## Constants

- **DRIVEN_MODEL = `deepseek-v4-pro`** — 计算密集型主力
- **REPORT_MODEL = `mimo-v2.5`** — 分析报告撰写（成本更低）
- **SCAN_RANGES = [-20%, -10%, 0, +10%, +20%]** — 默认参数扫描范围
- **OUTPUT_DIR = `output/figures/`** — 图表输出

## Inputs

1. 求解脚本路径（来自 `code-template` 产出）
2. 可选：敏感参数列表（`--params`）
3. 可选：扫描范围（`--ranges`），默认 ±20%

## Outputs

输出 `sensitivity_report.md`：

```markdown
# 敏感性分析报告

## 敏感参数识别

| 参数 | 基准值 | 扫描范围 | 目标值变化幅度 | 敏感度评级 |
|------|--------|---------|---------------|-----------|
| α    | 0.5    | ±20%    | ±3.2%        | 低敏感    |
| β    | 2.0    | ±20%    | ±18.7%       | 高敏感 ⚠️ |

## 参数扫描结果

- 每个敏感参数生成一条"参数值 vs 目标值"曲线图
- 标注基准方案的参考线

## 模型鲁棒性结论

- 模型对 α 不敏感（变化幅度 < 5%）：假设的微小偏差不影响结论
- 模型对 β 高度敏感（变化幅度 > 15%）：该参数的精度至关重要，建议在论文中重点讨论其取值依据
```

## Workflow

### Step 1: 识别敏感参数

从求解脚本中提取关键参数：
1. 模型假设中声明的参数（如弹性系数、衰减率、权重）
2. 数据预处理中引入的参数（如标准化方式、填充值）
3. 对每个参数，判断它是否可能影响结论方向

### Step 2: 设计扫描方案

对每个参数：
1. 以基准值为中心，按 SCAN_RANGES 生成扫描点
2. 考虑参数间的交互（两个高敏感参数需做双因子扫描）
3. 每个扫描点重新运行求解脚本并记录目标值

### Step 3: 逐参数扫描

通用扫描框架：

```python
def scan_param(script_path, param_name, base_val, scan_range, target_func):
    results = []
    for pct in [-0.2, -0.1, 0, 0.1, 0.2]:
        val = base_val * (1 + pct)
        output = run_and_capture(script_path, {param_name: val})
        target = target_func(output)
        results.append((val, target))
    return results
```

### Step 4: 生成扫描图

对每个参数：
1. 折线图：X=参数值，Y=目标值
2. 标注基准方案（虚线）
3. 标注 ±5% 和 ±10% 变化区间
4. 多个参数时生成多子图或多曲线叠加图

### Step 5: 撰写结论

- **敏感参数**：如果目标值变化 > 10%，标记为"高敏感"，建议在论文中重点讨论该参数取值依据
- **稳定参数**：如果目标值变化 < 5%，标记为"低敏感"，可作为模型鲁棒性的证据
- **交互效应**：如果两个参数存在协同影响，建议追加双因子分析

### Step 6: 自检

- 是否覆盖了所有关键假设参数？
- 扫描范围是否合理（默认 ±20%，可根据实际调整）？
- 高敏感参数的结论是否有充分的定性解释？
- 图表是否清晰标注了基准方案？
