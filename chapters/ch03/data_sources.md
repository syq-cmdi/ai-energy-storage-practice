# 来源、版本与适用范围

数据：`run.py`生成的教学构造观测；随机种子20261114。无外部数据下载、无企业数据、无现场验证。

电压名义关系V=3.45+0.60 SOC−0.035I为人为选定的线性教学代理，不拟合任何电芯型号。温度名义状态以一阶递推响应I²，测量加入噪声、设备偏移和人工异常。内阻异常用附加电压降表示，冷却异常用温度残差表示，均不构成经验证电化学或热安全模型。测试组合异常同时改变电压A与温度；缺失场景通过删除电压A实现。

配置版本：本仓库第3章初稿，2026-11-14。参考数值环境Python3.12、NumPy2.3.5、SciPy1.15.3、scikit-learn1.6.1。浏览器读取冻结的测试分值，JavaScript重新计算告警和事件指标；不重新训练模型。

可复现性：manifest.json记录构造脚本与配置及分发文件SHA-256；运行完整实验另生成完整输出清单、模型与重载误差。哈希只证明文件一致性，不证明科学有效性。

## 方法资料（访问2026-11-14）

- [scikit-learn 1.6 数据泄漏与Pipeline](https://scikit-learn.org/1.6/common_pitfalls.html)
- [LogisticRegression](https://scikit-learn.org/1.6/modules/generated/sklearn.linear_model.LogisticRegression.html)
- [IsolationForest](https://scikit-learn.org/1.6/modules/generated/sklearn.ensemble.IsolationForest.html)
- [分类阈值选择](https://scikit-learn.org/1.6/modules/classification_threshold.html)
- [模型评估](https://scikit-learn.org/1.6/modules/model_evaluation.html)
- [Kim等：Towards a Rigorous Evaluation of Time-series Anomaly Detection](https://arxiv.org/abs/2109.05257)
- [模型保存](https://scikit-learn.org/1.6/model_persistence.html)

上述资料支撑算法接口和评估原则，不为本章构造参数或现场性能背书。七幅代码图由Python/Matplotlib及SVG生成，可编辑源文件随仓库提供。Word中另有AI生成教学场景图，标为概念示意，未作为真实接线图或实验照片使用。
