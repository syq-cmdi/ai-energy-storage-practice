# 第2章配套实验

本包以作者构造的教学电芯数据演示SOC误差与下一循环SOH预测。没有现场数据或NASA实测结果。完整数据由run.py生成，可检查每个参数与随机种子。默认无需联网或GPU；首次安装依赖需要网络。

## 运行

在本目录创建Python 3.12虚拟环境后执行：

```sh
python -m pip install -r requirements.txt
python run.py --out results/run_001
python verify.py
```

使用虚拟环境中的解释器；macOS/Linux路径为`.venv/bin/python`，Windows为`.venv\Scripts\python.exe`。本次实际测试平台记录在reference_results/manifest.json；Windows/Linux未实机验证。

相对输出路径按脚本所在目录解析，非空目录禁止覆盖。正常输出包括cycles.csv、soc.csv、predictions.csv、metrics.json、models.pkl和manifest.json。reference_results是本章作者实际运行记录；重新运行时使用新的results子目录。

## 实验合同

- 12个教学电芯，各160循环，5循环窗口，3个历史特征（容量比例、内阻、温度）。预测下一循环SOH。
- C01—C06训练；C07选择；C08校准经验误差带；C09—C12测试。设备集合互斥。
- 持久性、岭回归、随机森林与16隐藏单元窗口前馈网络；网络种子17、29、43，使用平均预测。
- 参数拟合仅使用训练集，超参数和模型族仅按C07误差选择。C08与测试集不参与选模。
- 经验误差带基于C08的90%绝对误差分位数。相关窗口和电芯分布差异使其不具备独立同分布假设下的覆盖保证。
- 模型文件含缩放器、特征顺序、配置和估计器；只从本地可信来源加载pickle。跨版本迁移需重新核验。
- RUL部分只生成观测阈值/删失标签；未实施长程寿命预测训练。

## 验证与复用

verify.py在新临时目录重跑实验，独立复算指标和SOC闭式结果，核对缩放器范围、分组、未来标签扰动不改变输入、保存重载一致性、经验覆盖和错误输入处理。结果写入verification_report.json。

本教学代码发布于 syq-cmdi/ai-energy-storage-practice。尚未授予开源再分发许可证；授权范围见仓库根目录 RIGHTS.md。

建议引用本地材料时注明：石玉琦. 储能系统人工智能实践 第2章配套教学实验. V1, 2026-11-14. 未出版教学材料。

## 图稿与课堂演示

仓库根目录 `demo/教学演示.html` 可离线打开；`plot_results.py` 从保存的CSV生成SVG、600 dpi PNG和PDF。先安装根目录 requirements-viz.txt，再执行绘图命令。课堂活动见 docs/课堂讲义.md。
