# -*- coding: utf-8 -*-
"""
模型名称: 基于熵权TOPSIS-GRA与精确时窗运筹规划的自驾景点优选与随机动力学仿真模型
求解方法: 熵权 TOPSIS-GRA 联合评价 、 地理连通性拓扑图论 、 预计算候选日不相交回溯剪枝路径优化 、 蒙特卡洛随机动力学仿真 、 方差贡献率分析
"""

import os
import json
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx
from itertools import combinations, permutations

# 强制标准输出和错误流为 UTF-8 编码，防止 Windows 控制台因 GBK 导致 Unicode 字符崩溃
import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# 设置画图风格
sns.set_theme(style="ticks")
import matplotlib.font_manager as fm
# 优先使用 Windows 自带的微软雅黑，确保中文渲染无警告
msyh_path = r"C:\Windows\Fonts\msyh.ttc"
if os.path.exists(msyh_path):
    fm.fontManager.addfont(msyh_path)
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
else:
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['axes.unicode_minus'] = False

def clean_partition_label(part):
    """递归清洗景点分区标签，消除中括号、单引号等 Python 数据结构 debug 痕迹"""
    if isinstance(part, str):
        return part
    if hasattr(part, "__iter__"):
        items = []
        for x in part:
            if hasattr(x, "__iter__") and not isinstance(x, str):
                items.append(clean_partition_label(x))
            else:
                items.append(str(x))
        return "+".join(items)
    return str(part)

# 1. 基础路径配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(BASE_DIR, "data", "c_data.json")
FIG_DIR = os.path.join(BASE_DIR, "output", "figures")
TAB_DIR = os.path.join(BASE_DIR, "output", "tables")

os.makedirs(FIG_DIR, exist_ok=True)
os.makedirs(TAB_DIR, exist_ok=True)

# 加载数据
with open(DATA_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

spots = data["spots"]
distances = data["distances"]

# 转换为方便操作的数据结构
spot_ids = list(spots.keys())
all_points = ["Hotel"] + spot_ids

# ----------------- MODULE 1: PROBLEM 1 景点综合评估与地理网络分析 -----------------

def get_peak_overlap(open_range):
    """计算营业时间与高峰时段的重叠小时数"""
    start, end = open_range
    # 道路高峰: 07:00-09:00, 11:00-13:00, 16:00-18:00
    road_peaks = [(7.0, 9.0), (11.0, 13.0), (16.0, 18.0)]
    # 排队高峰: 09:00-12:00
    queue_peaks = [(9.0, 12.0)]
    
    overlap = 0.0
    for p_start, p_end in road_peaks:
        o_start = max(start, p_start)
        o_end = min(end, p_end)
        if o_start < o_end:
            overlap += (o_end - o_start)
    for p_start, p_end in queue_peaks:
        o_start = max(start, p_start)
        o_end = min(end, p_end)
        if o_start < o_end:
            overlap += (o_end - o_start)
            
    return overlap

def solve_problem_1():
    print("\n--- 启动问题一：景点综合特征评估与联动分析 ---")
    
    rows = []
    for sid in spot_ids:
        spot = spots[sid]
        commutes = [distances[sid][other] for other in spot_ids if other != sid]
        avg_commute = np.mean(commutes)
        
        open_range = spot["open_time"]
        total_open = open_range[1] - open_range[0]
        overlap_hours = get_peak_overlap(open_range)
        sensitivity = overlap_hours / total_open
        
        rows.append({
            "景点编号": sid,
            "景点名称": spot["name"],
            "游览耗时": spot["comfort_stay"],
            "通勤距离": avg_commute,
            "拥堵敏感度": sensitivity,
            "喜好度": spot["score"]
        })
        
    df_x = pd.DataFrame(rows)
    X = df_x[["游览耗时", "通勤距离", "拥堵敏感度", "喜好度"]].values
    n, m = X.shape
    
    # 极值标准化
    X_norm = np.zeros_like(X)
    X_norm[:, 0] = (X[:, 0] - X[:, 0].min()) / (X[:, 0].max() - X[:, 0].min())
    X_norm[:, 1] = (X[:, 1].max() - X[:, 1]) / (X[:, 1].max() - X[:, 1].min())
    X_norm[:, 2] = (X[:, 2].max() - X[:, 2]) / (X[:, 2].max() - X[:, 2].min())
    X_norm[:, 3] = (X[:, 3] - X[:, 3].min()) / (X[:, 3].max() - X[:, 3].min())
    
    # 熵权法计算权重
    p = X_norm / np.sum(X_norm, axis=0)
    e = - (1.0 / np.log(n)) * np.sum(p * np.log(p + 1e-12), axis=0)
    d = 1.0 - e
    w = d / np.sum(d)
    
    print(f"熵权法计算出的各指标客观权重:\n 游览耗时: {w[0]:.4f}, 通勤距离: {w[1]:.4f}, 拥堵敏感度: {w[2]:.4f}, 喜好度: {w[3]:.4f}")
    
    # TOPSIS 评分
    V = X_norm * w
    V_plus = np.max(V, axis=0)
    V_minus = np.min(V, axis=0)
    D_plus = np.sqrt(np.sum((V - V_plus)**2, axis=1))
    D_minus = np.sqrt(np.sum((V - V_minus)**2, axis=1))
    C = D_minus / (D_plus + D_minus)
    
    # 灰色关联度 (GRA) 评分
    rho = 0.5
    delta = np.abs(X_norm - np.max(X_norm, axis=0))
    grc = (np.min(delta) + rho * np.max(delta)) / (delta + rho * np.max(delta))
    w_grg = np.sum(grc * w, axis=1)
    
    # 联合评价评分 (TOPSIS 贴近度 + 加权关联度 1:1 结合)
    joint_score = 0.5 * C + 0.5 * w_grg
    
    df_x["TOPSIS贴近度"] = C
    df_x["灰色关联度"] = w_grg
    df_x["综合优先级评分"] = joint_score
    df_x["综合排名"] = df_x["综合优先级评分"].rank(ascending=False).astype(int)
    df_x["优先级"] = df_x["综合排名"].apply(lambda r: "高" if r <= 5 else "低")
    df_x = df_x.sort_values(by="综合排名")
    
    # 输出表格
    table_p1_path = os.path.join(TAB_DIR, "table_problem1_evaluation.csv")
    df_x.to_csv(table_p1_path, index=False, encoding='utf-8-sig')
    print(f"问题一评价结果已写入表格: {table_p1_path}")
    print(df_x[["景点编号", "景点名称", "综合优先级评分", "综合排名", "优先级"]].to_string(index=False))
    
    # 地理网络与联动组合挖掘
    link_threshold = 0.4
    linkages = []
    G = nx.Graph()
    G.add_node("Hotel", type="Hotel", label="酒店")
    for sid in spot_ids:
        G.add_node(sid, type="Spot", name=spots[sid]["name"], score=df_x.loc[df_x["景点编号"]==sid, "综合优先级评分"].values[0])
        
    for i in range(len(all_points)):
        for j in range(i + 1, len(all_points)):
            u, v = all_points[i], all_points[j]
            dist = distances[u][v]
            if dist <= link_threshold:
                G.add_edge(u, v, weight=dist)
                if u != "Hotel" and v != "Hotel":
                    linkages.append((u, spots[u]["name"], v, spots[v]["name"], dist))
                    
    # 绘制地理网络图
    plt.figure(figsize=(10, 8), dpi=300)
    pos = nx.spring_layout(G, seed=42, k=1.5)
    
    node_colors = []
    node_sizes = []
    labels = {}
    for node in G.nodes():
        if node == "Hotel":
            node_colors.append("#1f77b4")
            node_sizes.append(1000)
            labels[node] = "酒店"
        else:
            score = G.nodes[node]["score"]
            node_colors.append(plt.cm.OrRd(0.3 + 0.7 * score))
            node_sizes.append(600 + 400 * score)
            labels[node] = f"{node}\n{G.nodes[node]['name']}"
            
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes, edgecolors="gray", linewidths=1.5)
    
    hotel_edges = [(u, v) for u, v in G.edges() if u == "Hotel" or v == "Hotel"]
    spot_edges = [(u, v) for u, v in G.edges() if u != "Hotel" and v != "Hotel"]
    
    nx.draw_networkx_edges(G, pos, edgelist=hotel_edges, width=1.5, edge_color="gray", style="dashed")
    nx.draw_networkx_edges(G, pos, edgelist=spot_edges, width=3.0, edge_color="#2ca02c")
    
    # 标签微调向上偏移，避免与着色节点重叠以提高对比度和可读性
    pos_labels = {node: (coords[0], coords[1] + 0.07) for node, coords in pos.items()}
    nx.draw_networkx_labels(G, pos_labels, labels=labels, font_size=9, font_weight="bold")
    
    plt.axis("off")
    plt.tight_layout()
    fig_network_path = os.path.join(FIG_DIR, "spot_linkage_network.png")
    plt.savefig(fig_network_path, bbox_inches="tight")
    plt.close()
    
    df_link = pd.DataFrame(linkages, columns=["起点编号", "起点名称", "终点编号", "终点名称", "车程(h)"])
    df_link = df_link.sort_values(by="车程(h)")
    table_link_path = os.path.join(TAB_DIR, "table_problem1_linkages.csv")
    df_link.to_csv(table_link_path, index=False, encoding='utf-8-sig')
    print("挖掘出的黄金联动景点组合:")
    print(df_link.to_string(index=False))
    
    return df_x

# ----------------- MODULE 2: PROBLEM 2 无扰动行程精确运筹求解器 -----------------

def check_day_schedule(spots_list, stay_type, day_num=2, start_hour=8.0):
    timeline = []
    driving_time = 0.0
    
    if day_num == 1:
        # 第一天从居住地自驾前往市区酒店 (4.0 小时)
        # 7:00出发，11:00到达酒店，然后办理入住手续0.5小时，11:30开始出游
        curr_time = 7.0
        timeline.append({
            "event": "从居住地自驾前往市区酒店",
            "start": curr_time,
            "end": curr_time + 4.0,
            "duration": 4.0,
            "location": "家 -> 酒店"
        })
        curr_time += 4.0
        driving_time += 4.0
        
        timeline.append({
            "event": "办理市区酒店入住手续",
            "start": curr_time,
            "end": curr_time + 0.5,
            "duration": 0.5,
            "location": "酒店"
        })
        curr_time += 0.5
        
        # 从酒店出发前往第一个景点
        s1 = spots_list[0]
        drive_1 = distances["Hotel"][s1]
        t_arr_1 = curr_time + drive_1
        
        open_1, close_1 = spots[s1]["open_time"]
        t_wait_1 = 0.0
        if t_arr_1 < open_1:
            t_wait_1 = open_1 - t_arr_1
            t_arr_1 = open_1
            
        timeline.append({
            "event": f"通勤前往【{spots[s1]['name']}】",
            "start": curr_time,
            "end": t_arr_1 - t_wait_1,
            "duration": drive_1,
            "location": f"Hotel -> {s1}"
        })
        if t_wait_1 > 0.0:
            timeline.append({
                "event": "等待景区开放",
                "start": t_arr_1 - t_wait_1,
                "end": t_arr_1,
                "duration": t_wait_1,
                "location": s1
            })
            
        if stay_type == 'comfort':
            stay_1 = spots[s1]["comfort_stay"]
        elif stay_type == 'min':
            stay_1 = spots[s1]["min_stay"]
        else:
            stay_1 = 0.5 * (spots[s1]["min_stay"] + spots[s1]["comfort_stay"])
            
        t_dep_1 = t_arr_1 + stay_1
        
        # 午餐时间注入
        spans_lunch_1 = (t_arr_1 < 13.0 and t_dep_1 > 11.5)
        lunch_added_1 = 0.0
        if spans_lunch_1:
            lunch_added_1 = 1.0
            t_dep_1 += 1.0
            
        if t_dep_1 > close_1:
            return False, None, 0.0
            
        timeline.append({
            "event": f"游览【{spots[s1]['name']}】" + (" (包含午餐1h)" if spans_lunch_1 else ""),
            "start": t_arr_1,
            "end": t_dep_1,
            "duration": stay_1 + lunch_added_1,
            "location": s1
        })
        
        curr_time = t_dep_1
        driving_time += drive_1
        dest = s1
        
        # 如果有第二个景点
        if len(spots_list) == 2:
            s2 = spots_list[1]
            drive_2 = distances[s1][s2]
            t_arr_2 = curr_time + drive_2
            
            open_2, close_2 = spots[s2]["open_time"]
            t_wait_2 = 0.0
            if t_arr_2 < open_2:
                t_wait_2 = open_2 - t_arr_2
                t_arr_2 = open_2
                
            timeline.append({
                "event": f"跨景点通勤前往【{spots[s2]['name']}】",
                "start": curr_time,
                "end": t_arr_2 - t_wait_2,
                "duration": drive_2,
                "location": f"{s1} -> {s2}"
            })
            if t_wait_2 > 0.0:
                timeline.append({
                    "event": "等待景区开放",
                    "start": t_arr_2 - t_wait_2,
                    "end": t_arr_2,
                    "duration": t_wait_2,
                    "location": s2
                })
                
            if stay_type == 'comfort':
                stay_2 = spots[s2]["comfort_stay"]
            elif stay_type == 'min':
                stay_2 = spots[s2]["min_stay"]
            else:
                stay_2 = 0.5 * (spots[s2]["min_stay"] + spots[s2]["comfort_stay"])
                
            t_dep_2 = t_arr_2 + stay_2
            
            spans_lunch_2 = (not spans_lunch_1) and (t_arr_2 < 13.0 and t_dep_2 > 11.5)
            lunch_added_2 = 0.0
            if spans_lunch_2:
                lunch_added_2 = 1.0
                t_dep_2 += 1.0
                
            if t_dep_2 > close_2:
                return False, None, 0.0
                
            timeline.append({
                "event": f"游览【{spots[s2]['name']}】" + (" (包含午餐1h)" if spans_lunch_2 else ""),
                "start": t_arr_2,
                "end": t_dep_2,
                "duration": stay_2 + lunch_added_2,
                "location": s2
            })
            curr_time = t_dep_2
            driving_time += drive_2
            dest = s2
            
        # 返回市区酒店
        drive_back = distances[dest]["Hotel"]
        t_end = curr_time + drive_back
        
        if t_end > 21.0:
            return False, None, 0.0
            
        timeline.append({
            "event": "返程回市区酒店",
            "start": curr_time,
            "end": t_end,
            "duration": drive_back,
            "location": f"{dest} -> Hotel"
        })
        
        driving_time += drive_back
        
        return True, timeline, driving_time
        
    elif day_num == 5:
        # 第五天从酒店出发，进行游览，最后办理退房手续0.5小时，自驾返程回家4.0小时
        curr_time = start_hour
        
        # 1. 起床整装
        t_wake = start_hour - 1.5
        timeline.append({
            "event": "起床+早餐+出行整装",
            "start": t_wake,
            "end": start_hour,
            "duration": 1.5,
            "location": "酒店"
        })
        
        # 2. 从酒店出发至第一个景点
        s1 = spots_list[0]
        drive_1 = distances["Hotel"][s1]
        t_arr_1 = curr_time + drive_1
        
        open_1, close_1 = spots[s1]["open_time"]
        t_wait_1 = 0.0
        if t_arr_1 < open_1:
            t_wait_1 = open_1 - t_arr_1
            t_arr_1 = open_1
            
        timeline.append({
            "event": f"通勤前往【{spots[s1]['name']}】",
            "start": curr_time,
            "end": t_arr_1 - t_wait_1,
            "duration": drive_1,
            "location": f"Hotel -> {s1}"
        })
        if t_wait_1 > 0.0:
            timeline.append({
                "event": "等待景区开放",
                "start": t_arr_1 - t_wait_1,
                "end": t_arr_1,
                "duration": t_wait_1,
                "location": s1
            })
            
        if stay_type == 'comfort':
            stay_1 = spots[s1]["comfort_stay"]
        elif stay_type == 'min':
            stay_1 = spots[s1]["min_stay"]
        else:
            stay_1 = 0.5 * (spots[s1]["min_stay"] + spots[s1]["comfort_stay"])
            
        t_dep_1 = t_arr_1 + stay_1
        
        spans_lunch_1 = (t_arr_1 < 13.0 and t_dep_1 > 11.5)
        lunch_added_1 = 0.0
        if spans_lunch_1:
            lunch_added_1 = 1.0
            t_dep_1 += 1.0
            
        if t_dep_1 > close_1:
            return False, None, 0.0
            
        timeline.append({
            "event": f"游览【{spots[s1]['name']}】" + (" (包含午餐1h)" if spans_lunch_1 else ""),
            "start": t_arr_1,
            "end": t_dep_1,
            "duration": stay_1 + lunch_added_1,
            "location": s1
        })
        
        curr_time = t_dep_1
        driving_time += drive_1
        dest = s1
        
        # 如果有第二个景点
        if len(spots_list) == 2:
            s2 = spots_list[1]
            drive_2 = distances[s1][s2]
            t_arr_2 = curr_time + drive_2
            
            open_2, close_2 = spots[s2]["open_time"]
            t_wait_2 = 0.0
            if t_arr_2 < open_2:
                t_wait_2 = open_2 - t_arr_2
                t_arr_2 = open_2
                
            timeline.append({
                "event": f"跨景点通勤前往【{spots[s2]['name']}】",
                "start": curr_time,
                "end": t_arr_2 - t_wait_2,
                "duration": drive_2,
                "location": f"{s1} -> {s2}"
            })
            if t_wait_2 > 0.0:
                timeline.append({
                    "event": "等待景区开放",
                    "start": t_arr_2 - t_wait_2,
                    "end": t_arr_2,
                    "duration": t_wait_2,
                    "location": s2
                })
                
            if stay_type == 'comfort':
                stay_2 = spots[s2]["comfort_stay"]
            elif stay_type == 'min':
                stay_2 = spots[s2]["min_stay"]
            else:
                stay_2 = 0.5 * (spots[s2]["min_stay"] + spots[s2]["comfort_stay"])
                
            t_dep_2 = t_arr_2 + stay_2
            
            spans_lunch_2 = (not spans_lunch_1) and (t_arr_2 < 13.0 and t_dep_2 > 11.5)
            lunch_added_2 = 0.0
            if spans_lunch_2:
                lunch_added_2 = 1.0
                t_dep_2 += 1.0
                
            if t_dep_2 > close_2:
                return False, None, 0.0
                
            timeline.append({
                "event": f"游览【{spots[s2]['name']}】" + (" (包含午餐1h)" if spans_lunch_2 else ""),
                "start": t_arr_2,
                "end": t_dep_2,
                "duration": stay_2 + lunch_added_2,
                "location": s2
            })
            curr_time = t_dep_2
            driving_time += drive_2
            dest = s2
            
        # 返回市区酒店
        drive_back = distances[dest]["Hotel"]
        t_ret_hotel = curr_time + drive_back
        timeline.append({
            "event": "返回酒店办理退房",
            "start": curr_time,
            "end": t_ret_hotel,
            "duration": drive_back,
            "location": f"{dest} -> Hotel"
        })
        curr_time = t_ret_hotel
        driving_time += drive_back
        
        # 酒店退房手续办理0.5小时
        timeline.append({
            "event": "办理酒店退房手续",
            "start": curr_time,
            "end": curr_time + 0.5,
            "duration": 0.5,
            "location": "酒店"
        })
        curr_time += 0.5
        
        # 酒店返程回家自驾车程 (4.0 小时)
        timeline.append({
            "event": "自驾从市区酒店返程回家",
            "start": curr_time,
            "end": curr_time + 4.0,
            "duration": 4.0,
            "location": "酒店 -> 家"
        })
        curr_time += 4.0
        driving_time += 4.0
        
        if curr_time > 21.0:
            return False, None, 0.0
            
        return True, timeline, driving_time
        
    else:
        # 标准天 (2, 3, 4)
        timeline = []
        curr_time = start_hour
        
        # 1. 起床整装
        t_wake = start_hour - 1.5
        timeline.append({
            "event": "起床+早餐+出行整装",
            "start": t_wake,
            "end": start_hour,
            "duration": 1.5,
            "location": "酒店"
        })
        
        # 2. 从酒店出发到第一个景点
        s1 = spots_list[0]
        drive_1 = distances["Hotel"][s1]
        t_arr_1 = curr_time + drive_1
        
        open_1, close_1 = spots[s1]["open_time"]
        t_wait_1 = 0.0
        if t_arr_1 < open_1:
            t_wait_1 = open_1 - t_arr_1
            t_arr_1 = open_1
            
        timeline.append({
            "event": f"通勤前往【{spots[s1]['name']}】",
            "start": curr_time,
            "end": t_arr_1 - t_wait_1,
            "duration": drive_1,
            "location": f"Hotel -> {s1}"
        })
        if t_wait_1 > 0.0:
            timeline.append({
                "event": "等待景区开放",
                "start": t_arr_1 - t_wait_1,
                "end": t_arr_1,
                "duration": t_wait_1,
                "location": s1
            })
            
        if stay_type == 'comfort':
            stay_1 = spots[s1]["comfort_stay"]
        elif stay_type == 'min':
            stay_1 = spots[s1]["min_stay"]
        else:
            stay_1 = 0.5 * (spots[s1]["min_stay"] + spots[s1]["comfort_stay"])
            
        t_dep_1 = t_arr_1 + stay_1
        
        # 午餐时间注入
        spans_lunch_1 = (t_arr_1 < 13.0 and t_dep_1 > 11.5)
        lunch_added_1 = 0.0
        if spans_lunch_1:
            lunch_added_1 = 1.0
            t_dep_1 += 1.0
            
        if t_dep_1 > close_1:
            return False, None, 0.0
            
        timeline.append({
            "event": f"游览【{spots[s1]['name']}】" + (" (包含午餐1h)" if spans_lunch_1 else ""),
            "start": t_arr_1,
            "end": t_dep_1,
            "duration": stay_1 + lunch_added_1,
            "location": s1
        })
        
        curr_time = t_dep_1
        driving_time = drive_1
        
        # 3. 如果有第二个景点
        if len(spots_list) == 2:
            s2 = spots_list[1]
            drive_2 = distances[s1][s2]
            t_arr_2 = curr_time + drive_2
            
            open_2, close_2 = spots[s2]["open_time"]
            t_wait_2 = 0.0
            if t_arr_2 < open_2:
                t_wait_2 = open_2 - t_arr_2
                t_arr_2 = open_2
                
            timeline.append({
                "event": f"跨景点通勤前往【{spots[s2]['name']}】",
                "start": curr_time,
                "end": t_arr_2 - t_wait_2,
                "duration": drive_2,
                "location": f"{s1} -> {s2}"
            })
            if t_wait_2 > 0.0:
                timeline.append({
                    "event": "等待景区开放",
                    "start": t_arr_2 - t_wait_2,
                    "end": t_arr_2,
                    "duration": t_wait_2,
                    "location": s2
                })
                
            if stay_type == 'comfort':
                stay_2 = spots[s2]["comfort_stay"]
            elif stay_type == 'min':
                stay_2 = spots[s2]["min_stay"]
            else:
                stay_2 = 0.5 * (spots[s2]["min_stay"] + spots[s2]["comfort_stay"])
                
            t_dep_2 = t_arr_2 + stay_2
            
            spans_lunch_2 = (not spans_lunch_1) and (t_arr_2 < 13.0 and t_dep_2 > 11.5)
            lunch_added_2 = 0.0
            if spans_lunch_2:
                lunch_added_2 = 1.0
                t_dep_2 += 1.0
                
            if t_dep_2 > close_2:
                return False, None, 0.0
                
            timeline.append({
                "event": f"游览【{spots[s2]['name']}】" + (" (包含午餐1h)" if spans_lunch_2 else ""),
                "start": t_arr_2,
                "end": t_dep_2,
                "duration": stay_2 + lunch_added_2,
                "location": s2
            })
            curr_time = t_dep_2
            driving_time += drive_2
            dest = s2
        else:
            dest = s1
            
        # 4. 返回酒店
        drive_back = distances[dest]["Hotel"]
        t_end = curr_time + drive_back
        
        if t_end > 21.0:
            return False, None, 0.0
            
        timeline.append({
            "event": "返程回市区酒店",
            "start": curr_time,
            "end": t_end,
            "duration": drive_back,
            "location": f"{dest} -> Hotel"
        })
        
        driving_time += drive_back
        
        return True, timeline, driving_time

# 预计算单日候选行程
def precompute_candidate_days(stay_type, day_num=2, start_hour=8.0):
    candidates = []
    # 单景点日
    for sid in spot_ids:
        feasible, timeline, driving = check_day_schedule([sid], stay_type, day_num, start_hour)
        if feasible:
            if day_num == 1:
                active_h = timeline[-1]["end"] - 10.0
            elif day_num == 5:
                active_h = timeline[-3]["end"] - 6.5
            else:
                active_h = timeline[-1]["end"] - timeline[0]["start"]
            s_data = spots[sid]
            actual_stay = s_data["comfort_stay"] if stay_type == 'comfort' else (s_data["min_stay"] if stay_type == 'min' else 0.5 * (s_data["min_stay"] + s_data["comfort_stay"]))
            satisfaction = s_data["score"] * (actual_stay / s_data["comfort_stay"])
            candidates.append({
                "spots": (sid,),
                "driving": driving,
                "satisfaction": satisfaction,
                "timeline": timeline,
                "active_hours": active_h
            })
    # 双景点日 (有序)
    for s1, s2 in permutations(spot_ids, 2):
        feasible, timeline, driving = check_day_schedule([s1, s2], stay_type, day_num, start_hour)
        if feasible:
            if day_num == 1:
                active_h = timeline[-1]["end"] - 10.0
            elif day_num == 5:
                active_h = timeline[-3]["end"] - 6.5
            else:
                active_h = timeline[-1]["end"] - timeline[0]["start"]
            sat = 0.0
            for sid in [s1, s2]:
                s_data = spots[sid]
                actual_stay = s_data["comfort_stay"] if stay_type == 'comfort' else (s_data["min_stay"] if stay_type == 'min' else 0.5 * (s_data["min_stay"] + s_data["comfort_stay"]))
                sat += s_data["score"] * (actual_stay / s_data["comfort_stay"])
            candidates.append({
                "spots": (s1, s2),
                "driving": driving,
                "satisfaction": sat,
                "timeline": timeline,
                "active_hours": active_h
            })
    return candidates

# 不相交回溯剪枝搜索
def search_itineraries(cands_by_day, day_idx, current_spots, current_cands, results, min_s, max_s):
    if day_idx == 5:
        num_spots = len(current_spots)
        if min_s <= num_spots <= max_s:
            sats = sum(c["satisfaction"] for c in current_cands)
            drivings = sum(c["driving"] for c in current_cands)
            actives = [c["active_hours"] for c in current_cands]
            balance_std = np.std(actives)
            metrics = {
                "satisfaction": sats,
                "driving_fatigue": drivings,
                "balance_std": balance_std,
                "daily_driving": [c["driving"] for c in current_cands],
                "daily_active_hours": actives,
                "num_spots": num_spots
            }
            partition = [list(c["spots"]) for c in current_cands]
            timelines = [c["timeline"] for c in current_cands]
            results.append((partition, metrics, timelines))
        return
        
    rem_days = 5 - day_idx
    if len(current_spots) + rem_days * 1 > max_s:
        return
        
    candidates = cands_by_day[day_idx]
    for cand in candidates:
        overlap = False
        for s in cand["spots"]:
            if s in current_spots:
                overlap = True
                break
        if overlap:
            continue
            
        new_spots = current_spots.copy()
        new_spots.update(cand["spots"])
        if len(new_spots) > max_s:
            continue
            
        search_itineraries(cands_by_day, day_idx + 1, new_spots, current_cands + [cand], results, min_s, max_s)

def solve_problem_2(df_p1):
    print("\n--- 启动问题二：无随机扰动下的多目标行程精确优化 ---")
    start_hour = 8.0
    
    # 偏好1: 深游打卡型 (A-tier) -> 5-6 景点, comfort 模式
    print("正在搜索【深游打卡型 (A-tier)】方案...")
    cands_a_d1 = precompute_candidate_days('comfort', 1, start_hour)
    cands_a_norm = precompute_candidate_days('comfort', 2, start_hour)
    cands_a_d5 = precompute_candidate_days('comfort', 5, start_hour)
    cands_a_by_day = [cands_a_d1, cands_a_norm, cands_a_norm, cands_a_norm, cands_a_d5]
    results_a = []
    search_itineraries(cands_a_by_day, 0, set(), [], results_a, 5, 6)
    results_a.sort(key=lambda x: (-x[1]["satisfaction"], x[1]["driving_fatigue"]))
    best_a = results_a[0] if len(results_a) > 0 else None
    
    # 偏好2: 轻松休闲型 (B-tier) -> 5 景点, mid 模式
    print("正在搜索【轻松休闲型 (B-tier)】与【中等风险平衡型 (M-tier)】方案...")
    cands_b_d1 = precompute_candidate_days('mid', 1, start_hour)
    cands_b_norm = precompute_candidate_days('mid', 2, start_hour)
    cands_b_d5 = precompute_candidate_days('mid', 5, start_hour)
    cands_b_by_day = [cands_b_d1, cands_b_norm, cands_b_norm, cands_b_norm, cands_b_d5]
    results_b = []
    search_itineraries(cands_b_by_day, 0, set(), [], results_b, 5, 6)
    
    results_b_5 = [x for x in results_b if x[1]["num_spots"] == 5]
    results_b_5.sort(key=lambda x: (x[1]["balance_std"], x[1]["driving_fatigue"]))
    best_b = results_b_5[0] if len(results_b_5) > 0 else None
    
    results_b_6 = [x for x in results_b if x[1]["num_spots"] == 6]
    results_b_6.sort(key=lambda x: (x[1]["balance_std"], x[1]["driving_fatigue"]))
    best_m = results_b_6[0] if len(results_b_6) > 0 else None
    
    # 偏好3: 特种兵打卡型 (C-tier) -> 7-8 景点, min 模式
    print("正在搜索【特种兵打卡型 (C-tier)】方案...")
    cands_c_d1 = precompute_candidate_days('min', 1, start_hour)
    cands_c_norm = precompute_candidate_days('min', 2, start_hour)
    cands_c_d5 = precompute_candidate_days('min', 5, start_hour)
    cands_c_by_day = [cands_c_d1, cands_c_norm, cands_c_norm, cands_c_norm, cands_c_d5]
    results_c = []
    search_itineraries(cands_c_by_day, 0, set(), [], results_c, 7, 8)
    results_c.sort(key=lambda x: (-x[1]["num_spots"], -x[1]["satisfaction"], x[1]["driving_fatigue"]))
    best_c = results_c[0] if len(results_c) > 0 else None
    
    best_schemes = {
        "A": ("深游打卡型 (A-tier)", best_a),
        "B": ("轻松休闲型 (B-tier)", best_b),
        "M": ("中等风险平衡型 (M-tier)", best_m),
        "C": ("特种兵打卡型 (C-tier)", best_c)
    }
    
    for key, (name, res) in best_schemes.items():
        if res is None:
            print(f"警告：未找到可行的 {name} 行程方案！")
            continue
        partition, metrics, timelines = res
        print(f"\n[最佳] 【{name}】方案评价指标:")
        print(f"  已选景点数: {metrics['num_spots']} 个")
        print(f"  总喜好满意度: {metrics['satisfaction']:.2f}")
        print(f"  行车总负荷: {metrics['driving_fatigue']:.2f} 小时")
        print(f"  行程均衡度(标准差): {metrics['balance_std']:.2f} 小时")
        print(f"  每日景点分配: {partition}")
        
        tb_rows = []
        for d in range(5):
            for step in timelines[d]:
                tb_rows.append({
                    "天数": f"第 {d+1} 天",
                    "活动环节": step["event"],
                    "开始时间": f"{int(step['start']):02d}:{int((step['start']%1)*60):02d}",
                    "结束时间": f"{int(step['end']):02d}:{int((step['end']%1)*60):02d}",
                    "持续时间(h)": f"{step['duration']:.2f}",
                    "所处地点": step["location"]
                })
        df_tb = pd.DataFrame(tb_rows)
        tb_path = os.path.join(TAB_DIR, f"table_problem2_timeline_{key}.csv")
        df_tb.to_csv(tb_path, index=False, encoding='utf-8-sig')
        print(f"  详细时间轴已写入: {tb_path}")
        
        plot_gantt(timelines, name, key)
        
    return best_schemes

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

# ----------------- MODULE 3: PROBLEM 3 随机扰动模拟器与 方差贡献率分析 -----------------

def run_stochastic_day_simulation(spots_list, stay_type, day_num, start_hour=8.0, 
                                 noise_traffic=True, noise_queue=True,
                                 p_peak_jam=0.4, p_flat_jam=0.15):
    curr_time = start_hour
    driving_time = 0.0
    
    def get_traffic_delay(dep_time, base_time):
        if not noise_traffic:
            return 0.0
        is_peak = (7.0 <= dep_time < 9.0) or (11.0 <= dep_time < 13.0) or (16.0 <= dep_time < 18.0)
        p_jam = p_peak_jam if is_peak else p_flat_jam
        
        if np.random.rand() < p_jam:
            if is_peak:
                return np.random.uniform(1.0, 4.0)
            else:
                return np.random.uniform(0.0, 1.5)
        return 0.0
        
    def get_queue_delay(arr_time):
        if not noise_queue:
            return 0.0
        is_peak = (9.0 <= arr_time < 12.0)
        if is_peak:
            return np.random.uniform(0.5, 3.0)
        else:
            return np.random.uniform(0.0, 1.0)
            
    if day_num == 1:
        # 第一天自驾4.0小时，入住0.5小时，从酒店出发
        curr_time = 7.0 + 4.0 + 0.5
        driving_time += 4.0
        
        s1 = spots_list[0]
        base_drive_1 = distances["Hotel"][s1]
        delay_1 = get_traffic_delay(curr_time, base_drive_1)
        actual_drive_1 = base_drive_1 + delay_1
        t_arr_1 = curr_time + actual_drive_1
        
        open_1, close_1 = spots[s1]["open_time"]
        t_arr_1 = max(t_arr_1, open_1)
        
        q_delay_1 = get_queue_delay(t_arr_1)
        t_entry_1 = t_arr_1 + q_delay_1
        
        if stay_type == 'comfort':
            planned_stay_1 = spots[s1]["comfort_stay"]
        elif stay_type == 'min':
            planned_stay_1 = spots[s1]["min_stay"]
        else:
            planned_stay_1 = 0.5 * (spots[s1]["min_stay"] + spots[s1]["comfort_stay"])
            
        t_dep_1 = t_entry_1 + planned_stay_1
        spans_lunch_1 = (t_entry_1 < 13.0 and t_dep_1 > 11.5)
        lunch_duration = np.random.uniform(0.8, 1.2) if spans_lunch_1 else 0.0
        t_dep_1 += lunch_duration
        
        max_possible_stay_1 = min(close_1, 21.0 - distances[s1]["Hotel"]) - t_entry_1
        s1_fail = (max_possible_stay_1 < spots[s1]["min_stay"])
        
        curr_time = t_dep_1
        driving_time += actual_drive_1
        
        s2_fail = False
        dest = s1
        
        if len(spots_list) == 2:
            s2 = spots_list[1]
            base_drive_2 = distances[s1][s2]
            delay_2 = get_traffic_delay(curr_time, base_drive_2)
            actual_drive_2 = base_drive_2 + delay_2
            t_arr_2 = curr_time + actual_drive_2
            
            open_2, close_2 = spots[s2]["open_time"]
            t_arr_2 = max(t_arr_2, open_2)
            
            q_delay_2 = get_queue_delay(t_arr_2)
            t_entry_2 = t_arr_2 + q_delay_2
            
            if stay_type == 'comfort':
                planned_stay_2 = spots[s2]["comfort_stay"]
            elif stay_type == 'min':
                planned_stay_2 = spots[s2]["min_stay"]
            else:
                planned_stay_2 = 0.5 * (spots[s2]["min_stay"] + spots[s2]["comfort_stay"])
                
            t_dep_2 = t_entry_2 + planned_stay_2
            spans_lunch_2 = (not spans_lunch_1) and (t_entry_2 < 13.0 and t_dep_2 > 11.5)
            lunch_duration_2 = np.random.uniform(0.8, 1.2) if spans_lunch_2 else 0.0
            t_dep_2 += lunch_duration_2
            
            max_possible_stay_2 = min(close_2, 21.0 - distances[s2]["Hotel"]) - t_entry_2
            s2_fail = (max_possible_stay_2 < spots[s2]["min_stay"])
            
            curr_time = t_dep_2
            driving_time += actual_drive_2
            dest = s2
            
        base_drive_back = distances[dest]["Hotel"]
        delay_back = get_traffic_delay(curr_time, base_drive_back)
        actual_drive_back = base_drive_back + delay_back
        t_end = curr_time + actual_drive_back
        
        overtime_fail = (t_end > 21.0)
        insufficiency_fail = s1_fail or s2_fail
        
        return overtime_fail, insufficiency_fail, t_end
        
    elif day_num == 5:
        # 第五天进行游览，然后酒店退房0.5小时，返程自驾4.0小时回家
        s1 = spots_list[0]
        base_drive_1 = distances["Hotel"][s1]
        delay_1 = get_traffic_delay(curr_time, base_drive_1)
        actual_drive_1 = base_drive_1 + delay_1
        t_arr_1 = curr_time + actual_drive_1
        
        open_1, close_1 = spots[s1]["open_time"]
        t_arr_1 = max(t_arr_1, open_1)
        
        q_delay_1 = get_queue_delay(t_arr_1)
        t_entry_1 = t_arr_1 + q_delay_1
        
        if stay_type == 'comfort':
            planned_stay_1 = spots[s1]["comfort_stay"]
        elif stay_type == 'min':
            planned_stay_1 = spots[s1]["min_stay"]
        else:
            planned_stay_1 = 0.5 * (spots[s1]["min_stay"] + spots[s1]["comfort_stay"])
            
        t_dep_1 = t_entry_1 + planned_stay_1
        spans_lunch_1 = (t_entry_1 < 13.0 and t_dep_1 > 11.5)
        lunch_duration = np.random.uniform(0.8, 1.2) if spans_lunch_1 else 0.0
        t_dep_1 += lunch_duration
        
        max_possible_stay_1 = min(close_1, 21.0 - distances[s1]["Hotel"]) - t_entry_1
        s1_fail = (max_possible_stay_1 < spots[s1]["min_stay"])
        
        curr_time = t_dep_1
        driving_time += actual_drive_1
        
        s2_fail = False
        dest = s1
        
        if len(spots_list) == 2:
            s2 = spots_list[1]
            base_drive_2 = distances[s1][s2]
            delay_2 = get_traffic_delay(curr_time, base_drive_2)
            actual_drive_2 = base_drive_2 + delay_2
            t_arr_2 = curr_time + actual_drive_2
            
            open_2, close_2 = spots[s2]["open_time"]
            t_arr_2 = max(t_arr_2, open_2)
            
            q_delay_2 = get_queue_delay(t_arr_2)
            t_entry_2 = t_arr_2 + q_delay_2
            
            if stay_type == 'comfort':
                planned_stay_2 = spots[s2]["comfort_stay"]
            elif stay_type == 'min':
                planned_stay_2 = spots[s2]["min_stay"]
            else:
                planned_stay_2 = 0.5 * (spots[s2]["min_stay"] + spots[s2]["comfort_stay"])
                
            t_dep_2 = t_entry_2 + planned_stay_2
            spans_lunch_2 = (not spans_lunch_1) and (t_entry_2 < 13.0 and t_dep_2 > 11.5)
            lunch_duration_2 = np.random.uniform(0.8, 1.2) if spans_lunch_2 else 0.0
            t_dep_2 += lunch_duration_2
            
            max_possible_stay_2 = min(close_2, 21.0 - distances[s2]["Hotel"]) - t_entry_2
            s2_fail = (max_possible_stay_2 < spots[s2]["min_stay"])
            
            curr_time = t_dep_2
            driving_time += actual_drive_2
            dest = s2
            
        base_drive_back = distances[dest]["Hotel"]
        delay_back = get_traffic_delay(curr_time, base_drive_back)
        actual_drive_back = base_drive_back + delay_back
        t_ret_hotel = curr_time + actual_drive_back
        
        # 增加退房和返程自驾
        t_end = t_ret_hotel + 0.5 + 4.0
        driving_time += actual_drive_back + 4.0
        
        overtime_fail = (t_end > 21.0)
        insufficiency_fail = s1_fail or s2_fail
        
        return overtime_fail, insufficiency_fail, t_end
        
    else:
        # 标准天 (2, 3, 4)
        s1 = spots_list[0]
        base_drive_1 = distances["Hotel"][s1]
        delay_1 = get_traffic_delay(curr_time, base_drive_1)
        actual_drive_1 = base_drive_1 + delay_1
        t_arr_1 = curr_time + actual_drive_1
        
        open_1, close_1 = spots[s1]["open_time"]
        t_arr_1 = max(t_arr_1, open_1)
        
        q_delay_1 = get_queue_delay(t_arr_1)
        t_entry_1 = t_arr_1 + q_delay_1
        
        if stay_type == 'comfort':
            planned_stay_1 = spots[s1]["comfort_stay"]
        elif stay_type == 'min':
            planned_stay_1 = spots[s1]["min_stay"]
        else:
            planned_stay_1 = 0.5 * (spots[s1]["min_stay"] + spots[s1]["comfort_stay"])
            
        t_dep_1 = t_entry_1 + planned_stay_1
        spans_lunch_1 = (t_entry_1 < 13.0 and t_dep_1 > 11.5)
        lunch_duration = np.random.uniform(0.8, 1.2) if spans_lunch_1 else 0.0
        t_dep_1 += lunch_duration
        
        max_possible_stay_1 = min(close_1, 21.0 - distances[s1]["Hotel"]) - t_entry_1
        s1_fail = (max_possible_stay_1 < spots[s1]["min_stay"])
        
        curr_time = t_dep_1
        driving_time = actual_drive_1
        
        s2_fail = False
        dest = s1
        
        if len(spots_list) == 2:
            s2 = spots_list[1]
            base_drive_2 = distances[s1][s2]
            delay_2 = get_traffic_delay(curr_time, base_drive_2)
            actual_drive_2 = base_drive_2 + delay_2
            t_arr_2 = curr_time + actual_drive_2
            
            open_2, close_2 = spots[s2]["open_time"]
            t_arr_2 = max(t_arr_2, open_2)
            
            q_delay_2 = get_queue_delay(t_arr_2)
            t_entry_2 = t_arr_2 + q_delay_2
            
            if stay_type == 'comfort':
                planned_stay_2 = spots[s2]["comfort_stay"]
            elif stay_type == 'min':
                planned_stay_2 = spots[s2]["min_stay"]
            else:
                planned_stay_2 = 0.5 * (spots[s2]["min_stay"] + spots[s2]["comfort_stay"])
                
            t_dep_2 = t_entry_2 + planned_stay_2
            spans_lunch_2 = (not spans_lunch_1) and (t_entry_2 < 13.0 and t_dep_2 > 11.5)
            lunch_duration_2 = np.random.uniform(0.8, 1.2) if spans_lunch_2 else 0.0
            t_dep_2 += lunch_duration_2
            
            max_possible_stay_2 = min(close_2, 21.0 - distances[s2]["Hotel"]) - t_entry_2
            s2_fail = (max_possible_stay_2 < spots[s2]["min_stay"])
            
            curr_time = t_dep_2
            driving_time += actual_drive_2
            dest = s2
            
        base_drive_back = distances[dest]["Hotel"]
        delay_back = get_traffic_delay(curr_time, base_drive_back)
        actual_drive_back = base_drive_back + delay_back
        t_end = curr_time + actual_drive_back
        
        overtime_fail = (t_end > 21.0)
        insufficiency_fail = s1_fail or s2_fail
        
        return overtime_fail, insufficiency_fail, t_end

def run_full_itinerary_simulation(partition, stay_type, start_hours, N=10000,
                                 noise_traffic=True, noise_queue=True, seed=12345):
    if seed is not None:
        np.random.seed(seed)
    overtime_count = 0
    insufficiency_count = 0
    both_success_count = 0
    
    daily_overtime = [0] * 5
    daily_insufficiency = [0] * 5
    end_times_history = [[] for _ in range(5)]
    
    for _ in range(N):
        itinerary_overtime = False
        itinerary_insuff = False
        
        for d in range(5):
            spots_list = partition[d]
            overtime, insuff, t_end = run_stochastic_day_simulation(
                spots_list, stay_type, d + 1, start_hours[d], noise_traffic, noise_queue
            )
            
            end_times_history[d].append(t_end)
            
            if overtime:
                daily_overtime[d] += 1
                itinerary_overtime = True
            if insuff:
                daily_insufficiency[d] += 1
                itinerary_insuff = True
                
        if itinerary_overtime:
            overtime_count += 1
        if itinerary_insuff:
            insufficiency_count += 1
        if (not itinerary_overtime) and (not itinerary_insuff):
            both_success_count += 1
            
    reliability = both_success_count / N
    overtime_prob = overtime_count / N
    insuff_prob = insufficiency_count / N
    
    return {
        "reliability": reliability,
        "overtime_probability": overtime_prob,
        "insuff_probability": insuff_prob,
        "daily_overtime": [c / N for c in daily_overtime],
        "daily_insuff": [c / N for c in daily_insufficiency],
        "end_times_history": end_times_history
    }

def plot_prob_distribution_key(end_times_history, partition, name, key):
    plt.figure(figsize=(10, 6), dpi=300)
    for d in range(5):
        # 清洗图例中的标签，防止显示 Python list/tuple 的括号与引号
        label_str = clean_partition_label(partition[d])
        sns.kdeplot(end_times_history[d], fill=True, label=f"第 {d+1} 天 ({label_str})", linewidth=2.5)
        
    plt.axvline(21.0, color="red", linestyle="--", linewidth=2.0, label="21:00 返程硬时间界限")
    plt.xlim(13.0, 24.0)
    plt.xticks(range(13, 25), [f"{h:02d}:00" for h in range(13, 25)])
    plt.xlabel("实际返回市区酒店时刻", fontsize=12, fontweight="bold")
    plt.ylabel("概率密度 (KDE Estimation)", fontsize=12, fontweight="bold")
    # 去除硬编码标题，避免与 LaTeX caption 重复
    plt.legend(loc="upper left")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    
    # 保存特定键的KDE图
    fig_dist_path_key = os.path.join(FIG_DIR, f"monte_carlo_pdf_distributions_{key}.png")
    plt.savefig(fig_dist_path_key, bbox_inches="tight")
    
    # 与B-tier保持兼容
    if key == "B":
        fig_dist_path_compat = os.path.join(FIG_DIR, "monte_carlo_pdf_distributions.png")
        plt.savefig(fig_dist_path_compat, bbox_inches="tight")
        
    plt.close()

def plot_sensitivity_bar_key(traffic_contribs, queue_contribs, name, key):
    plt.figure(figsize=(10, 6), dpi=300)
    
    # 构造 x 轴标签
    x_labels = ["第 1 天", "第 2 天", "第 3 天", "第 4 天", "第 5 天", "五日平均"]
    
    # 获取平均值并拼接到列表中
    avg_t = np.mean(traffic_contribs)
    avg_q = np.mean(queue_contribs)
    
    y_traffic = [val * 100 for val in traffic_contribs] + [avg_t * 100]
    y_queue = [val * 100 for val in queue_contribs] + [avg_q * 100]
    
    x = np.arange(len(x_labels))
    width = 0.35  # 条形图宽度
    
    # 使用期刊级莫兰迪学术配色：
    # 道路拥堵：暗红 (#b03a2e)，景区排队：经典暗蓝 (#1f618d)
    rects1 = plt.bar(x - width/2, y_traffic, width, label="道路拥堵延迟贡献率 ($S_{T}$)", color="#b03a2e", edgecolor="black", alpha=0.85)
    rects2 = plt.bar(x + width/2, y_queue, width, label="景区入园排队贡献率 ($S_{Q}$)", color="#1f618d", edgecolor="black", alpha=0.85)
    
    plt.ylabel("方差波动贡献率 (%)", fontsize=12, fontweight="bold")
    plt.xticks(x, x_labels, fontsize=10, fontweight="bold")
    plt.ylim(0, max(max(y_traffic), max(y_queue)) * 1.15)  # 留出顶部空间放数值标签
    
    # 添加网格
    plt.grid(axis="y", linestyle="--", alpha=0.5)
    
    # 在条形图上方标注数值标签
    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            plt.annotate(f"{height:.1f}%",
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),  # 3点垂直偏移
                        textcoords="offset points",
                        ha="center", va="bottom", fontsize=8.5, fontweight="bold")
                        
    autolabel(rects1)
    autolabel(rects2)
    
    plt.legend(loc="upper right", fontsize=10, frameon=True, shadow=True)
    plt.tight_layout()
    
    # 依然保存为 sobol_sensitivity_pie 相关的命名，保持与 LaTeX 引用完全兼容，避免编译错误
    fig_pie_path_key = os.path.join(FIG_DIR, f"sobol_sensitivity_pie_{key}.png")
    plt.savefig(fig_pie_path_key, bbox_inches="tight")
    
    # 与B-tier保持兼容
    if key == "B":
        fig_pie_path_compat = os.path.join(FIG_DIR, "sobol_sensitivity_pie.png")
        plt.savefig(fig_pie_path_compat, bbox_inches="tight")
        
    plt.close()

def optimize_reliability_to_90_key(partition, stay_type, start_hours, N, name, key):
    print(f"\n--- 启动【{name}】可靠度提升至90%以上的优化方案设计 ---")
    
    res_base = run_full_itinerary_simulation(partition, stay_type, start_hours, N)
    print(f" 原始基准行程 (8:00出发) 可靠度: {res_base['reliability']*100:.2f}%")
    
    if res_base['reliability'] >= 0.90:
        print(" 基准行程可靠度已满足90%以上，无需调整出发时序。")
        return
        
    weak_day_idx = np.argmax(res_base['daily_overtime'])
    
    # 优化方案一: 薄弱天提前出发
    opt_start_hours = list(start_hours)
    opt_start_hours[weak_day_idx] = 7.0
    res_opt = run_full_itinerary_simulation(partition, stay_type, opt_start_hours, N)
    print(f" 优化后方案一 (第{weak_day_idx+1}天提前至07:00出发) 可靠度: {res_opt['reliability']*100:.2f}%")
    
    # 优化方案二: 全程统一提前至 07:30 出发
    opt_start_hours_2 = [7.5] * 5
    res_opt_2 = run_full_itinerary_simulation(partition, stay_type, opt_start_hours_2, N)
    print(f" 优化后方案二 (每天均提前至07:30出发) 可靠度: {res_opt_2['reliability']*100:.2f}%")
    
    df_opt = pd.DataFrame({
        "方案描述": ["基准方案 (全天08:00出发)", f"优化方案一 (第{weak_day_idx+1}天提前至07:00出发)", "优化方案二 (全程07:30统一提前出发)"],
        "整体行程可靠度": [res_base['reliability'], res_opt['reliability'], res_opt_2['reliability']],
        "超时失效概率": [res_base['overtime_probability'], res_opt['overtime_probability'], res_opt_2['overtime_probability']],
        "游览不达标率": [res_base['insuff_probability'], res_opt['insuff_probability'], res_opt_2['insuff_probability']]
    })
    
    # 保存特定键的优化对比图
    opt_path_key = os.path.join(TAB_DIR, f"table_problem3_optimization_comparison_{key}.csv")
    df_opt.to_csv(opt_path_key, index=False, encoding='utf-8-sig')
    print(f" 优化方案对比表格({key})已保存: {opt_path_key}")
    
    # 与B-tier保持兼容
    if key == "B":
        opt_path_compat = os.path.join(TAB_DIR, "table_problem3_optimization_comparison.csv")
        df_opt.to_csv(opt_path_compat, index=False, encoding='utf-8-sig')

def evaluate_scheme_stochastic(scheme, key, name, N_trials=10000):
    partition, metrics, timelines = scheme
    start_hours = [8.0] * 5
    stay_type = 'mid'
    
    print(f"\n正在进行【{name}】蒙特卡洛随机动力学仿真，抽样次数 N = {N_trials} 次...")
    res_all = run_full_itinerary_simulation(partition, stay_type, start_hours, N_trials, True, True)
    res_traffic = run_full_itinerary_simulation(partition, stay_type, start_hours, N_trials, True, False)
    res_queue = run_full_itinerary_simulation(partition, stay_type, start_hours, N_trials, False, True)
    
    print(f"\n================== {name} 随机评估结果 ==================")
    print(f"行程整体稳定可靠度: {res_all['reliability']*100:.2f}%")
    print(f"由于道路堵车或排队导致行程超时（超过21:00）的概率: {res_all['overtime_probability']*100:.2f}%")
    print(f"由于拥堵导致实际游览时间不达标的概率: {res_all['insuff_probability']*100:.2f}%")
    print("每日超时风险分布: " + ", ".join([f"第{i+1}天: {p*100:.1f}%" for i, p in enumerate(res_all['daily_overtime'])]))
    print("每日时长不达标分布: " + ", ".join([f"第{i+1}天: {p*100:.1f}%" for i, p in enumerate(res_all['daily_insuff'])]))
    
    traffic_contribs = []
    queue_contribs = []
    for d in range(5):
        var_all = np.var(res_all["end_times_history"][d])
        var_t = np.var(res_traffic["end_times_history"][d])
        var_q = np.var(res_queue["end_times_history"][d])
        
        s_t = var_t / var_all if var_all > 0 else 0.0
        s_q = var_q / var_all if var_all > 0 else 0.0
        
        traffic_contribs.append(s_t)
        queue_contribs.append(s_q)
        
    avg_s_t = np.mean(traffic_contribs)
    avg_s_q = np.mean(queue_contribs)
    print("\n------------------ 物理隔离场景方差贡献率分析 ------------------")
    print(f"道路堵车对行程时间波动的贡献率: {avg_s_t*100:.2f}%")
    print(f"景区排队对行程时间波动的贡献率: {avg_s_q*100:.2f}%")
    
    weak_day = np.argmax(res_all['daily_overtime']) + 1
    max_overtime_p = np.max(res_all['daily_overtime'])
    print(f"系统结构性薄弱点识别：")
    print(f"  - 风险最高节点为【第 {weak_day} 天】，单日超时失效概率达 {max_overtime_p*100:.2f}%。")
    print(f"  - 主要薄弱原因：该日游览景点组合为 {partition[weak_day-1]}，游览时间过长且通勤总距离远，缺乏延时缓冲。")
    
    df_stoch = pd.DataFrame({
        "评估维度": ["整体行程", "第一天", "第二天", "第三天", "第四天", "第五天"],
        "超时失效概率": [res_all['overtime_probability']] + res_all['daily_overtime'],
        "游览不达标概率": [res_all['insuff_probability']] + res_all['daily_insuff'],
        "堵车贡献率": [avg_s_t] + traffic_contribs,
        "排队贡献率": [avg_s_q] + queue_contribs
    })
    
    # 保存特定键的随机评估CSV数据
    stoch_path_key = os.path.join(TAB_DIR, f"table_problem3_stochastic_evaluation_{key}.csv")
    df_stoch.to_csv(stoch_path_key, index=False, encoding='utf-8-sig')
    print(f"随机仿真指标评估表格({key})已保存: {stoch_path_key}")
    
    # 与B-tier保持兼容
    if key == "B":
        stoch_path_compat = os.path.join(TAB_DIR, "table_problem3_stochastic_evaluation.csv")
        df_stoch.to_csv(stoch_path_compat, index=False, encoding='utf-8-sig')
        
    plot_prob_distribution_key(res_all["end_times_history"], partition, name, key)
    plot_sensitivity_bar_key(traffic_contribs, queue_contribs, name, key)
    optimize_reliability_to_90_key(partition, stay_type, start_hours, N_trials, name, key)

def solve_problem_3(best_schemes):
    print("\n--- 启动问题三：随机扰动下行程稳定性仿真与敏感性分析 ---")
    
    # 1. 评估 B-tier (轻松休闲型)
    b_scheme = best_schemes["B"][1]
    if b_scheme is not None:
        evaluate_scheme_stochastic(b_scheme, "B", "轻松休闲型 (B-tier)")
        
    # 2. 评估 M-tier (中等风险平衡型)
    m_scheme = best_schemes["M"][1]
    if m_scheme is not None:
        evaluate_scheme_stochastic(m_scheme, "M", "中等风险平衡型 (M-tier)")

def plot_prob_distribution(end_times_history, partition):
    plt.figure(figsize=(10, 6), dpi=300)
    for d in range(5):
        # 清洗图例中的标签，防止显示 Python list/tuple 的括号与引号
        label_str = clean_partition_label(partition[d])
        sns.kdeplot(end_times_history[d], fill=True, label=f"第 {d+1} 天 ({label_str})", linewidth=2.5)
        
    plt.axvline(21.0, color="red", linestyle="--", linewidth=2.0, label="21:00 返程硬时间界限")
    plt.xlim(13.0, 24.0)
    plt.xticks(range(13, 25), [f"{h:02d}:00" for h in range(13, 25)])
    plt.xlabel("实际返回市区酒店时刻", fontsize=12, fontweight="bold")
    plt.ylabel("概率密度 (KDE Estimation)", fontsize=12, fontweight="bold")
    # 去除硬编码标题，避免与 LaTeX caption 重复
    plt.legend(loc="upper left")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    fig_dist_path = os.path.join(FIG_DIR, "monte_carlo_pdf_distributions.png")
    plt.savefig(fig_dist_path, bbox_inches="tight")
    plt.close()

def plot_sensitivity_pie(s_t, s_q):
    plt.figure(figsize=(6, 5), dpi=300)
    total = s_t + s_q
    weights = [s_t/total, s_q/total]
    labels = [f"道路拥堵延迟 ({weights[0]*100:.1f}%)", f"景区入园排队 ({weights[1]*100:.1f}%)"]
    colors = ["#d62728", "#1f77b4"]
    
    plt.pie(weights, labels=labels, colors=colors, autopct='%1.1f%%', startangle=140, 
            wedgeprops={"edgecolor":"black",'linewidth': 1.5, 'antialiased': True},
            textprops={'fontsize': 11, 'weight': 'bold'})
    plt.title("行程延时方差波动的敏感性来源贡献占比 (物理隔离场景方差贡献)", fontsize=13, fontweight="bold", pad=15)
    plt.tight_layout()
    fig_pie_path = os.path.join(FIG_DIR, "sobol_sensitivity_pie.png")
    plt.savefig(fig_pie_path, bbox_inches="tight")
    plt.close()

def optimize_reliability_to_90(partition, stay_type, start_hours, N):
    print("\n--- 启动可靠度提升至90%以上的优化方案设计 ---")
    
    res_base = run_full_itinerary_simulation(partition, stay_type, start_hours, N)
    print(f" 原始基准行程 (8:00出发) 可靠度: {res_base['reliability']*100:.2f}%")
    
    if res_base['reliability'] >= 0.90:
        print(" 基准行程可靠度已满足90%以上，无需调整出发时序。")
        return
        
    weak_day_idx = np.argmax(res_base['daily_overtime'])
    
    # 优化方案一: 薄弱天提前出发
    opt_start_hours = list(start_hours)
    opt_start_hours[weak_day_idx] = 7.0
    res_opt = run_full_itinerary_simulation(partition, stay_type, opt_start_hours, N)
    print(f" 优化后方案一 (第{weak_day_idx+1}天提前至07:00出发) 可靠度: {res_opt['reliability']*100:.2f}%")
    
    # 优化方案二: 全程统一提前至 07:30 出发
    opt_start_hours_2 = [7.5] * 5
    res_opt_2 = run_full_itinerary_simulation(partition, stay_type, opt_start_hours_2, N)
    print(f" 优化后方案二 (每天均提前至07:30出发) 可靠度: {res_opt_2['reliability']*100:.2f}%")
    
    df_opt = pd.DataFrame({
        "方案描述": ["基准方案 (全天08:00出发)", f"优化方案一 (第{weak_day_idx+1}天提前至07:00出发)", "优化方案二 (全程07:30统一提前出发)"],
        "整体行程可靠度": [res_base['reliability'], res_opt['reliability'], res_opt_2['reliability']],
        "超时失效概率": [res_base['overtime_probability'], res_opt['overtime_probability'], res_opt_2['overtime_probability']],
        "游览不达标率": [res_base['insuff_probability'], res_opt['insuff_probability'], res_opt_2['insuff_probability']]
    })
    opt_path = os.path.join(TAB_DIR, "table_problem3_optimization_comparison.csv")
    df_opt.to_csv(opt_path, index=False, encoding='utf-8-sig')
    print(f" 优化方案对比表格已保存: {opt_path}")

# ----------------- MAIN PIPELINE -----------------

if __name__ == "__main__":
    df_p1 = solve_problem_1()
    best_schemes = solve_problem_2(df_p1)
    solve_problem_3(best_schemes)
    print("\n====== 数据求解与图形渲染全部完成 ======")
