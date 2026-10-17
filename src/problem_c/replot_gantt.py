import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIG_DIR = os.path.join(BASE_DIR, "output", "figures")
TAB_DIR = os.path.join(BASE_DIR, "output", "tables")

def clean_gantt_label(event, duration):
    name = event
    spot = None
    if "【" in name and "】" in name:
        spot = name.split("【")[1].split("】")[0]
        
    if "通勤" in name:
        if duration < 0.6:
            return "通勤"
        elif duration < 1.0:
            return f"往{spot}" if spot else "通勤"
        else:
            return f"通勤至{spot}" if spot else "通勤"
            
    if "游览" in name:
        if spot:
            return spot
        return name.split(" (")[0]
        
    if "返程" in name or "返回" in name:
        if "退房" in name:
            return "返程"
        if duration < 0.6:
            return "返程"
        elif duration < 1.0:
            return "回酒店"
        else:
            return "返回酒店"
            
    if "起床+早餐" in name or "起床" in name:
        return "整装" if duration < 1.8 else "起居整装"
        
    if "入住" in name:
        return "入住"
        
    if "退房" in name:
        return "退房"
        
    if "返程回家" in name or "自驾返程" in name:
        return "回程" if duration < 2.0 else "自驾回程"
        
    if "自驾前往" in name or "自驾去" in name:
        return "去程" if duration < 2.0 else "自驾去程"
        
    if "等待" in name:
        return "等待"
        
    txt = name.split("【")[-1].replace("】", "") if "【" in name else name
    txt = txt.split(" (")[0]
    return txt

def plot_gantt(timelines, name, key):
    plt.figure(figsize=(12, 6), dpi=300)
    for d in range(5):
        y_val = 5 - d
        for step in timelines[d]:
            start = step["start"]
            end = step["end"]
            duration = step["duration"]
            event = step["event"]
            
            # 使用学术期刊级柔和莫兰迪色系以提高对比度与美感
            if "通勤" in event or "返程" in event:
                color = "#b03a2e"  # 学术暗红
                hatch = "//"
            elif "游览" in event:
                color = "#196f3d"  # 典雅暗绿
                hatch = ""
            elif "等待" in event:
                color = "#b7950b"  # 暖沙黄色
                hatch = ".."
            else:
                color = "#1f618d"  # 经典暗蓝
                hatch = ""
                
            plt.barh(y_val, duration, left=start, color=color, edgecolor="black", height=0.5, hatch=hatch, alpha=0.85)
            
            # 引入动态标签排版引擎：根据物理宽度自适应缩放或隐藏，防止中文重叠
            txt = clean_gantt_label(event, duration)
            char_len = len(txt)
            needed_width = char_len * 0.14  # 每个中文字符需要的物理空间估算值（单位：小时）
            
            if duration >= 0.35:  # 允许短活动打标
                # 动态计算最适合的字号，避免溢出
                if duration < needed_width:
                    fs = 5.5  # 空间受限，采用微型字号
                    if duration < char_len * 0.08:
                        continue  # 空间极度狭小，隐藏文字以防止溢出和重叠
                else:
                    fs = 6.5 if duration < 0.8 else 8.0
                    
                text_color = "black" if "等待" in event else "white"
                plt.text(start + duration/2, y_val, txt, ha="center", va="center", fontsize=fs, color=text_color, fontweight="bold")
                
    plt.yticks(range(1, 6), [f"第 {5-i} 天" for i in range(5)], fontsize=11, fontweight="bold")
    plt.xticks(range(5, 23), [f"{h:02d}:00" for h in range(5, 23)], fontsize=10)
    plt.xlim(5.0, 22.0)
    plt.xlabel("时间轴 (24小时制)", fontsize=12, fontweight="bold")
    plt.grid(axis="x", linestyle="--", alpha=0.5)
    plt.tight_layout()
    fig_path = os.path.join(FIG_DIR, f"gantt_timeline_{key}.png")
    plt.savefig(fig_path, bbox_inches="tight")
    plt.close()
    print(f"成功重新生成 {name} 甘特图 -> {fig_path}")

def time_str_to_float(t_str):
    h, m = map(int, t_str.split(":"))
    return h + m / 60.0

def replot_all_gantts():
    keys = ["A", "B", "M", "C"]
    names = {
        "A": "深游打卡型 (A-tier)",
        "B": "轻松休闲型 (B-tier)",
        "M": "中等风险平衡型 (M-tier)",
        "C": "特种兵打卡型 (C-tier)"
    }
    
    for key in keys:
        csv_path = os.path.join(TAB_DIR, f"table_problem2_timeline_{key}.csv")
        if not os.path.exists(csv_path):
            print(f"错误：文件不存在 {csv_path}")
            continue
            
        df = pd.read_csv(csv_path)
        timelines = [[] for _ in range(5)]
        
        for _, row in df.iterrows():
            day_str = row["天数"]
            # Extract day number
            d_idx = int(day_str.replace("第", "").replace("天", "").strip()) - 1
            
            start = time_str_to_float(row["开始时间"])
            end = time_str_to_float(row["结束时间"])
            duration = float(row["持续时间(h)"])
            event = row["活动环节"]
            location = row["所处地点"]
            
            timelines[d_idx].append({
                "start": start,
                "end": end,
                "duration": duration,
                "event": event,
                "location": location
            })
            
        plot_gantt(timelines, names[key], key)

if __name__ == "__main__":
    replot_all_gantts()
