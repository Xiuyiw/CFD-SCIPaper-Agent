# 可复用机制与反模式目录

日期：2026-09-01
输入：[`05_CROSS_PROJECT_COMPARISON.md`](05_CROSS_PROJECT_COMPARISON.md)、23份深读报告与
[`01_CURRENT_PRODUCT_BASELINE.md`](01_CURRENT_PRODUCT_BASELINE.md)
用途：为Task 8–9提供可追溯候选，不提前冻结V0.3范围

## 1. 使用规则

- 迁移类别只使用`direct reuse`、`reimplement`、`idea-only`和`reject`。
- “进入版本建议”是后续设计输入，不是已批准路线图；Task 9仍需按最小纵向切片取舍。
- 开源来源定位到固定commit与类/函数/测试；商业来源仅支持UX层`idea-only`，不推断内部架构。
- 历史回归只引用公开基线中已经抽象的模式，不读取或暴露私有项目资产。
- 目录只保留能改善真实CFD论文生产的机制；没有独立收益的治理对象不进入建议。

## 2. 机制目录

### S01 自描述CFD字段与范围对象

- **资源类别：** 科学理解与分析。
- **目标问题：** 裸数组无法说明变量、空间关联、zone/phase、单位和来源，易在后处理中错配。
- **来源与精确定位：** [PyDPF-Core](04_DEEP_DIVE_REPORTS/open-source/ansys__pydpf-core.md)：
  `field.py::Field`、`field_definition.py::FieldDefinition`、`fields_container.py::FieldsContainer`；
  [PyVista](04_DEEP_DIVE_REPORTS/open-source/pyvista__pyvista.md)：
  `pyvista/core/dataset.py::DataSet`、`datasetattributes.py::DataSetAttributes`；
  [xarray](04_DEEP_DIVE_REPORTS/open-source/pydata__xarray.md)：`DataArray`/`Dataset`。
- **迁移类别：** `reimplement`。
- **许可证：** PyDPF MIT、PyVista MIT、xarray Apache-2.0；借鉴对象结构，不复制供应商服务层。
- **适配条件：** 字段必须显式记录case、variable、association/location、scope、原始/规范单位和source locator。
- **预期收益：** 降低point/cell、zone、phase和case混用造成的硬错误。
- **开发成本：** 中；需连接现有Case/Evidence/QoI对象和适配器输出。
- **风险：** metadata齐全仍不代表收敛、可比或物理定义正确。
- **验证方式：** 公开小型fixture覆盖错location、错zone、缺单位、跨case混用和序列化往返。
- **进入版本建议：** `conditional enabler`。
- **历史回归对应：** 基线§6“派生数据必须记录算子”和“先证实可比性”。

### S02 命名坐标的严格对齐与显式缺失策略

- **资源类别：** 科学理解与分析。
- **目标问题：** 依靠数组位置拼接多case/多截面数据，会静默产生错位或把缺失当成零。
- **来源与精确定位：** [xarray](04_DEEP_DIVE_REPORTS/open-source/pydata__xarray.md)：
  `xarray/structure/alignment.py::Aligner`、`concat.py::concat`、`combine.py::combine_by_coords`。
- **迁移类别：** `direct reuse`。
- **许可证：** Apache-2.0；需选择兼容Python 3.10–3.12的稳定版本。
- **适配条件：** 默认`join="exact"`；QoI契约声明允许的fill/skipna行为；组合前先过工况可比性门。
- **预期收益：** 使case、section、time和variable缺失显性失败，而非生成貌似平滑的趋势。
- **开发成本：** 中；需定义坐标词典和NetCDF/CSV往返约束。
- **风险：** xarray自动broadcast、outer alignment或默认`skipna`仍可能掩盖错误。
- **验证方式：** 打乱坐标顺序、删除case/截面、重复标签、不同采样网格和NaN负向测试。
- **进入版本建议：** `conditional enabler`。
- **Internal regression relevance：** `authorized internal negative scientific-gate regression` 中的错误聚合与缺失数据包装。

### S03 单位感知的QoI计算

- **资源类别：** 科学理解与分析。
- **目标问题：** 单位后缀、人工换算和无量纲化基准容易漂移，量纲错误可能直到写作阶段才暴露。
- **来源与精确定位：** [Pint](04_DEEP_DIVE_REPORTS/open-source/hgrecco__pint.md)：
  `pint/registry.py::UnitRegistry`、`PlainQuantity.to/ito`、NumPy facet的`__array_ufunc__`。
- **迁移类别：** `direct reuse`。
- **许可证：** BSD-3-Clause；固定兼容目标Python矩阵的版本。
- **适配条件：** 保存原始值/单位、规范值/单位和转换；数组接口剥离单位时必须失败或显式确认。
- **预期收益：** 低成本阻断不相容量纲、错误换算和跨case单位混用。
- **开发成本：** 低至中。
- **风险：** 量纲正确不等于控制体、面积、平均方式或参考态正确。
- **验证方式：** 转换、量纲冲突、offset单位、NaN、数组剥离、序列化回放测试。
- **进入版本建议：** `conditional enabler`。
- **历史回归对应：** 基线§6“先统一量纲再比较”，但不得把通过单位检查视为科学批准。

### S04 有范围、可回放的科学算子链

- **资源类别：** 科学理解与分析。
- **目标问题：** 积分、平均、采样和归一化若只保存最终值，无法复核其控制体、权重和输入字段。
- **来源与精确定位：** [PyDPF-Core](04_DEEP_DIVE_REPORTS/open-source/ansys__pydpf-core.md)：
  `workflow.py::Workflow.connect/get_output/set_output_name`及typed operator pins；
  [PyVista](04_DEEP_DIVE_REPORTS/open-source/pyvista__pyvista.md)：`DataSetFilters.integrate_data`。
- **迁移类别：** `reimplement`。
- **许可证：** MIT来源；仅重实现轻量、求解器无关的算子描述。
- **适配条件：** 每个算子声明输入字段、scope、location、weights、missing policy、单位与输出QoI。
- **预期收益：** 派生量能回到明确算子与来源，便于复算和交叉适配器一致性检查。
- **开发成本：** 中。
- **风险：** 过度构建通用DAG会把资源拉回编排；只实现实际QoI所需的最小算子集。
- **验证方式：** 同一公开QoI在CSV/VTK/可选原生adapter间数值、单位、scope一致。
- **进入版本建议：** `conditional enabler`。
- **历史回归对应：** 基线§5.2显示量、严格物理量、派生指标和辅助诊断分离。

### S05 工况可比性先于数值组合

- **资源类别：** 科学理解与分析。
- **目标问题：** 相同变量名或单位并不保证几何、材料、边界、模型、采样和参考态可比。
- **来源与精确定位：** [跨项目比较§3.2](05_CROSS_PROJECT_COMPARISON.md)：Pint/xarray/SALib均不
  判断完整CFD可比性；[产品基线§6](01_CURRENT_PRODUCT_BASELINE.md)“先证实可比性，再解释差异”。
- **迁移类别：** `reimplement`。
- **许可证：** 本项目原创连接机制；不复制外部代码。
- **适配条件：** 以Boundary/Mesh/Physics/Sampling/QoI版本形成显式比较合同，差异分为允许、需解释和阻断。
- **预期收益：** 在趋势、图件和写作之前阻止不可辩护的case比较。
- **开发成本：** 中至高，需领域可扩展规则而非燃烧器专用字段。
- **风险：** 规则过硬会误拒绝合理比较；规则过松会复现内部负向科学门回归已暴露的错误。
- **验证方式：** 单相内流、换热、瞬态/多相fixture分别覆盖允许差异与阻断差异。
- **进入版本建议：** `V0.3 minimum-slice must-consider`。
- **Internal regression relevance：** `authorized internal negative scientific-gate regression` 的首要阻断点。

### S06 QoI定义合同

- **资源类别：** 科学理解与分析。
- **目标问题：** 同名指标可能使用不同控制体、统计窗口、权重、基准和聚合算子。
- **来源与精确定位：** [SALib](04_DEEP_DIVE_REPORTS/open-source/SALib__SALib.md)：
  `ProblemSpec`绑定problem/samples/results/analysis；[xarray](04_DEEP_DIVE_REPORTS/open-source/pydata__xarray.md)
  命名dims/coords；[产品基线§5.2](01_CURRENT_PRODUCT_BASELINE.md)的figure/analysis证据链。
- **迁移类别：** `reimplement`。
- **许可证：** 本项目原创合同；外部MIT/Apache机制仅作参考。
- **适配条件：** QoI必须声明公式、输入、单位、scope、统计窗口、weights、normalization、missing policy和版本。
- **预期收益：** 同一数值可以被准确解释、复算并传播到图表和正文。
- **开发成本：** 中。
- **风险：** 将合同写成大量治理字段；只保留会改变数值含义的字段。
- **验证方式：** 同名不同定义、分箱均值冒充原始点、加权/未加权、不同参考值的负向fixture。
- **进入版本建议：** `V0.3 minimum-slice must-consider`。
- **历史回归对应：** 基线§6“派生数据必须记录算子”。

### S07 全序列趋势与峰值判定

- **资源类别：** 科学理解与分析。
- **目标问题：** 端点改善、图形印象或平滑曲线常被误写成逐点单调、全域规律或连续最优区。
- **来源与精确定位：** [产品基线§6](01_CURRENT_PRODUCT_BASELINE.md)“趋势词必须计算验证”；
  [SALib报告§6](04_DEEP_DIVE_REPORTS/open-source/SALib__SALib.md)警示非设计离散工况的错误推断；
  [Matplotlib报告§6](04_DEEP_DIVE_REPORTS/open-source/matplotlib__matplotlib.md)的平滑/轴尺度风险。
- **迁移类别：** `reimplement`。
- **许可证：** 本项目原创规则与算法。
- **适配条件：** 只在完整、有序、同定义序列上计算；区分monotonic、overall change、peak、plateau和insufficient。
- **预期收益：** 让论文趋势措辞与真实离散证据一致。
- **开发成本：** 低至中。
- **风险：** 容差、噪声和采样稀疏会改变分类；必须由分析计划声明。
- **验证方式：** 反转中间点、平台、缺点、重复横坐标、噪声容差和非均匀采样fixture。
- **进入版本建议：** `V0.3 minimum-slice must-consider`。
- **Internal regression relevance：** `authorized internal negative scientific-gate regression` 对错误单调趋势的直接回放。

### S08 收敛与守恒证据资格

- **资源类别：** 科学理解与分析。
- **目标问题：** 单一残差或单一监测量趋稳被包装成“结果已收敛”，随后进入论文主张。
- **来源与精确定位：** [产品基线§6](01_CURRENT_PRODUCT_BASELINE.md)“弱收敛不能包装为完成”；
  [跨项目比较§3.2](05_CROSS_PROJECT_COMPARISON.md)确认外部算法库不承担这一综合判断；
  [NASA Glenn CFD V&V tutorial](https://www.grc.nasa.gov/www/wind/valid/tutorial/tutorial.html)基于
  AIAA G-077，分别组织 iterative convergence、solution consistency/conservation、spatial/temporal
  convergence、verification assessment 与 validation assessment。
- **迁移类别：** `reimplement`。
- **许可证：** 本项目原创科学门控。
- **适配条件：** 按项目声明残差、关键监测量、守恒闭合、稳态/统计窗口和缺失证据处理。
- **预期收益：** 缺失或弱收敛时自动降级为受限分析/缺口，而非完整论文claim。
- **开发成本：** 中至高；需稳态/瞬态、多相等不同策略。
- **风险：** 不同求解器与物理问题阈值不能硬编码为一套数字。
- **验证方式：** 残差好但守恒差、监测量稳但窗口短、瞬态未达统计稳定、证据缺失fixture。
- **进入版本建议：** `V0.3 minimum-slice must-consider`。
- **Internal regression relevance：** `authorized internal negative scientific-gate regression` 对弱收敛证据被错误晋升的阻断要求。

### S09 设计约束的敏感性分析

- **资源类别：** 科学理解与分析。
- **目标问题：** 把普通离散参数扫描直接送入全局敏感性算法，会产生形式完整但不可辩护的指数。
- **来源与精确定位：** [SALib](04_DEEP_DIVE_REPORTS/open-source/SALib__SALib.md)：
  `ProblemSpec`、`sample/sobol.py::sample`、`analyze/sobol.py::analyze`及输出长度检查。
- **迁移类别：** `direct reuse`（条件性可选引擎）。
- **许可证：** MIT。
- **适配条件：** 设计矩阵、case映射、QoI版本、单位、缺失值和样本长度全部通过后才启用。
- **预期收益：** 在证据确实满足设计时提供成熟敏感性算法和置信区间。
- **开发成本：** 中。
- **风险：** 用户把“敏感性”作为任何参数扫描的通用标签；默认应拒绝而非近似替代。
- **验证方式：** 正确设计、错序结果、缺case、常量输出、NaN和非设计扫描负向测试。
- **进入版本建议：** `defer to V0.4+`。
- **历史回归对应：** 保护离散筛选不被外推为连续规律。

### S10 Evidence到claim ceiling的单向传播

- **资源类别：** 科学理解与分析。
- **目标问题：** 检索、脚本、图件或阶段状态完成后，系统容易把结果自动提升为更强结论。
- **来源与精确定位：** [PaperQA2§6](04_DEEP_DIVE_REPORTS/open-source/Future-House__paper-qa.md)
  “引用存在不等于claim被支持”；[data-to-paper§6](04_DEEP_DIVE_REPORTS/open-source/Technion-Kishony-lab__data-to-paper.md)
  “完整流程不保证CFD前提”；[产品基线§2、§6](01_CURRENT_PRODUCT_BASELINE.md)。
- **迁移类别：** `reimplement`。
- **许可证：** 本项目原创科学授权机制。
- **适配条件：** claim只读锁定Evidence/QoI；写作、图件和外部AI不能提高证据等级；缺口使claim降级。
- **预期收益：** 防止漂亮产物、引用链接和状态字段制造虚假科学确定性。
- **开发成本：** 中。
- **风险：** 若实现为复杂promotion registry会恢复V1过度治理；保持少量明确状态与作者决定。
- **验证方式：** 文件存在、引用存在、图导出、审查通过等事件均不能自行提升claim的负向测试。
- **进入版本建议：** `V0.3 minimum-slice must-consider`。
- **Internal regression relevance：** `authorized internal negative scientific-gate regression` 的虚假批准教训，以及 `authorized internal positive regression` 的跨文件主张传播经验。

### S11 显示量、派生量与严格物理量分层

- **资源类别：** 科学理解与分析。
- **目标问题：** 云图显示、局部样本、代理指标和严格积分量被混写，造成物理含义和主张强度错位。
- **来源与精确定位：** [PyVista§6](04_DEEP_DIVE_REPORTS/open-source/pyvista__pyvista.md)区分filter输出与物理结论；
  [产品基线§5.2](01_CURRENT_PRODUCT_BASELINE.md)明确显示量、严格物理量、派生指标和辅助诊断分开。
- **迁移类别：** `reimplement`。
- **许可证：** 本项目原创科学语义层。
- **适配条件：** 每个量声明measure class、operator、scope和允许的claim角色；写作使用对应术语模板而非自由升级。
- **预期收益：** 防止局部species、采样峰值、近似换算或视觉强度承担整体性能结论。
- **开发成本：** 中。
- **风险：** 分类过细会增加作者负担；仅覆盖会改变解释的类别。
- **验证方式：** 同一字段构造显示图、局部采样、积分QoI和辅助指标，检查其允许表述不同。
- **进入版本建议：** `conditional enabler`。
- **Internal regression relevance：** `authorized internal positive regression` 中的图件—指标—正文边界。

### PW01 FigureContract先于绘图

- **资源类别：** 科研绘图与写作。
- **目标问题：** 先画图再解释会造成图型、指标和论文主张不匹配。
- **来源与精确定位：** [Matplotlib](04_DEEP_DIVE_REPORTS/open-source/matplotlib__matplotlib.md)：
  `Figure.savefig`/`print_figure`与SVG/PDF后端；[PyVista](04_DEEP_DIVE_REPORTS/open-source/pyvista__pyvista.md)：
  `BasePlotter.save_graphic`；[产品基线§5.2](01_CURRENT_PRODUCT_BASELINE.md)的figure contract证据链。
- **迁移类别：** `reimplement`。
- **许可证：** Matplotlib License、PyVista MIT；绘图引擎复用，合同由本项目实现。
- **适配条件：** 合同先锁科学问题、case、source data、变量/单位、panel角色、主张上限和输出格式。
- **预期收益：** 图件直接服务论文论证，避免普通dashboard和后补解释。
- **开发成本：** 中。
- **风险：** 合同变成冗长表单；只要求影响科学读法和交付的字段。
- **验证方式：** 合同—source data—脚本—图注—正文引用一致性测试。
- **进入版本建议：** `V0.3 minimum-slice must-consider`。
- **Internal regression relevance：** `authorized internal positive regression` 中复杂图件形成的首要成功模式。

### PW02 数据、叙事与视觉三重QA

- **资源类别：** 科研绘图与写作。
- **目标问题：** 渲染成功或套用期刊样式不能发现错误数值、误导图型、遮挡和图文冲突。
- **来源与精确定位：** [SciencePlots§6、§13](04_DEEP_DIVE_REPORTS/open-source/garrettj403__SciencePlots.md)；
  [Matplotlib§6、§13](04_DEEP_DIVE_REPORTS/open-source/matplotlib__matplotlib.md)；
  [产品基线§5.2](01_CURRENT_PRODUCT_BASELINE.md)。
- **迁移类别：** `reimplement`。
- **许可证：** 本项目QA；底层绘图依赖沿用各自许可证。
- **适配条件：** 数据QA重算关键读数；叙事QA检查panel与claim；视觉QA检查bbox、字体、legend、色标和人工预览。
- **预期收益：** 同时降低科学硬错、AI式图件和基础排版错误。
- **开发成本：** 中。
- **风险：** 视觉QA无限循环；每图一轮程序检查加一轮作者预览，发现实质问题才重开。
- **验证方式：** 故意注入错单位、错case、缺source row、裁切、遮挡和caption错序fixture。
- **进入版本建议：** `V0.3 minimum-slice must-consider`。
- **历史回归对应：** 图件“越改越乱”与仅视觉美化失败的反向经验。

### PW03 来源优先的文献证据工作区

- **资源类别：** 科研绘图与写作。
- **目标问题：** 文献摘要、生成列或引用链接直接进入正文，缺少原文定位、角色和作者判断。
- **来源与精确定位：** [PaperQA2](04_DEEP_DIVE_REPORTS/open-source/Future-House__paper-qa.md)：
  `Docs.aadd`、`PQASession`引用映射；[Elicit§2、§5](04_DEEP_DIVE_REPORTS/commercial-public-workflows/product__elicit.md)；
  [SciSpace§4](04_DEEP_DIVE_REPORTS/commercial-public-workflows/product__scispace.md)；
  [scite§5–6](04_DEEP_DIVE_REPORTS/commercial-public-workflows/product__scite.md)。
- **迁移类别：** `reimplement`。
- **许可证：** PaperQA2 Apache-2.0；商业UX只作idea-only。
- **适配条件：** 先结构化过滤项目/版本/文献角色，再全文检索；答案必须链接原文locator并由作者纳入/排除。
- **预期收益：** 提高文献角色准确性和引用可定位性，减少“有引用但不支持”。
- **开发成本：** 中至高。
- **风险：** 语义召回与商业分类被误当证据；embedding只能用于找材料。
- **验证方式：** 相互矛盾、范围不一致、撤稿、无DOI和错误版本文献fixture。
- **进入版本建议：** `defer to V0.4+`。
- **Internal regression relevance：** `authorized internal positive regression` 中手工核对引用角色、并将外部 AI 意见回到原文的经验。

### PW04 Paper spine、阶段产物与数值反链

- **资源类别：** 科研绘图与写作。
- **目标问题：** 分节写作脱离分析结果，数字无法回到source data，章节功能重复或结论越界。
- **来源与精确定位：** [data-to-paper](04_DEEP_DIVE_REPORTS/open-source/Technion-Kishony-lab__data-to-paper.md)：
  `HypothesisTestingStepsRunner`、`ReferencedValue/find_numeric_values`；
  [STORM](04_DEEP_DIVE_REPORTS/open-source/stanford-oval__storm.md)：`StormInformationTable`与文章树。
- **迁移类别：** `reimplement`。
- **许可证：** 两者MIT；仅重实现适合成熟CFD证据的窄机制。
- **适配条件：** 作者批准paper spine；每段claim绑定Evidence/QoI/Figure；数值从锁定记录渲染而非手工复制。
- **预期收益：** 形成“发现—证据—机制—工程含义”的连贯论文，并降低跨章节数值漂移。
- **开发成本：** 高。
- **风险：** 自动并行写作制造长而空泛的文本；写作阶段不得发明研究问题或修改锁定证据。
- **验证方式：** `authorized internal positive regression` 检查数值、术语、图号与 claim 传播；外部盲审检查自然学术语言。
- **进入版本建议：** `V0.3 minimum-slice must-consider`。
- **范围限定：** 只候选一个受证据约束的文本产物；完整paper spine延期。
- **Internal regression relevance：** `authorized internal positive regression` 中逐节写作与跨文件传播的核心正向资产。

### PW05 真实文档导出、损失披露与页面预览

- **资源类别：** 科研绘图与写作。
- **目标问题：** Markdown草稿、可打开DOCX或编译PDF被误当投稿级交付；动态引用、公式、图表和分页可能静默损坏。
- **来源与精确定位：** [Quarto](04_DEEP_DIVE_REPORTS/open-source/quarto-dev__quarto-cli.md)：
  `renderPandoc`、`docxFormat`、`manuscriptRenderer`；
  [python-docx](04_DEEP_DIVE_REPORTS/open-source/python-openxml__python-docx.md)：`Document`、`save`；
  [Jenni§5](04_DEEP_DIVE_REPORTS/commercial-public-workflows/product__jenni.md)与
  [Overleaf§5](04_DEEP_DIVE_REPORTS/commercial-public-workflows/product__overleaf.md)的公开损失/产物分层。
- **迁移类别：** `direct reuse`（Quarto CLI和python-docx作为可选后端）。
- **许可证：** Quarto MIT核心、python-docx MIT；商业流程不复制实现。
- **适配条件：** 科学内容冻结后导出；预先声明不支持对象；回读OOXML/LaTeX结构并渲染PDF逐页检查。
- **预期收益：** 产出真实DOCX/LaTeX/PDF和可移植投稿包，而非仅Markdown。
- **开发成本：** 中至高。
- **风险：** 工具链体积、字体/TeX差异、Zotero域和修订保真。
- **验证方式：** 含公式、图表、引用、批注、分节和动态域的公开fixture往返及页面比较。
- **进入版本建议：** `defer to V0.4+`。
- **Internal regression relevance：** `authorized internal positive regression` 中最终 Word/PDF 逐页 QA 与版本混淆教训。

### AU01 分层的求解器适配器

- **资源类别：** 适配与易用性。
- **目标问题：** 普通用户不能手工把每个求解器结果重构成统一证据，但通用转换又容易丢求解器语义。
- **来源与精确定位：** [PyVista](04_DEEP_DIVE_REPORTS/open-source/pyvista__pyvista.md)：`read`及DataSet；
  [PyDPF-Core](04_DEEP_DIVE_REPORTS/open-source/ansys__pydpf-core.md)：`DataSources`、`Model`、`ResultInfo`；
  [xarray](04_DEEP_DIVE_REPORTS/open-source/pydata__xarray.md)：`BackendEntrypoint`/`list_engines`。
- **迁移类别：** `reimplement`。
- **许可证：** MIT/Apache-2.0；PyDPF作为可选供应商adapter，不成为核心依赖。
- **适配条件：** 统一`probe → inventory → extract(request)`；原始结果只读；缺字段保持缺失并给最低人工导出建议。
- **预期收益：** 降低跨求解器接入成本，同时保留变量、location、zone和来源。
- **开发成本：** 高，按CSV/VTK优先、原生adapter分阶段。
- **风险：** “能读取”被宣传成“理解求解器/科学有效”；必须把语义资格留给科学层。
- **验证方式：** 至少两种求解器或求解器+中性格式的同QoI一致性与缺失字段合同测试。
- **进入版本建议：** `conditional enabler`。
- **Internal regression relevance：** `authorized internal negative scientific-gate regression` 表明只回传文件清单不足，也不能把对象存在当科学证据。

### AU02 渐进披露、可测试的内置Skill包

- **资源类别：** 适配与易用性。
- **目标问题：** 全部科研规则塞入长系统提示词，触发不准、上下文膨胀、跨宿主不可移植且无法回归。
- **来源与精确定位：** [OMF Skills](04_DEEP_DIVE_REPORTS/open-source/openmodelingfoundation__skills.md)：
  `docs/SKILL-TEMPLATE.md`、`skills/peer-review/SKILL.md`、`evals.json`、validators；
  [OpenSkill](04_DEEP_DIVE_REPORTS/open-source/vudknguyen__openskill.md)：`discoverSkills`、宿主adapter与安装回滚。
- **迁移类别：** OMF Skills 的包结构、渐进披露和 eval 机制为`reimplement`；OpenSkill 的跨宿主
  路径与失败回退仅为`idea-only`。
- **许可证：** 两者MIT；不复制无关Skill正文或建设marketplace。
- **适配条件：** Level 1元数据、Level 2工作流、Level 3按需scripts/references/templates；每Skill有正/负/对抗eval、依赖探测和回退。
- **预期收益：** 只在需要时加载专业方法，提升跨宿主可用性并减少全局规则噪声。
- **开发成本：** 中。
- **风险：** Skill数量堆积或安装状态被误当科学质量；采用shrink-to-fit和真实任务回放。
- **验证方式：** 跨Codex/Claude/其他宿主解析、错误触发、工具缺失、证据不足和正常任务fixture。
- **进入版本建议：** `conditional enabler`。
- **Internal regression relevance：** 将 `authorized internal positive regression` 经验转化为 gotcha/template，将 `authorized internal negative scientific-gate regression` 失败转化为 adversarial eval。

### RP01 版本化、本地优先的检索上下文

- **资源类别：** 必要可靠性、溯源与作者权限。
- **目标问题：** 换任务/电脑/模型后召回旧文件或错误版本，语义相似内容压过权威证据。
- **来源与精确定位：** [PaperQA2](04_DEEP_DIVE_REPORTS/open-source/Future-House__paper-qa.md)：
  内容哈希、manifest、崩溃恢复索引；[LlamaIndex](04_DEEP_DIVE_REPORTS/open-source/run-llama__llama_index.md)：
  `BaseNode.ref_doc_id`、`IngestionPipeline` cache key、metadata filters、`StorageContext.persist`。
- **迁移类别：** `reimplement`。
- **许可证：** Apache-2.0与MIT；窄实现于现有SQLite/FTS，不引入完整RAG框架。
- **适配条件：** 结构化项目/case/version过滤先于FTS与可选embedding；文件变化使旧索引stale。
- **预期收益：** 可靠恢复正确版本的有限上下文，减少长聊天和版本混用。
- **开发成本：** 中。
- **风险：** 检索平台膨胀；embedding绝不能证明数值或claim。
- **验证方式：** 同名多版本、删除/替换文件、跨电脑恢复、关闭embedding和过期索引负向测试。
- **进入版本建议：** `conditional enabler`。
- **Internal regression relevance：** `authorized internal positive regression` 中权威文件锁定与多轮版本混淆的直接经验。

### RP02 可恢复阶段与真实作者中断

- **资源类别：** 必要可靠性、溯源与作者权限。
- **目标问题：** 中断后重复工作，或执行器用状态字段冒充作者已批准。
- **来源与精确定位：** [LangGraph](04_DEEP_DIVE_REPORTS/open-source/langchain-ai__langgraph.md)：
  `BaseCheckpointSaver`、`Pregel.get_state_history/update_state`、`interrupt`、`Command(resume=...)`；
  [Overleaf§7](04_DEEP_DIVE_REPORTS/commercial-public-workflows/product__overleaf.md)的审阅角色UX。
- **迁移类别：** `reimplement`。
- **许可证：** LangGraph MIT；商业UX仅作idea-only。
- **适配条件：** 现有SQLite保存阶段父链和输入版本；作者检查点必须绑定真实身份、动作和所批对象。
- **预期收益：** 跨任务恢复而不重做，并防止系统自封批准。
- **开发成本：** 中。
- **风险：** 复制完整图运行时或新增多层审批；只保留项目恢复和三个作者检查点。
- **验证方式：** 崩溃恢复、输入变更失效、错误身份、状态报告伪装批准和重复执行测试。
- **进入版本建议：** `conditional enabler`。
- **Internal regression relevance：** `authorized internal negative scientific-gate regression` 中虚假 `master acceptance`，以及 `authorized internal positive regression` 中真实作者确认模式。

## 3. 资源分配核对

候选机制数量只反映Task 7目录覆盖范围，不表示工时、权重或实现份额。
55/25/10/10是Task 9组合最终最小纵向切片时的目标资源约束，与本目录的机制数量不做换算。

| 资源类别 | 机制 | 候选机制数量 | Task 9组合级目标资源份额 |
|---|---|---:|---:|
| 科学理解与分析 | S01–S11 | 11 | 55% |
| 科研绘图与写作 | PW01–PW05 | 5 | 25% |
| 适配与易用性 | AU01–AU02 | 2 | 10% |
| 必要可靠性、溯源与作者权限 | RP01–RP02 | 2 | 10% |
| **合计** | 20项 | 20 | **100%** |

标记为`V0.3 minimum-slice must-consider`的机制只构成一条Task 9候选链，不在Task 7
冻结路线图：`S05 + S08 → S06 + S07 → S10 → PW01 + PW02 → PW04最小文本产物`。
该链依次表示证据资格与工况可比性、QoI定义与全序列趋势、claim ceiling、
FigureContract与三重QA，以及至少一个受证据约束的产物。Task 9必须在这条链上
做最小化取舍，而不是将八项机制全部实现。

该份额只约束Task 9最终选定的最小纵向切片：科学与绘图写作合计80%，可靠性/治理严格为10%。没有为安全审计、registry、评分仪表盘或多层审批
单独分配资源；它们只在能够阻止真实错误或恢复任务的两个机制中保留必要部分。

## 4. 反模式目录

| ID | 反模式 | 证据与精确定位 | 为什么拒绝 | 产品响应 |
|---|---|---|---|---|
| AP01 | README驱动的虚假完成 | [方法§8](02_BENCHMARK_METHOD.md)；[OMF Skills§9](04_DEEP_DIVE_REPORTS/open-source/openmodelingfoundation__skills.md)区分Alpha路线图与实现 | 愿景、文件名或示例不能证明发布路径和科学能力 | 只接受固定版本代码/测试/官方可观察工作流；其余标`not verified` |
| AP02 | 文件存在即证据 | [产品基线§2、§6](01_CURRENT_PRODUCT_BASELINE.md)；[python-docx§6](04_DEEP_DIVE_REPORTS/open-source/python-openxml__python-docx.md) | DOCX、报告、图或脚本存在不能证明内容、来源、收敛或作者批准 | 文件只进入inventory；EvidenceRecord资格由来源、科学门和作者动作决定 |
| AP03 | 无限自动研究与自我复评 | [STORM§12–13](04_DEEP_DIVE_REPORTS/open-source/stanford-oval__storm.md)；[data-to-paper§6、§12](04_DEEP_DIVE_REPORTS/open-source/Technion-Kishony-lab__data-to-paper.md) | 生成更多问题/文字不会修复不可比case或缺失证据，并可能放大错误叙事 | 真实外部事件驱动；候选/检索达到机制饱和即停；返修仅由真实审稿触发 |
| AP04 | 长系统提示词代替Skill | [OMF Skills§3–9](04_DEEP_DIVE_REPORTS/open-source/openmodelingfoundation__skills.md)；[OpenSkill§3–8](04_DEEP_DIVE_REPORTS/open-source/vudknguyen__openskill.md) | 上下文膨胀、触发不准、资源不可发现、无法跨宿主测试 | 三级渐进披露、shrink-to-fit、正/负/对抗eval和工具缺失回退 |
| AP05 | 无source data的漂亮图 | [SciencePlots§6、§12](04_DEEP_DIVE_REPORTS/open-source/garrettj403__SciencePlots.md)；[Matplotlib§6](04_DEEP_DIVE_REPORTS/open-source/matplotlib__matplotlib.md) | 风格统一可掩盖错单位、不可比case、插值和平滑误导 | FigureContract先行；source data、脚本、矢量/栅格输出和三重QA共同交付 |
| AP06 | 引用存在但无法定位或不支持主张 | [PaperQA2§6](04_DEEP_DIVE_REPORTS/open-source/Future-House__paper-qa.md)；[scite§6](04_DEEP_DIVE_REPORTS/commercial-public-workflows/product__scite.md) | 引用ID、分类或摘要不等于原文对当前claim提供正确角色支持 | 保存原文locator、文献角色和作者判断；无法映射的引用不进入正文 |
| AP07 | 状态报告冒充作者批准 | [LangGraph§6](04_DEEP_DIVE_REPORTS/open-source/langchain-ai__langgraph.md)；[产品基线§6](01_CURRENT_PRODUCT_BASELINE.md) | `complete`、checkpoint或worker handoff不能创造作者权限 | 真实身份和显式动作绑定批准对象；执行器只能报告产物状态 |
| AP08 | 过度治理挤压科学 | [LangGraph§12–13](04_DEEP_DIVE_REPORTS/open-source/langchain-ai__langgraph.md)；[产品基线§7](01_CURRENT_PRODUCT_BASELINE.md) | 多层registry、审批和审计会让Agent证明“没做错”而不理解CFD，且仍可能传播错误QoI | 55/25/10/10；治理仅保留RP01–RP02，其他资源回到科学、图件和写作 |
| AP09 | 自动对齐/跳过缺失掩盖不可比性 | [xarray§6、§12](04_DEEP_DIVE_REPORTS/open-source/pydata__xarray.md) | outer alignment、broadcast和`skipna`可生成数值合理但物理错误的趋势 | 可比性gate先行，默认`join="exact"`，missing policy由QoI合同声明 |
| AP10 | 非设计离散扫描冒充全局敏感性 | [SALib§6、§12](04_DEEP_DIVE_REPORTS/open-source/SALib__SALib.md) | 算法输出形式完整，但设计矩阵、case顺序和样本完整性不成立 | 只有满足设计合同才调用SALib；否则只报告离散趋势和证据缺口 |
| AP11 | 编译/导出成功冒充科学完成 | [Quarto§6、§12](04_DEEP_DIVE_REPORTS/open-source/quarto-dev__quarto-cli.md)；[Overleaf§6](04_DEEP_DIVE_REPORTS/commercial-public-workflows/product__overleaf.md) | PDF可编译或DOCX可打开只证明文件链运行，不能证明数据、claim或引用正确 | 科学门先于export；结构回读与页面QA只承担交付验证，不提升claim ceiling |
| AP12 | 安装Skill或恢复checkpoint即视为能力成熟 | [OpenSkill§6、§12](04_DEEP_DIVE_REPORTS/open-source/vudknguyen__openskill.md)；[LangGraph§6](04_DEEP_DIVE_REPORTS/open-source/langchain-ai__langgraph.md) | 分发和持久化只保证状态存在，不能保证Skill正确理解数据或QoI | Skill必须通过真实CFD正/负回放；checkpoint输入变化后必须失效相关产物 |

## 5. Task 8–9的使用边界

Task 8应从AU02和与之直接相关的科学/表达机制中选择最小Skill组合，不把20项机制逐项包装成
20个Skill。Task 9应从本目录选择一个能贯通“成熟结果 → 科学分析 → 图件/写作产物”的最小纵向
切片；其余明确延期。任何建议若在后续设计中主要增加报告、审批或registry，而没有改善科学判断、
图件、写作、适配或普通用户完成任务的能力，应按AP08删除。
