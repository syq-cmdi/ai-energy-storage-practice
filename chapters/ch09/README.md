# 第9章 储能运维知识助手

从自编规程到带出处回答，再到单位可校验的只读计算。16份文档、60道冻结题目、三种检索方法和13个工具情景均可离线运行。本章使用确定性模板组织回答，LSA向量由当前语料训练；开放式语言模型通过可选结构化主张接口接入，其线上性能留待接入后评测。

## 快速开始

在仓库根目录执行（Python 3.12，Node.js 24）：

```bash
python -m pip install -r requirements.txt
python chapters/ch09/run.py
python chapters/ch09/verify.py
python chapters/ch09/build_demo.py
node --test tests/ch09.test.cjs
```

直接打开 `demo/ch09/教学演示.html` 即可离线使用。可改写问题、改变设备与日期、调整k、比较BM25/TF–IDF/LSA、查看原文行号并导出JSON证据报告。计算页提供SOC滑块、电量与水体显热的实时可视化。故障页回放实际Python子进程运行记录。

```bash
python -m pip install -r requirements-viz.txt
python chapters/ch09/plot_results.py
```

Linux绘图可安装 `fonts-noto-cjk`；或通过 `--font /path/to/font.ttf` 指定合法取得的中文字体。图源导出SVG/PDF与600 dpi PNG。AI概念图独立登记来源，见 `docs/ch09/figure_provenance.md`。

Notebook `ch09_walkthrough.ipynb` 含6个已执行代码单元和实际图形输出。可在Jupyter环境中重跑（需IPython、nbformat及绘图依赖），请先选择本仓库的依赖环境。它从当前目录向上定位仓库根目录。

## 实验合同

- 语料、参数、对象及故障均由作者构造，使用与权利约定沿用仓库RIGHTS.md；没有企业运行数据。
- 任务字段明确给出asset、as_of、metric，教学身份固定class_a。自然语言text用于检索；开放式意图识别不在本次测量范围。
- 24道开发题选择LSA秩：4/8/12/20；按开发MRR@3、Recall@3和较小维数依次选取12。
- 36道测试题在选择配置写盘后运行。数据与参考标签先冻结哈希。题目共享设备、属性与语料，主要测量措辞变化。
- BM25参数k1=1.2、b=.75；字符单元与双字符共同构词；TF–IDF使用平滑IDF与L2归一化；LSA使用同一矩阵的截断SVD。
- 检索与回答代码不读取reference_labels.json。范围筛选在返回top-k前进行，支持检查使用目标属性、量值、单位、哈希与原文。
- 找到目标属性后，以有效范围的同属性索引补查冲突；该步骤不改变原始检索指标。
- 离线包包含全部**教学**语料，页面筛选展示权限逻辑。实际服务需在可信后端执行授权，避免向客户端传递未授权内容；全局索引统计量也应按授权域评估。

## 测量结果

| 方法 | Recall@3（30道有证据题） | MRR@3 | 状态正确率（36题） | 有据回答覆盖率 |
|---|---:|---:|---:|---:|
| BM25 | 86.67% | 75.00% | 88.89% | 66.67% |
| TF–IDF | 83.33% | 75.00% | 86.11% | 63.89% |
| LSA，12维 | 76.67% | 63.33% | 80.56% | 58.33% |

各自已回答主张的支持精确率为100%，分别回答24/23/21题，另各识别2题冲突。参考状态包含28题量值回答、2题冲突和6题证据不足。测试漏答保留在 `results/ch09/experiment.json`；不以局部指标概括部署状态。

工具样例：1000 kWh × (0.8−0.2) × .95 / 300 kW = 1.9 h；20 m³水体跨6 K的显热量为139.3333 kWh。13情景：4次有效结果、4次请求错误、4次结果错误、1次连续超时。注入延迟.35 s、故障轮期限.10 s，正常/恢复轮5 s，最多两次尝试。具体耗时随机器负载变化。

## 文件地图

- `core.py`：分块、范围、BM25/TF–IDF/LSA、模板回答、可选生成主张校验。
- `tools_readonly.py`：严格字段与量纲校验、两个代数工具、独立子进程及有限重试。
- `run.py`：冻结检查、开发选择、测试与13情景实验账本。
- `verify.py`：252项行为与数据校验；包含37块出处位置、范围、反例与数值边界。
- `engine.js`：浏览器实时检索与计算纯函数；Node检查180组Python/JS一致性。
- `build_demo.py` / `demo_template.html`：自包含离线页面；原文显示进行HTML转义。
- `data/`：语料清单、原文、任务、独立参考标签及冻结哈希。
- `results_reference.json`：版本化的配置与参考指标；完整实验账本由run.py生成。

精确引用：石玉琦. 储能系统人工智能实践：第9章储能运维知识助手（教学代码）. 2026. https://github.com/syq-cmdi/ai-energy-storage-practice/tree/main/chapters/ch09 。复用时补充实际使用的提交SHA。
