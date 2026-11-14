# 数据字典与评分口径

| 字段 | 单位/取值 | 含义与边界 |
|---|---|---|
| device_id / session_id | D01…D16 / 设备_场景 | 同一设备只能属于一个数据划分，窗口不得跨会话 |
| split / scenario | train, validation, test / 构造场景 | 元数据，不进入预测特征；场景只用于选择训练正常基线 |
| minute | min，0…179整数 | 每会话连续、严格递增，无重复 |
| current_a / soc | A / 0…1 | 放电电流为正；SOC为构造状态，不声称是可直接观测的现场真值 |
| voltage_a_v / voltage_b_v | V | 同一目标的双电压通道；缺失用空字段 |
| ambient_c / temperature_c | ℃ | 环境温度与测量温度 |
| expected_temperature_c | ℃ | 预设名义热响应；真实数据接入需另行辨识和验证 |
| label | normal等 | 构造真值，只训练分类器或评分，不作为输入特征 |
| valid | True / False | 必须连续5点所有所需信号完整才可判定 |
| voltage_residual_v | V | 5点电压名义模型残差中位数 |
| channel_difference_v | V | 5点A−B通道差中位数 |
| temperature_residual_c | ℃ | 5点温度模型残差中位数 |
| voltage_std_v | V | 5点电压残差总体标准差（ddof=0） |
| temperature_slope_c_min | ℃/min | 尾随窗口首末温度残差差值除以4 min |
| rule/logistic/isolation_score | 无量纲 | 数值越大越异常；不同模型不可直接横向比较 |
| class_prediction / class_confidence | 类别 / 0…1 | 类别最大分值；未进行概率校准，不能当故障后验概率 |
| alarm / onset | True / False | 持续状态 / 本时刻由非告警转为告警 |
| start_min / end_min | min | 事件半开区间[start,end)，结束样本不属于事件 |
| delay_min | min或空 | 首次有效告警起点减事件起点；漏报为空，不补零 |

异常标签在故障注入结束时立刻变为normal，尾随特征可能仍含历史异常；这些恢复过渡区保留在分类评分中。规则与孤立森林的正常分布拟合仅使用未注入目标异常的训练会话，避免这类残留污染基线。缺失时清空窗口、重置告警计数；恢复后重新收满5个点。

数据来源是程序构造；16个设备ID仅是模拟实体。参数与数据字段的定义应与run.py保持一致，真实数据映射必须保留原始时间戳、单位、质量标记、标签不确定性和设备身份。
