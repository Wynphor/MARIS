# -*- coding: utf-8 -*-
"""
文件名称: run_dual_spot_simulation.py
摘要说明: A1 + A10 双景点级联失效蒙特卡洛动力学仿真程序
"""

import numpy as np
import json
import os

# 设置随机种子以保证可复现性
np.random.seed(12345)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_PATH = os.path.join(BASE_DIR, "data", "c_data.json")

with open(DATA_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

spots = data["spots"]
distances = data["distances"]

N = 10000
p_peak_jam = 0.4
p_flat_jam = 0.15

def get_traffic_delay(dep_time, base_time, noise_traffic=True):
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
    
def get_queue_delay(arr_time, noise_queue=True):
    if not noise_queue:
        return 0.0
    is_peak = (9.0 <= arr_time < 12.0)
    if is_peak:
        return np.random.uniform(0.5, 3.0)
    else:
        return np.random.uniform(0.0, 1.0)

def run_single_day_simulation(spots_list, stay_type, start_hour=8.0):
    curr_time = start_hour
    driving_time = 0.0
    
    # 1. Hotel -> s1
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
    
    base_drive_back = distances[s2]["Hotel"]
    delay_back = get_traffic_delay(curr_time, base_drive_back)
    actual_drive_back = base_drive_back + delay_back
    t_end = curr_time + actual_drive_back
    
    overtime_fail = (t_end > 21.0)
    insufficiency_fail = s1_fail or s2_fail
    
    return overtime_fail, insufficiency_fail, t_end

overtimes = 0
insufficiencies = 0
successes = 0
end_times = []

for _ in range(N):
    overtime, insuff, t_end = run_single_day_simulation(["A1", "A10"], "mid", start_hour=8.0)
    end_times.append(t_end)
    if overtime:
        overtimes += 1
    if insuff:
        insufficiencies += 1
    if not overtime and not insuff:
        successes += 1

overtime_rate = overtimes / N * 100
insuff_rate = insufficiencies / N * 100
success_rate = successes / N * 100

print(f"--- A1+A10 双景点级联失效动力学仿真结果 ---")
print(f"蒙特卡洛模拟总轮数: {N}")
print(f"超时失效轮数 (返程时刻 > 21:00): {overtimes} ({overtime_rate:.2f}%)")
print(f"游览时长不足失效轮数 (停留时长 < 最低限制): {insufficiencies} ({insuff_rate:.2f}%)")
print(f"单日整体行程成功率 (系统可靠度): {successes} ({success_rate:.2f}%)")
print(f"平均返程时刻: {np.mean(end_times):.2f} (约 {int(np.mean(end_times))}:{int((np.mean(end_times)%1)*60):02d})")
print(f"第95百分位数返程时刻: {np.percentile(end_times, 95):.2f} (约 {int(np.percentile(end_times, 95))}:{int((np.percentile(end_times, 95)%1)*60):02d})")
print(f"最迟返程时刻: {np.max(end_times):.2f}")


# 将模拟结果保存为 CSV 文件以供交叉验证
csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dual_spot_simulation_results.csv")
import pandas as pd
df_results = pd.DataFrame({
    "trial": range(1, N + 1),
    "end_time": end_times,
    "overtime": [int(e > 21.0) for e in end_times]
})
df_results.to_csv(csv_path, index=False)
print(f"Results successfully saved to {csv_path}")
