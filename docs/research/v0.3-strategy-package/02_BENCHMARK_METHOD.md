# CFD-Paper-Agent v0.3 前置对标研究方法

日期：2026-08-31
适用基线：CFD-Paper-Agent v0.2.0
研究性质：公开证据驱动的产品研究，不包含 v0.3 生产实现

## 1. 研究目标与输出

对标研究要回答三个问题：外部项目已经通过什么可验证机制解决了相邻问题；这些机制对“成熟 CFD
结果到可辩护论文”的哪一段有帮助；应当直接复用、重新实现、只借鉴思想，还是明确拒绝。

研究输出由候选目录、来源清单、开源代码深读、商业公开工作流分析、跨项目比较和迁移建议组成。
所有产品建议必须能追溯到公开来源、当前产品缺口和可执行的验证方法。对标不是按知名度排榜，也不
用功能数量掩盖科学适用性差异。

## 2. 固定七条研究轨道

候选发现、深读、比较和结论统一使用以下标识：

| 轨道标识 | 研究范围 |
|---|---|
| `cfd-adapters` | 原生求解器、中性格式、只读提取、对象清单、单位、来源定位和适配器边界。 |
| `scientific-analysis` | QoI、可比性、收敛、守恒、趋势、敏感性、不确定度、物理解释和主张上限。 |
| `figures` | figure contract、source data、出版绘图、可编辑输出、图文一致性和视觉 QA。 |
| `writing` | 文献角色、paper spine、逐节写作、引用、跨章节传播、自审与真实返修。 |
| `agent-rag` | 任务编排、状态恢复、结构化检索、全文检索、可选语义检索和供应商抽象。 |
| `skills` | 技能发现、渐进加载、输入输出、脚本与资源、适用条件、回退、测试和版本管理。 |
| `quality-export` | 提交前检查、DOCX/LaTeX、图表与引用嵌入、渲染验证和可复现导出。 |

一个候选可以覆盖多条轨道，但必须分别说明证据深度，不能把单一亮点外推为全流程能力。

## 3. 双层研究漏斗

### 3.1 宽口径候选发现

七条轨道分别设计检索式并去重，目标为 **30–50 个候选**。发现阶段只记录足以判断相关性、来源
类型和初步风险的信息，不提前写深读结论。项目名称相同但官方产品和开源仓库承担不同功能时，可
作为关联来源记录，但不得重复计数制造覆盖度。

候选池需要覆盖四类来源：

- `open-source`：具有可访问代码仓库和可核对许可证的开源项目；
- `commercial-public`：只能通过官方公开页面、帮助中心、演示或产品文档分析的闭源产品；
- `standard`：协议、数据格式、质量规范或软件工程规范的官方来源；
- `academic-code`：与论文方法直接关联、由作者或机构公开的学术代码。

### 3.2 深度分析

从候选池选择 **12–18 个开源或学术代码项目**进行代码级深读，另选 **5–8 个商业产品**进行
官方公开工作流与用户体验分析。每条轨道至少有一个高相关深读对象；若公开生态确实没有成熟对象，
报告应如实记录空缺及搜索证据。

开源代码级深读至少覆盖：

- 入口和实际可运行路径；
- 核心数据对象、状态和存储；
- 插件、适配器、工具或技能扩展机制；
- 错误、缺失数据和恢复行为；
- 测试、示例、发布边界和依赖；
- 许可证、近期活动与可定位的文件、类、函数或规范章节。

不能只复述 README 或宣传示例。开源仓库中的 stars 仅作为维护和社区信号之一，不代表科学质量、
代码正确性、产品适配性或优先级。

闭源产品只分析官方公开工作流，包括用户输入、步骤、检查点、可见产物、导出形式和公开限制。
不反推内部架构、模型或算法。商业宣传不是技术事实；无法由官方文档或可观察工作流支持的内容，
不得写成已实现机制。

标准优先使用规范发布方的正式文本。学术代码同时核对原始论文与官方仓库，区分论文方法、仓库
实现和研究者推断。

## 4. 统一比较问题

每个深读对象使用同一组问题，但不强行压缩为单一总分：

1. 它解决的真实用户任务是什么，入口和产物是什么？
2. 科学事实、来源、主张和缺失数据如何表示并绑定？
3. 面对不可比工况、单位冲突、弱收敛、守恒缺失或错误趋势时如何处理？
4. 它对已有成熟结果的支持程度如何，是否假设从零生成数据？
5. 作者或用户在哪些节点保留判断权，系统能否制造批准或完成状态？
6. 状态如何恢复，上下文如何检索，陈旧证据如何排除？
7. 扩展点如何发现、加载、测试、隔离和版本化？
8. 图件、正文、引用和导出产物能否追溯、编辑、渲染和复现？
9. 直接集成需要什么依赖，许可证、维护和供应商锁定风险是什么？
10. 哪些机制会诱发虚假完成、过度自动化、内部治理膨胀或科学主张越界？

开源和商业对象可以回答同一用户问题，但不能用“代码质量”维度直接比较。没有公开证据的答案应
留空或明确标为推断。

## 5. 四种迁移判定

任何外部机制只能进入以下一种判定：

| 判定 | 含义 | 最低要求 |
|---|---|---|
| `direct reuse` | 直接复用现有代码、规范或独立组件。 | 许可证兼容，接口边界清楚，依赖可接受，有实际测试，并通过本项目隔离验证。 |
| `reimplement` | 保留机制，在本项目中重新实现。 | 机制已由代码或官方工作流证实，但原实现的许可证、依赖、架构或科学边界不适合直接引入。 |
| `idea-only` | 只借鉴交互、组织方式或设计原则。 | 可说明要解决的问题和本地验证方法，不复制未授权代码，也不把营销描述当作实现依据。 |
| `reject` | 明确不进入产品设计。 | 与成熟 CFD 证据、作者在环、产品资源原则或科学边界冲突，或证据不足以支撑采用。 |

每项迁移建议必须记录：来源、目标问题、判定、适配条件、预期收益、实现成本、风险、验证方法，
以及它与当前产品基线或历史正负经验的关系。相似并不等于可复用，许可证兼容也不等于科学适用。

## 6. 候选目录 JSONL 契约

`candidate_catalog.jsonl` 使用 UTF-8 JSON Lines。每一非空行必须是一个完整 JSON 对象。基础字段
固定为 `id`、`name`、`source_type`、`tracks`、`official_url`、`repository_url`、`license`、
`evidence_depth`、`status`、`selection_reason`、`risks` 和 `discovery_evidence`：

| 字段 | 类型与约束 | 含义 |
|---|---|---|
| `id` | string，目录内唯一且稳定 | 候选标识；名称或 URL 变化时尽量保持不变。 |
| `name` | string | 项目、产品、标准或学术代码的公开名称。 |
| `source_type` | string enum | 只允许 `open-source`、`commercial-public`、`standard`、`academic-code`。 |
| `tracks` | string array，至少一项 | 只使用本文件定义的七个轨道标识。 |
| `official_url` | string | 项目或产品的官方公开入口。 |
| `repository_url` | string 或 null | 官方代码仓库；无公开仓库时为 null。 |
| `license` | string | 已核对的许可证标识；商业产品记录公开条款类型。未核实时写明未核实状态，不作推断。 |
| `evidence_depth` | string enum | 只允许 `discovery`、`metadata-verified`、`official-workflow`、`code-deep-dive` 或 `standard-deep-dive`，表示当前实际查证深度。 |
| `status` | string enum | 只允许 `candidate`、`selected-open-source`、`selected-commercial`、`discovery-only`、`deep-read` 或 `rejected`，表示研究进度而非产品质量。 |
| `selection_reason` | string | 进入候选池、深读或拒绝的简洁依据。 |
| `risks` | string array | 许可证、维护、科学边界、依赖、锁定或证据不足等风险；无已知风险时使用空数组。 |
| `discovery_evidence` | object | 嵌入当前候选行的最低发现证据；结构见下文，不另建注册表。 |

状态从 `candidate` 开始。进入开源或学术代码深读的候选转换为 `selected-open-source`，进入商业公开
工作流分析的候选转换为 `selected-commercial`；保留在发现层、不进入深读的候选转换为
`discovery-only`。完成相应深读或工作流报告后，已选择候选可转换为 `deep-read`；在任一阶段被排除
时转换为 `rejected`，并在 `selection_reason` 中记录原因。不得使用本表枚举之外、缺少来源类型
语义的泛化状态。

`discovery_evidence` 的所有来源类型都必须包含 `checked_at`（string，RFC 3339 full-date 或
date-time）、`official_docs`（array[string]）和 `notes`（array[string]）。不同来源类型在此基础上
增加：

| `source_type` | `discovery_evidence` 的类型专用字段与 JSON 类型 |
|---|---|
| `open-source`、`academic-code` | `latest_activity_at`: string 或 null（RFC 3339 full-date/date-time）；`latest_release`: string 或 null；`tests_present`: boolean 或 null；`primary_languages`: array[string] |
| `commercial-public` | `inputs`、`outputs`、`human_checkpoints`、`export_formats`、`public_limitations` 均为 array[string] |
| `standard` | `edition_or_version`: string 或 null；除此之外只使用公共字段，不要求代码或商业工作流字段 |

每个规定字段都必须出现。允许 null 的标量字段以 `null` 表示未能从公开来源验证；数组使用空数组
表示已经核对但未发现相应条目。`tests_present` 只有在公开仓库证据明确时使用 `true` 或 `false`，
否则使用 `null`。

候选状态、证据深度与报告必须满足以下最小组合，不扩展为独立状态机：

| `source_type` | 允许的最小状态路径 | 选择状态的最低 `evidence_depth` | `deep-read` 对应的 `evidence_depth` |
|---|---|---|---|
| `open-source`、`academic-code` | `candidate` →（`selected-open-source` 或 `discovery-only`）→（`deep-read` 或 `rejected`） | `metadata-verified` | `code-deep-dive` |
| `commercial-public` | `candidate` →（`selected-commercial` 或 `discovery-only`）→（`deep-read` 或 `rejected`） | `official-workflow` | `official-workflow`，不表示代码验证 |
| `standard` | `candidate` → `discovery-only` / `deep-read` / `rejected` | 不使用选择状态 | `standard-deep-dive` |

深读或公开工作流报告完成时，必须在同一次目录更新中把 `status` 改为 `deep-read`、把
`evidence_depth` 改为上表对应值，并写入非空 `report_path`。选择状态尚未完成报告时可以没有
`report_path`；`deep-read` 不允许缺少报告路径。

所有基础字段必须保留，字段含义在后续研究中不得改变。后续可以添加 `report_path` 指向本地深读
报告，也可以添加不与基础字段冲突的扩展字段。新增字段不能把缺失的基础字段改成隐式默认值。

当前候选目录保持空文件，直到后续研究按公开来源实际发现并核对候选；不得用记忆、预期项目名或
示例对象预填。

## 7. 来源 manifest 契约

`sources_manifest.json` 的根对象包含：

- `schema_version`：整数，当前为 1；
- `generated_at`：RFC 3339 时间；`sources` 发生任何变化时刷新为 manifest 实际生成时间；
- `sources`：来源对象数组。

每条 `source` 必须包含以下字段：

| 字段 | 类型与约束 | 含义 |
|---|---|---|
| `id` | string | manifest 内唯一、首次赋值后稳定的人类可读标识，赋值规则见下文。 |
| `url` | string | 可复核的公开 URL，优先指向原始页面、官方文档或仓库固定位置。 |
| `source_type` | string enum | 与候选目录相同，只允许四种来源类型。 |
| `title` | string | 来源公开标题。 |
| `accessed_at` | RFC 3339 datetime string | 实际访问时间。 |
| `license_or_terms` | string | 许可证、文档许可或公开使用条款。 |
| `tracks` | string array，至少一项 | 该来源支持的研究轨道。 |
| `candidate_ids` | string array | 该来源支持的候选 `id`；可关联多个候选，没有候选关联时使用空数组。 |
| `used_in` | object array，至少一项 | 每项必须包含 `path`、`section`、`claim_id`；`claim_id` 可以为 null。 |
| `claim_type` | string enum | 只允许 `fact` 或 `inference`。 |
| `locator` | string | 文件、章节、标题、类、函数、版本、提交或页面锚点等精确定位。 |

`id` 是 manifest 内唯一、首次赋值后保持稳定的人类可读标识，例如 `src-pyvista-readme`；若名称
冲突，在末尾添加简短数字后缀。它只用于引用，不表示来源获批或主张成立，也不需要额外注册表。
来源去重基于 `(normalized_url, locator, claim_type)`：URL 规范化仅去除首尾空白并将 scheme 与
host 转为小写，不改变 path 或 query；`locator` 和 `claim_type` 保持原值。`candidate_ids` 可以包含
多个候选。

`used_in.path` 是使用来源的报告相对路径，`section` 是稳定章节标题或锚点，`claim_id` 是报告内
主张标识；报告尚未建立主张 ID 时使用 null。结构化关联用于定位来源实际支持了报告中的哪项内容，
不能用一个文件路径代替具体章节和主张关系。

一条来源同时支持事实和推断时，应拆成两条记录或在报告中把两类主张分开，并为各自主张提供清楚
定位。`fact` 只记录来源直接支持的内容；`inference` 必须使用克制语言并说明推理链。来源清单不是
网页收藏夹，只有实际用于报告主张的来源才进入 manifest。

## 8. 事实、推断与维护信号

- 事实必须能从登记来源和 locator 直接复核；研究者综合、适配判断和产品建议属于推断。
- 推断不能借用来源权威变成事实；报告中应明确使用“表明”“推测”“适合本项目的原因”等语义。
- 商业宣传、客户案例和演示中的效果主张，除非有公开可核对方法和结果，否则只作为产品定位或
  工作流线索。
- stars、下载量、融资和品牌知名度只可作为活动或生态信号，不能替代许可证、代码检查、测试、
  科学正确性或迁移适配分析。
- 仓库中存在文件、接口或未发布分支，不等于该能力已经进入稳定产品；报告必须核对发布说明和
  可运行路径。

## 9. 停止条件

候选扩展在以下条件同时满足时停止：

1. 去重候选达到 30–50 个，四类来源和七条轨道均得到合理覆盖；
2. 完成 12–18 个高相关开源或学术代码项目的代码级深读；
3. 完成 5–8 个商业产品的官方公开工作流分析；
4. 每条轨道都有可追溯结论，或有足够搜索记录支持“未发现成熟对象”；
5. 连续两个补充筛选批次不再产生重要的新机制、反模式或迁移选项；
6. 所有进入跨项目比较的事实、推断、许可证和活动状态均有来源与 locator。

停止条件控制的是研究饱和度，不要求为了达到上限而纳入低相关项目。若达到数量下限后仍存在关键
轨道空白或相互冲突的实现证据，应继续在数量上限内定向补充；若超过上限仍无法回答关键问题，应
先记录证据缺口并请求调整范围，而不是无限扩展搜索。

## 10. 资源原则与建议筛选

研究结论和未来产品建议统一按 **55/25/10/10** 分配注意力：

- **55% 科学理解与分析**：证据资格、可比性、单位、收敛、守恒、QoI、趋势、敏感性、物理解释
  与主张上限；
- **25% 科研绘图与写作**：figure contract、source data、图文传播、文献角色、论文结构、自审与返修；
- **10% 适配和易用性**：求解器与中性格式适配、普通用户入口、渐进交互和项目上下文；
- **10% 必要可靠性、溯源与作者权限**：可恢复状态、来源定位、渲染验证、权限边界和回归测试。

该比例用于防止产品研究被编排框架或治理对象主导，不是逐条候选的机械打分。可靠性与溯源应尽量
成为后台默认能力，只有影响科学判断或需要作者选择时才进入主交互。

## 11. 研究边界

本研究不恢复 L0–L4、promotion registry、synthetic master acceptance，也不以这些历史治理结构
组织新产品。历史正向与负向材料只用于抽象科学模式、作者语气、回归问题和交付要求，不进入公开
来源 manifest，也不暴露私有项目位置、未发表数值、单位信息或论文原文。

研究包完成、外部评审返回并获得作者批准之前，不把研究建议描述为 v0.3 已交付能力，也不启动
生产实现。任何后续实现仍需从最小切片、公开契约和可复现验收开始。
