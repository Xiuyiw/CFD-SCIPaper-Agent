# V0.3 项目景观：候选发现与组合筛选

日期：2026-08-31
适用基线：CFD-Paper-Agent v0.2.0
研究阶段：Task 2–3 候选发现与深读组合筛选

## 1. 发现边界

本轮发现只核实公开项目或产品的最低元数据，用于判断是否进入后续深读。开源与学术代码的
能力描述限于官方仓库、官方文档和原始论文的公开定位；商业产品限于官方帮助中心、产品文档
和条款。搜索结果只用于定位官方入口，不作为最终证据。仓库存在、README描述或产品宣传均不
写成已经在本项目中验证的实现。

候选池在 33 个时停止扩展：候选数已超过30，七轨均有不少于4个候选；在机制已经覆盖后，
最后一批 VTK、seaborn、The AI Scientist、Agent Laboratory 和 Anthropic Skills 分别重复了
PyVista/Matplotlib、data-to-paper、Agent Skills规范与OMF Skills已经提供的机制或反模式，
连续5个合格候选未增加独立迁移机制。50是上限，不是目标。

## 2. 分轨检索记录

检索日期均为2026-08-31。检索结果页和排行榜只承担发现作用；最终登记来源类型为官方GitHub
仓库、官方文档/帮助中心、原始论文或官方规范。

| 轨道 | 检索式 | 最终来源类型 |
|---|---|---|
| cfd-adapters | `GitHub CFD post-processing VTK Python adapter tests`；`official Fluent Python API result extraction`；`mesh neutral format reader writer scientific data`；`Ansys DPF Python result fields` | 官方仓库、官方求解器文档 |
| scientific-analysis | `Python physical units quantities library tests`；`global sensitivity analysis Python Sobol Morris`；`uncertainty quantification scientific Python official repository`；`labeled multidimensional scientific data Python` | 官方仓库、官方方法文档 |
| figures | `scientific plotting publication styles matplotlib official`；`VTK ParaView scientific visualization repository`；`editable SVG PDF scientific figures Python` | 官方仓库、官方绘图库文档 |
| writing | `research paper agent citations GitHub academic code`；`data to paper backward traceable AI research`；`official academic writing assistant DOCX LaTeX export`；`literature review agent citations official` | 官方仓库、原始论文、商业帮助中心 |
| agent-rag | `scientific literature RAG citations repository`；`local agent state persistence human in loop official docs`；`document index retrieval agent framework tests`；`research report agent outline citations` | 官方仓库、官方框架文档、原始论文 |
| skills | `Agent Skills specification progressive disclosure official`；`computational modeling agent skills GitHub`；`cross host agent skill manager repository`；`skills scripts references assets validation` | 官方规范、官方仓库 |
| quality-export | `scientific DOCX LaTeX Quarto export official`；`python WordprocessingML document library tests`；`academic citation export BibTeX RIS DOCX`；`publisher submission LaTeX workflow official` | 官方仓库、官方出版文档、商业帮助中心 |

## 3. 候选覆盖与来源层级

候选目录共33项：20个`open-source`、5个`academic-code`、7个
`commercial-public`和1个`standard`。同一候选可以覆盖多轨，因此轨道计数不相加。

| 轨道 | 候选数 | 主要模块类型 |
|---|---:|---|
| cfd-adapters | 7 | VTK生态、求解器官方Python接口、中性网格格式、带标签数据 |
| scientific-analysis | 10 | 单位、敏感性/UQ、带标签数据、科学工作流 |
| figures | 7 | 底层绘图库、期刊样式、三维科学可视化、出版系统 |
| writing | 15 | 数据到论文、科学文献RAG、长文编排、写作/协作产品 |
| agent-rag | 12 | 有状态编排、文档索引、科学文献检索、商业检索UX |
| skills | 5 | Agent Skills规范、计算建模技能、跨宿主管理、工具节点 |
| quality-export | 14 | SVG/PDF、DOCX、LaTeX、Quarto、引用与出版社提交 |

每个候选至少关联一条`sources_manifest.json`来源。开源活动时间和许可证来自官方GitHub
仓库/API或仓库许可证文本；商业输入、输出、人工检查点、导出和限制来自官方公开页面。
`latest_release=null`、`tests_present=null`表示在本轮最低核查中未独立定位，不表示没有
release或测试。`tests_present=false`本轮未使用，以避免把“根目录没有tests”误写为仓库没有测试。

## 4. 是否存在整体直接同类

未发现能够以公开证据同时覆盖“成熟CFD结果输入、科学资格检查、QoI/单位/趋势/不确定度、
论文级图件、带证据写作、真实DOCX/LaTeX交付和作者检查点”的整体直接同类。公开生态更成熟的
形态是模块组合：

- CFD与科学数据项目解决数据对象、格式、字段或可视化，不判断论文主张是否成立；
- UQ、单位和绘图库解决单一科学或表达机制，不建立跨章节证据链；
- 研究Agent多从主题或原始数据开始，不能据此推断其适合已有成熟CFD结果；
- 商业产品提供文献、写作、引用、审校或协作UX，但公开材料不足以核实内部科学机制；
- 出版工具能产生真实文件，不负责科学证据资格和claim ceiling。

因此，后续深读应围绕可组合机制而不是寻找一个“完整论文Agent”替代品。

## 5. 生态空白

1. 求解器或中性文件读取之后，缺少公开通用机制把case、边界、收敛、守恒、QoI定义和来源
   一并提升为可辩护论文证据。
2. 单位库、UQ库和趋势计算库彼此独立，缺少面向多case可比性和主张上限的组合接口。
3. 科研绘图库强调绘制或样式，较少把figure contract、source data、视觉QA和图文传播作为
   一个公开契约。
4. 研究Agent强调检索、生成或自动研究，公开项目很少把锁定数值、跨章节传播和真实返修作为
   核心对象。
5. Agent Skill生态开始形成规范与计算建模样例，但科学Skill的触发、失败回退、测试和跨宿主
   行为仍需分项目核实。
6. DOCX/LaTeX工具能够导出文件，但公式、引用、图表、可编辑文本和最终渲染的一致性通常需要
   额外验证。

## 6. 初步反模式

- 把README中的端到端愿景或论文效果主张直接写成当前实现；
- 用stars、更新日期或品牌知名度代替科学正确性和适配性；
- 把通用格式转换写成求解器语义理解，把单位换算写成算例可比；
- 把离散CFD筛选写成连续最优区、稳定边界或实验验证；
- 把引用链接存在写成主张已经由原文支持；
- 把Markdown报告生成写成DOCX/LaTeX、引用、图表和页面渲染均已交付；
- 把全自动研究流程的阶段完成状态当作作者批准或科学证据成熟；
- 因通用Agent框架功能多而引入与当前科学任务无关的编排与治理。

## 7. 进入深读的筛选依据

筛选不使用统一stars总分，而按轨道判断：

1. 候选必须有真实公开实现，或是商业产品的可观察官方工作流；
2. 开源/学术代码必须核实许可证，并具有测试、示例或规范价值；
3. 对七轨带来独立机制证据，不能只重复已选对象；
4. 能定位输入、输出、状态、扩展点、错误/缺失数据行为或真实导出中的至少一个关键问题；
5. 依赖、许可证和场景边界允许形成明确的direct reuse、reimplement、idea-only或reject判断；
6. 自动科研、商业宣传和托管内部架构只能作为边界或UX，不作为未经验证的实现事实。

商业对象只进入公开工作流与UX组合；标准不标为`selected-open-source`。未进入组合的项目保留
为`discovery-only`，原因是机制重复、场景偏离、许可证/维护风险或本轮没有新增机制。


## 8. Task 3 入选组合

组合按轨道的独立机制筛选，不作统一stars总分。当前状态表示“已锁定、待后续Task深读”，
`metadata-verified`不表示代码已经深读，`official-workflow`也不表示商业内部实现得到验证。

### 8.1 开源与学术代码：16项

| 机制组 | 入选对象 | 入选理由 |
|---|---|---|
| CFD与科学数据 | PyVista；PyDPF-Core；xarray；Pint；SALib | 分别代表中性网格/可视化、求解器结果对象、带标签数据、单位量和敏感性分析；避免用一个大型项目替代全部科学机制。 |
| 科研绘图 | SciencePlots；Matplotlib；PyVista | 分别覆盖期刊样式、底层artist/布局/导出和三维科学可视化；后续需核查source data与视觉QA边界。 |
| 论文/研究Agent | data-to-paper；PaperQA2；STORM | 分别覆盖数值后向追溯、科学文献RAG和多视角长文编排；三者的目标任务和风险不同。 |
| RAG与状态编排 | LangGraph；LlamaIndex；PaperQA2 | 分别代表可恢复状态图、摄取/索引/检索抽象和科学文献证据上下文。 |
| Skill与科学工作流 | OMF Skills；OpenSkill；LangGraph；data-to-paper | 分别提供领域Skill/evals、跨宿主管理、工具节点编排和可核验科学工作流；后续只深读各自独立机制。 |
| 质量与真实交付 | Quarto；python-docx；Matplotlib；SciencePlots | 分别代表多格式科学出版、WordprocessingML、可编辑图件导出和出版样式。 |

组成满足最低要求：CFD/科学数据不少于2项，科研绘图不少于2项，论文/研究Agent不少于3项，
RAG/编排不少于2项，Skill/科学工作流不少于3项；七轨在入选组合中均非空。部分对象跨组出现
只表示跨轨覆盖，不重复计算候选。

### 8.2 商业公开工作流：7项

| 对象 | 只对标的公开UX |
|---|---|
| Elicit | 文献检索、系统综述筛选/抽取、报告与表格/引用导出 |
| SciSpace | 文献表格比较、论文问答、筛选与导出 |
| Paperpal | 作者逐项接受的学术写作、语言/一致性和提交前检查 |
| scite | 引用上下文、支持/反驳/提及分类和来源核查 |
| Jenni AI | DOCX/LaTeX、原生Word引用、BibTeX/RIS与评论保留 |
| Consensus | 问题驱动检索、来源跳转、研究总结和列表导出 |
| Overleaf | 协作LaTeX、编译预览、模板和出版社提交 |

这些对象标为`selected-commercial`仅表示后续读取官方公开工作流。登录后、付费功能或内部
模型、RAG、数据库、分类器和Agent架构均不从公开营销材料反推。

## 9. 仅发现对象与明确原因

| 对象 | 保留为 discovery-only 的原因 |
|---|---|
| VTK | 底层数据/可视化机制已由PyVista覆盖；官方镜像不增加本轮独立迁移问题。 |
| ParaView | 应用体量大；pipeline和可视化机制已由更轻的PyVista/VTK生态代表。 |
| meshio | 主要增加格式数量，不能保留全部求解器语义，且维护活动弱于已选适配对象。 |
| PyFluent | 依赖商业Fluent且侧重求解器控制；本轮只读结果适配由PyDPF-Core代表。 |
| OpenTURNS | UQ机制与SALib部分重叠，GPL与C++/Python依赖提高直接复用成本。 |
| seaborn | 统计绘图语法与Matplotlib/SciencePlots重叠，不覆盖CFD场图和交付QA。 |
| The AI Scientist | 自定义非OSI许可证；从零全自动科研与成熟CFD、作者在环定位冲突。 |
| Agent Laboratory | 端到端研究Agent机制与data-to-paper重叠，活动较弱且场景偏离。 |
| Agent Skills specification | 保留官方规范事实；标准对象按契约不使用开源选择状态。 |
| Anthropic Skills | 示例集合与Agent Skills/OMF Skills重叠，且无仓库级统一许可证。 |

## 10. 组合边界

后续每份报告只回答其入选机制所需的入口、核心对象、一个代表性实现、测试/示例和许可证。
报告路径已经在候选目录中确定，但本Task不创建空项目报告，也不把待验证功能写成implemented。
若后续入口材料表明没有新增机制或不适合本项目，应停止读取并降级，而不是为满足数量完成长报告。
