# 数据字典

所有序列由 `profiles()` 确定性生成，无外部测量文件、训练集或随机采样。

|字段|含义|单位|
|---|---|---|
|time|区间开始时刻|h|
|renewable|可再生输入功率|kW|
|demand|用氢需求|kg/h|
|tariff|电网电价|元/kWh|
|grid_cap|电网接入上限|kW|
|request / p|请求/实际电解功率|kW|
|on / start|开机/启动事件|0或1|
|q / served / shortage|产氢/已供/缺供流率|kg/h|
|m_before / m_after|区间初/末质量库存|kg|
|compressor / auxiliary / total|压缩/辅助/总电功率|kW|
|grid / renewable_used / curtailment|购电/已利用可再生/弃用功率|kW|
|loss|本区间库存损失|kg，本版0|
|projected|请求是否被执行器调整|布尔|

summary各字段单位由后缀标明；electricity_cost/start_cost为元，starts/projected_steps为次数，lhv_efficiency为0–1比值。solver.status为SciPy状态码，gap为相对最优间隙，objective为包含惩罚项的目标值。

`experiment.json`含完整配置、输入、逐步账本、求解状态和摘要；`profiles.csv`包含4类输入各192行；`summary.csv`包含36组摘要；`checkpoint.json`为分组中间保存，最终完整文件为experiment.json。演示内嵌数字保留8位小数，跨语言验证使用完整精度结果。
