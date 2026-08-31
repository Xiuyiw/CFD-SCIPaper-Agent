# 跨项目能力比较

日期：2026-09-01
适用基线：CFD-Paper-Agent v0.2.0
证据范围：16份开源/学术代码深读与7份商业公开工作流报告

## 1. 如何阅读本比较

本文件比较的是公开证据能够证明的机制，不是项目排名。七条轨道分别判断，不能把某一列的
成熟能力外推到其他列，也不能把商业产品的公开工作流当作其内部实现证明。状态只使用以下五种：

| 状态 | 含义 |
|---|---|
| `implemented` | 固定版本源码、测试或可运行示例证明核心机制存在。 |
| `partial` | 固定版本实现直接满足该轨道至少一项定义能力，但未覆盖整条轨道；仅有可扩展接口、测试、缓存或持久化不计入。 |
| `documented-only` | 官方公开材料说明可观察工作流，但内部代码和独立效果未验证。 |
| `absent` | 深读材料明确表明该任务不在项目范围内。 |
| `not verified` | 公开证据不足，不能判断存在或不存在。 |

矩阵不使用星级、总分或“最佳项目”。每个状态的依据均在
[`04_DEEP_DIVE_REPORTS/`](04_DEEP_DIVE_REPORTS/README.md)对应报告中；开源定位固定到报告记录的
commit与类/函数，商业定位固定到官方页面与报告章节。

## 2. 七轨能力矩阵

| 项目 | 来源类型 | CFD适配 | 科学分析 | 科研绘图 | 文献/写作 | Agent/RAG | Skill系统 | 质量/交付 |
|---|---|---|---|---|---|---|---|---|
| PyVista | 开源 | implemented | partial | implemented | absent | absent | absent | partial |
| PyDPF-Core | 开源 | implemented | partial | partial | absent | absent | absent | absent |
| xarray | 开源 | partial | implemented | partial | absent | absent | absent | partial |
| Pint | 开源 | absent | implemented | absent | absent | absent | absent | absent |
| SALib | 开源 | absent | implemented | not verified | absent | absent | absent | absent |
| SciencePlots | 开源 | absent | absent | partial | absent | absent | absent | partial |
| Matplotlib | 开源 | absent | absent | implemented | absent | absent | absent | partial |
| data-to-paper | 学术代码 | absent | partial | partial | implemented | implemented | absent | implemented |
| PaperQA2 | 学术代码 | absent | absent | absent | partial | implemented | absent | partial |
| STORM | 学术代码 | absent | absent | absent | partial | implemented | absent | partial |
| LangGraph | 开源 | absent | absent | absent | absent | implemented | absent | absent |
| LlamaIndex | 开源 | absent | absent | absent | absent | implemented | absent | absent |
| OMF Skills | 开源 | absent | partial | not verified | partial | absent | implemented | partial |
| OpenSkill | 开源 | absent | absent | absent | absent | partial | implemented | partial |
| Quarto | 开源 | absent | absent | partial | implemented | absent | absent | implemented |
| python-docx | 开源 | absent | absent | absent | partial | absent | absent | implemented |
| Elicit | 商业公开 | absent | absent | not verified | documented-only | not verified | not verified | documented-only |
| SciSpace | 商业公开 | absent | absent | absent | documented-only | not verified | not verified | documented-only |
| Paperpal | 商业公开 | absent | absent | absent | documented-only | not verified | not verified | documented-only |
| scite | 商业公开 | absent | absent | absent | documented-only | not verified | not verified | documented-only |
| Jenni AI | 商业公开 | absent | absent | absent | documented-only | not verified | not verified | documented-only |
| Consensus | 商业公开 | absent | absent | absent | documented-only | not verified | not verified | documented-only |
| Overleaf | 商业公开 | absent | absent | absent | documented-only | absent | not verified | documented-only |

## 3. 分轨结论

### 3.1 CFD资产识别与适配

PyVista证明了以通用网格、point/cell/field数组和显式filter组织中性结果的可行性；PyDPF-Core证明
了原生结果源、zone/phase/location、单位和typed operator的价值；xarray适合承载求解器提取后的
多case标签数组。三者都没有把边界条件、收敛、守恒和可比性一并提升为论文证据。因此，求解器
适配必须止于可定位的只读提取，不能自行批准后续科学比较。

关键定位：

- PyVista：`pyvista/core/utilities/fileio.py::read`、
  `pyvista/core/filters/data_set.py::DataSetFilters.integrate_data`；
- PyDPF-Core：`src/ansys/dpf/core/model.py::Model`、`field.py::Field`、
  `workflow.py::Workflow`；
- xarray：`xarray/core/dataarray.py::DataArray`、
  `xarray/structure/alignment.py::Aligner`。

### 3.2 科学分析与物理解释

Pint能够阻断量纲冲突，xarray能够用命名坐标和`join="exact"`阻断数组位置错配，SALib能够在
有效采样设计上执行敏感性分析，PyDPF/PyVista能够执行有空间范围的算子。没有任何一个项目同时
判断工况可比性、收敛、守恒、QoI语义、趋势措辞和claim ceiling。这一空白是CFD-Paper-Agent最
需要保留的差异化核心，且必须在绘图与写作之前运行。

### 3.3 科研绘图

Matplotlib提供成熟artist、布局与SVG/PDF/PNG/TIFF后端；PyVista提供三维场数据与矢量导出；
SciencePlots提供可组合样式基线。它们均不自动生成与图一致的source data，也不审查工况、单位、
平滑、插值、双轴、色标或图件主张。出版级图件需要在这些引擎之上建立FigureContract、锁定数据、
叙事/数据/视觉三重QA和可编辑输出回读，而不是再引入一套绘图库。

### 3.4 文献与论文写作

data-to-paper证明分析产物、文本数值和LaTeX/PDF可以形成真实反链；PaperQA2证明内容哈希、来源
上下文和引用映射可以进入同一会话；STORM证明“多视角问题—资料表—提纲—分节文本”的阶段组织
可行。商业产品进一步展示证据矩阵、原文下钻、句级建议、作者接受/拒绝和导入/导出损失披露。
但这些机制都不能替代CFD证据资格。最适合迁移的是“证据先于写作、建议不直接改锁定事实、作者
保留接受权”，而不是端到端自动研究。

### 3.5 Agent编排与RAG

LangGraph的checkpoint父链与`interrupt`/`resume`、LlamaIndex的`ref_doc_id`/内容哈希/metadata
过滤、PaperQA2的可恢复索引均有真实实现。它们解决状态与检索，不证明被保存或召回的内容科学
正确。V0.3应在现有本地SQLite/FTS基础上窄实现版本过滤与任务恢复，语义检索只用于找到材料，
不引入大型通用Agent框架来替代科学门控。

### 3.6 专用Skill系统

OMF Skills最接近目标形态：短元数据与`SKILL.md`入口、按需`references/assets/scripts`、正向/
负向/对抗eval和结构validator；OpenSkill补充跨宿主路径、来源commit和安装回滚。两者均不能证明
Skill的科研结论正确。应重实现轻量、内置、可测试的专业Skill包，不建设marketplace，不把长系统
提示词或安装成功当成能力通过。

### 3.7 质量与交付

Quarto和python-docx都能产生真实文件：前者适合QMD/BibTeX到DOCX/LaTeX/PDF/JATS，后者适合模板
驱动的局部Word装配。Jenni、Paperpal和Overleaf的公开流程共同说明：导入/导出损失要显式披露，
建议要由作者接受，源码、预览和投稿包应分层。编译成功、DOCX可打开或报告存在都不能成为科学
批准；最终交付仍需结构回读和页面渲染。

## 4. 跨项目共同结论

1. **没有公开项目覆盖完整链路。** 数据对象、科学算法、绘图、文献、编排、Skill和交付各自成熟，
   但“成熟CFD结果到可辩护论文”的科学连接层仍为空白。
2. **可直接复用的是窄组件。** Pint、xarray、Matplotlib、PyVista、SALib、Quarto和python-docx均只
   应在明确边界内调用；其API成功不等于科学判断通过。
3. **更适合重实现的是连接机制。** 工况可比性、QoI契约、claim ceiling、figure contract、数值反链、
   版本过滤和作者检查点必须围绕本产品的数据对象重实现。
4. **商业产品主要贡献UX。** 阶段化向导、证据旁复核、句级建议、接受/拒绝、损失披露和产物预览
   值得借鉴，但不构成内部模型或科学能力证据。
5. **V0.3不应成为框架集成项目。** 科学资格与论文产物之间的最小纵向切片优先；通用Agent图、
   marketplace和多供应商平台只有在真实需求出现后再评估。
