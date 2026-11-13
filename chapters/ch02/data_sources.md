# 数据来源与公开数据接入

## 本章数据

数据性质：作者构造。12个电芯、每个160循环，参考容量2 A·h。latent_soh = 1 - a*n - b*max(n-knee,0)^2；每个电芯的a、b、knee列表位于run.py的generate函数。容量测量加入标准差0.004 A·h的高斯扰动；温度为25+2*sin(n/11+j)加标准差0.25 ℃的扰动；内阻为0.035+0.14*(1-latent_soh)+0.0002*(temperature-25)加标准差0.0005 Ω扰动。随机数种子为20261114+j，j为0—11。模型只读历史容量比例、内阻与温度，不读latent_soh。

source_kind恒为constructed。未以实测数据拟合生成器；结果只用于验证教学流程。

## NASA扩展入口

查阅日期：2026-11-14。

- 官方仓库：https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/
- 官方目录：https://data.nasa.gov/dataset/li-ion-battery-aging-datasets
- 目录许可字段：License not specified。本包不包含其原始数据。

接入时登记：下载URL、日期、文件SHA256、资料引用、授权/许可、化学体系、温度、充放电截止条件、额定或初始参考容量、设备标识。

循环结构中的type用来区分charge、discharge和impedance。Time以秒为单位；Current_measured需核实符号；Capacity按原资料口径解释，不能假设所有放电记录都可比。不要把原始结构数组序号直接当成等效完整循环数。

本章示例特征包括循环末的内阻指标，NASA的阻抗测量可能不与每次放电一一对应。实际适配需先规定时间对齐和可用性，不能从未来阻抗记录回填。若缺少这一特征，可建立容量历史单特征的新实验，并保持训练、选择和测试边界。此文件是接入协议，不代表已完成NASA训练。
