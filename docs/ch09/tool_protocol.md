# 只读工具协议 v1

请求必须且只能包含request_id（非空字符串）、tool（登记名称）、arguments（对象）。每个参数必须且只能包含value和unit。value为有限int/float，显式排除bool。输入支持Wh/kWh、W/kW、L/m3、kg/m3、kJ/(kg K)、温差K/degC及无量纲1。

energy_runtime：能量>0、功率>0、0≤soc_min≤soc≤1、0<eta≤1。water_sensible_heat：体积、密度、比热、温差均>0。现有参数范围对应教学任务，增补物理上界须根据对象重新定义并验证。

返回结果必须且只能包含value和unit，且量值为有限实数。返回与独立代数复算对比，rel_tol=abs_tol=1e-10。额外动作字段被拒绝。失败状态包括invalid_request、invalid_result、timeout、worker_error；结果只在ok状态提供。

每次尝试记录attempt、event、elapsed_s、parameter_sha256。实际请求保存在外层实验记录request中。故障注入通过执行器的独立fault参数控制，不来自检索文本；工具进程参数由白名单归一化后构造。

该实现使用显式校验函数，并非完整JSON Schema标准校验器。参考字段约束说明：https://json-schema.org/understanding-json-schema/reference/object 。两个工具均为只读计算，代码未接入设备控制。
