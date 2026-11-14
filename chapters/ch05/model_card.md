# 第5章模型卡与来源

版本v0.1.0，2026-11-14；对象W-C1-P。用途是教学、算法复算和扩展实验。所有运行数据及经济参数均由本章构造。

## 边界

冷机55 kW产冷，直供与充冷共享；储罐接口各30 kW且互斥；供水6 ℃、回水12 ℃、末端流量上限3.2 kg/s。常规有效容量为0.85×V×1000×4.18×6/3600 kWh。充放效率各0.95，每1 h库存损失0.002。

温度资格要求储罐支路及混合供水均≤7 ℃。资格失效情景设储罐出口8 ℃，有效热力学容量随温差改变；放冷受资格限制，规则也停止充冷。其余条件与炎热日一致。

各日初末库存均为零，MPC每次窗口也设置零末端库存。当前请求和当前气温在时段开始已知，未来数据使用发布预测，时间尺度1 h。气温与负荷之间、COP与气温之间的关系为构造函数。冷机没有启停、最低稳定负荷与爬坡约束，泵耗为线性近似。储罐使用库存模型，后续可扩展分层温度状态。

## 评价与证据

调度目标为电费＋100元/kWh冷量×未满足冷量；年度成本为四类日加权电费＋投资年化，服务不足独立报告。理想信息下的目标界限只在相同模型、相同权重、相同工况的可行方案间比较。独立数值核验与浏览器复算覆盖实现正确性；现场性能评价需要独立实测与适用条件确认。

程序对求解失败抛出错误，保底运行策略是后续现场控制设计与验证的组成部分。本教学代码执行单机离线优化。

## 可复用资产

八幅代码图均由同仓库源码生成，定量图读取同一份 `experiment.json`。SVG文字可编辑，另有PDF和600 dpi PNG。Notebook保留实际执行输出；交互页面回放预计算结果。修改配置后使用新目录保存输出与SHA-256清单，保留原结果作为对照。

## 方法参考

1. EnergyPlus 26.2, [Thermal Energy Storage example](https://energyplus.readthedocs.io/en/v26.2.0/guides/plant-application-guide/7-example-system-2-thermal-energy-storage.html)：储冷系统功能组织的参考。
2. EnergyPlus 26.2, [Water Thermal Tanks](https://energyplus.readthedocs.io/en/v26.2.0/guides/engineering-reference/19.3-water-thermal-tanks-includes-water-heaters.html)：多节点分层水罐建模机制。
3. SciPy 1.15.3, [milp](https://docs.scipy.org/doc/scipy-1.15.3/reference/generated/scipy.optimize.milp.html)：求解接口、状态与最优性字段。
4. Rawlings, Mayne, Diehl, [Model Predictive Control: Theory, Computation, and Design](https://sites.engineering.ucsb.edu/~jbraw/mpc/), 2nd ed.：滚动控制组织方式。
5. scikit-learn 1.6, [Ridge](https://scikit-learn.org/1.6/modules/generated/sklearn.linear_model.Ridge.html)：平方误差与L2正则化目标。
6. NREL, [ATB 2024 Equations and Variables](https://atb.nrel.gov/electricity/2024b/equations_%26_variables)：资本回收系数。

参考资料用于方法与定义核对。本章数值参数、数据和软件实验由作者方显式设定，相关网页未提供本章的现场数据或设备报价。权利沿用根目录 `RIGHTS.md`，无新增许可授权。
