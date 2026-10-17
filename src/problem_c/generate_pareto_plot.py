# -*- coding: utf-8 -*-
"""
生成 Pareto Frontier 权衡分析图并保存
"""
import os
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# 设置画图风格
sns.set_theme(style="ticks")

import matplotlib.font_manager as fm
msyh_path = r"C:\Windows\Fonts\msyh.ttc"
if os.path.exists(msyh_path):
    fm.fontManager.addfont(msyh_path)
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
else:
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIG_DIR = os.path.join(BASE_DIR, "output", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

# 方案数据（升级为莫兰迪学术配色）
schemes = {
    "B-tier (轻松休闲型)": {"preference": 31.61, "reliability": 98.95, "spots": 5, "color": "#196f3d", "marker": "o"},
    "A-tier (深游打卡型)": {"preference": 49.50, "reliability": 2.03, "spots": 6, "color": "#1f618d", "marker": "s"},
    "C-tier (特种兵打卡型)": {"preference": 42.11, "reliability": 0.17, "spots": 8, "color": "#b03a2e", "marker": "^"}
}

# 绘图
plt.figure(figsize=(8, 6), dpi=300)

# 精准错开各方案文字标注的偏移量，防止在 X 轴相近处产生任何文本重叠
xytext_map = {
    "B-tier (轻松休闲型)": (15, -15),
    "A-tier (深游打卡型)": (15, 15),
    "C-tier (特种兵打卡型)": (-145, 25)
}

for name, info in schemes.items():
    plt.scatter(info["preference"], info["reliability"], s=200, c=info["color"], 
                marker=info["marker"], label=name, edgecolors="black", linewidths=1.5, zorder=5)
    # 添加文字标注
    plt.annotate(
        f"{name}\n(满意度: {info['preference']:.2f}, 可靠度: {info['reliability']:.2f}%)",
        xy=(info["preference"], info["reliability"]),
        xytext=xytext_map[name],
        textcoords="offset points",
        fontsize=9.5,
        fontweight="bold",
        # 升级为高质感轻奢淡灰色背景框，彻底摒弃刺眼的荧光黄
        bbox=dict(boxstyle="round,pad=0.4", fc="#f8f9fa", alpha=0.9, ec="#bdc3c7", lw=0.8)
    )

# 绘制帕累托前沿示意虚线 (A-tier 和 B-tier 构成帕累托前沿，因为它们在各自的优势上无法被对方支配)
# C-tier 在可靠度和喜好度上均被 A-tier 支配 (A-tier 喜好度49.50 > 42.11 且可靠度 2.03% > 0.17%)，所以 C-tier 为非帕累托最优方案
x_pareto = [31.61, 49.50]
y_pareto = [98.95, 2.03]
plt.plot(x_pareto, y_pareto, linestyle="--", color="#ff7f0e", linewidth=2.5, label="Pareto 前沿曲线", zorder=3)

# 填充不可达区域和被支配区域
plt.fill_between(x_pareto, y_pareto, 105, color="#ff7f0e", alpha=0.05, label="Pareto 优越区 (不可达)")

plt.xlim(25, 55)
plt.ylim(-5, 105)
plt.xlabel("总喜好度满意度 (越大越优)", fontsize=12, fontweight="bold")
plt.ylabel("系统稳定性整体可靠度 (%) (越大越优)", fontsize=12, fontweight="bold")
# 去除硬编码标题，避免与 LaTeX caption 重合
plt.grid(True, linestyle=":", alpha=0.6)
plt.legend(loc="upper right", fontsize=10, frameon=True, shadow=True)

# 标出支配关系
plt.annotate(
    "A-tier 支配 C-tier\n(满意度和可靠度均占优)",
    xy=(42.11, 0.17),
    xytext=(30, 40),
    arrowprops=dict(facecolor="gray", shrink=0.08, width=1.5, headwidth=6, headlength=6),
    fontsize=9.5,
    fontstyle="italic"
)

plt.tight_layout()
output_path = os.path.join(FIG_DIR, "pareto_frontier_tradeoff.png")
plt.savefig(output_path, bbox_inches="tight")
print(f"[OK] Successfully generated and saved Pareto Frontier plot to: {output_path}")
