"""
MathModel-Engine CLI — 数学建模竞赛命令行工具

直接调用后端服务，无需启动 HTTP 服务器。

Usage:
    python -m cli.init <title>                  # 创建工作区
    python -m cli.status                        # 查看状态
    python -m cli.decompose problem.pdf         # 赛题拆解
    python -m cli.model-select                  # 模型推荐
    python -m cli.code-gen                      # 代码生成
    python -m cli.write                         # 论文写作
    python -m cli.review --rounds 2             # 对抗审查
    python -m cli.compile                       # LaTeX 编译
    python -m cli.pack                          # 打包提交
    python -m cli.run-all                       # 一键全流程
    python -m cli.data data.csv                 # 数据探索
    python -m cli.chat                          # 交互式对话

Or install as command:
    pip install -e .
    mathmodel init "自驾行程规划"
    mathmodel decompose problem.pdf
"""
import sys
import os

# Ensure backend/app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
