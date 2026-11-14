# 数据字典与时间对齐

所有轨迹均为作者构造。`data/trajectories.json`保存17条完整轨迹；`models.json`保存已选权重、标准化参数、训练域与验证包络；`results/ch10/experiment.json`由运行生成。

## 轨迹记录

| 字段 | 长度/单位 | 含义 |
|---|---|---|
| id / split / seed | 字符串 / 字符串 / 整数 | 轨迹标识、划分、生成种子 |
| t_s | n+1 / s | 状态时刻，0至n×120 |
| temperature | n+1 / ℃ | 独立DOP853参考温度，即本章精确观测 |
| power | n / kW | 区间[k,k+1)保持的加热功率 |
| ambient | n / ℃ | 同一区间保持的环境温度 |
| energy_net_kJ | n / kJ | 该区间参考方程同时积分的净热量 |
| beta_reference | kW/K² | 构造环境参数，供来源登记与核验 |
| measurement_noise_std | K | 本章固定为0 |

温度变动乘C得到kJ，与energy_net_kJ对应；电输入累计Σpower×120/3600得到kWh。单条6 h轨迹n=180，状态181个。全数据17条98 h，区间2940、状态2957。

## 模型文件

`models.physical`含capacity与ua；`models.direct/residual`的输入顺序为[T,Ta,u]，coefs矩阵按input×output方向排列，biases为每层输出偏置。隐藏tanh，末层identity。网络先做输入标准化，输出再乘y_scale并加y_mean。direct输出温度增量，residual输出相对于linear_step的下一温度修正。

`development_candidates`保留全部4个开发候选的完整权重、标准化参数、配置和验证指标；`models`为按验证分数选定的三个预测器。

`domain`为训练输入的三个边界，逐变量检查。`empirical_bands[model][h]`为验证h步终点绝对误差的95%分位数（higher），单位K。`selected_config.json`先于测试计算写入输出目录。

## 预测结果

prediction_metrics每行对应轨迹×模型×跨度，rmse/mae/bias单位K；n_windows=n−h+1；empirical_coverage为测试终点误差绝对值落入对应验证半宽的比例。open_loop从每条轨迹起点连续递推全部n步，中途保持自己的预测状态。

## 控制记录

control_scenarios的target长n+1、ambient长n。rows[k].T_before为时刻k观测，T_after为区间推进后的参考状态，target=target[k+1]。time_s=k×120。当前决策使用从k起的环境预测与从k+1起的目标，尾部不足12步以最后值延拓。

candidates保存常动作候选未来12步的模型预测与代价；这些预测对应假设动作序列，实际控制每步重新规划。字段requested_action为规划器请求，action为共同执行器最终动作。status优先标记interlock，再标记fallback、rule或planned。

fallback为请求标志；fallback_executed为最终执行标志。requested_fallback_action与executed_fallback_action分别记录两者，执行被联锁接管时后者为null。兼容字段fallback_action保存请求值。fallback_kind为physical_feedback或zero_power；fallback_reason说明域外、非有限预测或无可行候选。

outside_input_domain_count检查实际(T_before,u,Ta)三元组；state_temperature_outside_count只检查T_before范围；outside_action_count只检查执行动作上限。三类计数分别报告。

domain_probes包含域内、高温、未知环境和非有限观测的明确构造请求。JSON用null记录无法以有限数表示的输入，程序测试内部使用NaN。完整行为核验输出在verification.json，输出遵循标准JSON格式，非有限输入以null登记。
