# Auto-Review 数学建模竞赛适配：跨模型对抗审查闭环

## 适配目标

将 ARIS 的单向审查升级为**双模型对抗闭环**：
```
DeepSeek V4 Pro 写论文 → MiMo V2.5/Pro 审稿 → DeepSeek 反驳 → 修改 → 再审 → 收敛
```

## ARIS 原生能力复用

| 组件 | 位置 | 角色 |
|------|------|------|
| `auto-review-loop` | `skills/auto-review-loop/` | 多轮审查循环（V4 Pro + MiMo 驱动） |
| `auto-review-loop-llm` | `skills/auto-review-loop-llm/` | MiMo 适配入口 |
| `skills-codex-gemini-review/auto-review-loop` | 嵌套层 | Gemini 驱动高标准审查（人工切网触发） |
| `kill-argument` | `skills/kill-argument/` | 对抗性论点检验：MiMo 攻击 → V4 Pro 防御 |
| `auto-paper-improvement-loop` | `skills/auto-paper-improvement-loop/` | 自动审查→修改→编译迭代 |
| `paper-claim-audit` | `skills/paper-claim-audit/` | 验证论文声明是否有数据支持 |
| `citation-audit` | `skills/citation-audit/` | 验证参考文献真实性 |

## 竞赛审查标准（替换学术论文标准）

| 优先级 | 审查维度 | 权重 | 细分审核项 (重要) |
|--------|---------|------|-----------------|
| 1 | **假设的合理性** — 每条假设是否有依据？是否过强？ | 最高 | 评估所有模型假设是否具有微观经济学、物理学或工程合理背景支撑，杜绝无理假设。 |
| 2 | **建模的创造性与人性化认知** — 是否超出课本方法？是否结合背景创新？ | 高 | **人性化探索审查**：审核是否包含还原人类真实的“试错与探索链”（如 Baseline -> 线性回归失败 -> SVM 非线性核 -> 随机森林集成），严禁一气呵成、一步到位的纯公式堆积。 |
| 3 | **结果的正确性与定性深度** | 高 | **深度领域定性审查**：审核是否穿插了深刻的领域背景解释（如 Stiglitz-Weiss 信贷配给、发票交易伙伴与作废率法医风险、价格弹性溢价梯度等）。**数值审查**：摘要及正文结论必须含具体数值（禁止模棱两可的定性）。 |
| 4 | **文字表述与高品质图表设计** | 中 | **TikZ 矢量图表审查**：正文中必须包含至少两幅基于 LaTeX 原生 TikZ 宏包渲染的 publication-grade 架构流程图（系统信贷决策流、COVID 贝叶斯传染修正流）。严禁低分辨率截图或简陋 ASCII 字符。 |

## 三级审查流程

### 第一级：V4 Pro 自审（自动化）
```
paper-write 产出 → auto-review-loop (V4 Pro) → 修改 → 再审 → 问题数 ≤ 3
```

### 第二级：MiMo 交叉审查（自动化）
```
V4 Pro 自审通过 → auto-review-loop-llm (MiMo) 独立审查
→ V4 Pro 逐条接受/反驳 → MiMo 再审 → 争议项标记 [人工裁决]
```

### 第三级：Gemini CLI 终审（人工切网触发）
```
[人工] 切换网络 → skills-codex-gemini-review/auto-review-loop
→ Gemini 最高标准审查 + 图表/引用/身份信息额外检查
```

## 对抗性论点检验：kill-argument

```
MiMo 扮演"攻击者" → 逐条攻击论文核心论点
V4 Pro 扮演"防御者" → 逐条反驳并修补
输出：kill_argument_report.md（已修补 / 坚固 / 争议项）
```

## 自动改进循环

```
kill-argument 完成后 → auto-paper-improvement-loop
→ 修改 → paper-compile → contest-format 检查 → 迭代 2 轮
```

## 完整时序

```
[1] V4 Pro 自审 → [2] MiMo 交叉审查 → [3] kill-argument 对抗
→ [4] paper-claim-audit + citation-audit
→ [5] [人工] Gemini CLI 终审 → [6] auto-paper-improvement-loop → 定稿
```

## 审稿反馈回流闭环（新增）

每轮审稿后必须执行以下回流：

1. 审稿输出问题列表 → 逐条标注严重度（P0强制/P1建议/P2可选）
2. V4 Pro 逐条处理：接受→修改论文 / 反驳→写理由 / 妥协→部分修改
3. 修改后的论文再送审（同一审稿模型）→ 检查问题是否已解决
4. 最多迭代 3 轮。第 3 轮后仍有未解决的 P0 项标记 [人工裁决]
5. 最终输出 `review_closure_report.md`：已解决 N 项 / 人工裁决 M 项

审稿不能是"打完分就结束"的单向动作。不回流不闭环。