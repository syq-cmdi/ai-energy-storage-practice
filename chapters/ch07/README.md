# 第7章 混合快速储能的功率分配

电池与超级电容通过共享物理环境比较低通规则、单步约束优化和表格Q学习。全部输入为教学构造数据。当前基准以低通规则取得较低的综合代价，完整保留优化与学习的库存偏移、残差及种子差异。

## 快速运行

在仓库根目录执行（Python 3.12，Node 24用于网页内核测试）：

```bash
python -m pip install -r requirements-viz.txt
python chapters/ch07/run.py
python chapters/ch07/verify.py
python chapters/ch07/plot_results.py
python chapters/ch07/draw_diagrams.py
python chapters/ch07/build_demo.py
node --test tests/ch07.test.cjs
```

运行会重新训练5个种子，每个250回合×300 s；按5条验证输入选检查点，再用15条独立测试输入×4场景评测，共420条轨迹。默认写入results/ch07。可用`--out`指定新的结果目录；后续绘图、验证与网页构建接受`--source <目录>/experiment.json`。

直接双击[离线演示](../../demo/ch07/教学演示.html)，可调时间常数、初始能量和需求幅值，切换4个场景与3个控制器，播放/单步/拖动时间，导出CSV和SVG。参数改变时Q表保持冻结。顶部指标汇总全部600 s，光标数值表示当前步。网页无需服务器、CDN或外部字体。

## 教学资产

- [已执行Notebook](ch07_walkthrough.ipynb)：单位手算、环境调用、三类策略、独立能量核验、彩图与参数实验。
- [课堂练习](teaching_handout.md)：观察问题、实验步骤与预期输出。
- [数据字典](data_dictionary.md)、[模型说明](model_card.md)、[来源](data_sources.md)。
- reference_results/：参考评价表、5个冻结Q表、训练日志、代表轨迹及验证结果；完整事件表由run.py生成。
- assets/ch07/：8幅可重绘原理图与定量图，每幅SVG、PDF、600 dpi PNG。

中文绘图需要本机合法字体；Linux可安装fonts-noto-cjk，或在绘图命令中通过`--font 字体路径`指定。字体文件随本机加载，不随仓库分发。Notebook另需Jupyter与IPython。

## 结果解释

标称场景平均残差RMSE：低通0.000、单步优化1.855、Q学习3.129 kW。电池吞吐量分别3.395、2.615、4.316 kWh；电容端点偏移分别−0.009、−0.408、−0.232 kWh。规则与优化各15条运行，Q学习5×15条。图7.8按输入种子配对，Q学习在同一输入内先对5个训练种子求均值。

端点为自由库存。吞吐量用于运行负担比较；寿命评价需要额外退化模型与老化数据。约束投影次数、执行后的物理越限与剩余需求分别报告。420次既定测试的物理越限步数为0，过载场景保留残差；额外负向测试主动触发爬坡—库存冲突。

独立核验包括逐时母线平衡、效率与库存账、165组随机可行状态的优化器交叉检查，以及500 kW请求残差390 kW反例。网页内核15项测试覆盖12组逐点Python/JavaScript对照、参数变化、导出与单文件打包。

版本：ch07-v1，2026-11-14。作者：石玉琦。代码与本章自建合成数据沿用仓库LICENSE。引用本教学资产可使用：石玉琦. AI储能实践代码：第7章混合快速储能的功率分配[CP/OL]. 2026. https://github.com/syq-cmdi/ai-energy-storage-practice/tree/main/chapters/ch07 （复现时补充实际commit SHA）。
