# 数据字典

cycles.csv：cell_id（字符串）；cycle（从1开始的循环整数）；capacity_ah（A·h）；reference_capacity_ah（A·h，本章2.0）；resistance_ohm（Ω）；temperature_c（℃）；latent_soh（构造潜变量，仅解释生成机制）；source_kind（constructed）。全部输入数值有限，cell_id+cycle唯一，循环顺序连续。

predictions.csv：target_cycle是预测目标，last_input_cycle=target_cycle-1。split为train/validation/calibration/test。target_soh和四个模型预测均为无量纲，lower_soh/upper_soh是所选模型的经验带。误差汇总按100×(预测−标签)得到百分点。

soc.csv：time_s表示区间边界时间。reference、correct、current_bias、nominal_capacity、initial_bias均为SOC无量纲。0—900 s为0.6 A，900—1800 s为1.2 A，1800—2700 s为−0.4 A，2700—3600 s为0 A；放电为正。

models.pkl为可信本地生成的Python模型文件，包含预处理与特征顺序。manifest.json记录版本与SHA256。metrics.json同时保留所有候选验证分数、单种子测试分数与警告。

寿命标签采用首次容量比例≤0.8的循环号（包含等号）；160循环内未触发者记录右删失，终点为null。
