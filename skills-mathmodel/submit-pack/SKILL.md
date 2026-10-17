---
name: submit-pack
description: "打包数学建模竞赛提交物：论文PDF + 源代码 + 数据 → 符合规范的 RAR 支撑材料包（≤20MB）。"
argument-hint: "<论文PDF路径> [--src <源码目录>] [--data <数据目录>]"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# Submit Pack: 提交物打包

打包竞赛提交物为规范的 RAR 支撑材料：**$ARGUMENTS**

## Constants

- **DRIVEN_MODEL = `none`** — 纯脚本工具，无需 LLM
- **MAX_SIZE_MB = 20** — 支撑材料上限
- **OUTPUT_FILE = `支撑材料_<题号>.rar`** — 最终提交包

## Inputs

1. 论文 PDF 路径
2. 源码目录（默认 `src/`）
3. 数据目录（默认 `data/`）
4. 可选：额外参考资料

## Outputs

1. **支撑材料 RAR**（≤ 20MB）
2. **提交检查清单** `submission_checklist.md`

## 提交物要求（山东省赛）

根据 `docs/` 下的章程和参赛规则：

| 项目 | 格式 | 要求 |
|------|------|------|
| 论文 | PDF | 电子版，不含身份信息 |
| 源程序 | 文件夹 | 所有求解代码，含注释 |
| 数据 | 文件夹 | 预处理后数据（赛题原始数据除外） |
| 中间结果 | 文件夹 | 图表、结果表 |
| 参考资料 | 文件夹 | 引用的文献和参考材料 |

**不含**：赛题提供的原始数据文件

## 提交前检查清单

```markdown
# 提交检查清单

## 论文
- [ ] 论文 PDF 已生成，可正常打开
- [ ] 封面已插入（pdfpages）
- [ ] 目录在第 1 页
- [ ] 摘要单独一页
- [ ] 正文 ≤ 20 页
- [ ] 正文和附录无身份信息
- [ ] 参考文献按 [1][2] 标注

## 源代码
- [ ] 所有脚本可复现运行（pip install -r requirements.txt 后）
- [ ] 每个脚本顶部有 docstring（题目编号、模型、方法）
- [ ] 不含赛题原始数据

## 支撑材料
- [ ] 总大小 ≤ 20MB
- [ ] 不含 .git/、__pycache__/ 等冗余文件
- [ ] 文件命名清晰，无乱码

## 最终确认
- [ ] 论文和支撑材料均已上传官方系统
```

## Workflow

### Step 1: 收集文件

```python
collect_paths = {
    "论文.pdf": args.paper_pdf,
    "src/": args.src_dir or "src/",
    "data/processed/": "data/processed/",
    "output/figures/": "output/figures/",
    "output/tables/": "output/tables/",
}
```

### Step 2: 清理冗余

自动排除：
- `__pycache__/`、`*.pyc`
- `.git/`、`.gitignore`
- `*.log`、`*.aux`、`*.out`（LaTeX 编译中间文件）
- 赛题原始数据（`data/` 下未经处理的原始文件）

### Step 3: 大小检查

如果超过 20MB：
1. 压缩超大图片（>1MB 的 PNG 转 JPEG）
2. 移除未使用的数据文件
3. 提示用户手动清理

### Step 4: 打包

```bash
# Windows (WinRAR)
rar a -r "支撑材料_<题号>.rar" temp_pack/*

# 跨平台 Python 方案
python -c "import shutil; shutil.make_archive('支撑材料', 'zip', 'temp_pack')"
```

### Step 5: 输出检查清单

生成 `submission_checklist.md`，逐项打勾确认。

### Step 6: 自检

- [ ] RAR 能否正常解压？
- [ ] 解压后目录结构是否清晰？
- [ ] 论文 PDF 是否在根目录？
- [ ] 是否误包含赛题原始数据？
