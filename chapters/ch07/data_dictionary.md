# 第7章数据字典

所有输入来自model.demand(seed,n,dt,scenario)，对应教学构造功率序列。场景与种子组合唯一标识输入，method与training_seed标识控制器。实际量使用双精度保存，绘图与正文进行显示舍入。

| 字段 | 单位与定义 |
| --- | --- |
| time_s / k | 秒 / 从0开始的步索引 |
| demand_kw | 母线净需求，正值需供电 |
| request_kw | 原始电池功率请求 |
| battery_kw / sc_kw | 母线侧执行功率，放电为正 |
| residual_kw | demand−battery−sc；保留符号 |
| battery_before_kwh / battery_kwh | 电池步前 / 步后内部能量 |
| sc_before_kwh / sc_kwh | 电容步前 / 步后内部能量 |
| sc_voltage_v | 按C和步后能量反算电压 |
| ramp_kw_s | 电池执行功率变化率 |
| projection_kw | 实际电池功率减请求功率 |
| ramp_conflict | 能量与爬坡窗口交集为空时为1 |
| cost | 用执行结果计算的归一化单步代价 |

## 输出

- evaluation.csv：420次运行的RMSE、绝对残差积分、吞吐量、电池RMS、爬坡RMS、两支路端点、投影次数、物理越限和代价。
- training.csv：各种子每25回合的验证代价、训练当回合代价、探索概率。
- constraint_events.csv：全部测试中发生投影、残差或爬坡冲突的逐时记录，保留训练/输入/场景标识。由run.py生成，体积较大，留在results目录。
- experiment.json：配置、冻结Q表、全部指标与12条代表轨迹；代表输入固定30000，Q策略按验证选择。
- q_seed_*.npz：每个训练种子选中的729×7 Q表。

指标计算：RMSE是每条600 s轨迹内残差平方均值开方；吞吐量为Σ|P_b|/3600；端点为末库存减初始库存；投影判据为|执行−请求|>1e−8 kW。平均RMSE按逐条RMSE再平均。
