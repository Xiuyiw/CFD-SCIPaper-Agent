# 内置专业 Skill 体系设计

日期：2026-09-01
适用基线：CFD-Paper-Agent v0.2.0
状态：Task 8 设计候选；不代表 V0.3 路线图已冻结

## 1. 设计结论

CFD-Paper-Agent 不需要把论文流程的每个动作都包装成一个 Skill。首批体系应由六个宿主无关的
能力包组成，并按项目阶段组合：

1. `cfd-evidence-intake`：案例盘点、可比性、单位、收敛和守恒证据资格；
2. `cfd-qoi-physics`：QoI 合同、锁定分析、全序列趋势和物理解读；
3. `cfd-figure-production`：FigureContract、科研绘图和数据/叙事/视觉三重 QA；
4. `cfd-evidence-writing`：paper spine、证据约束的逐节写作和数值反链；
5. `cfd-literature-evidence`：文献定位、证据角色和引用支持边界；
6. `cfd-publication-assurance`：跨文档 QA、提交前审查和真实事件驱动的返修。

前四个包构成 V0.3 必须考虑的最小纵向链；后两个包保留完整接口设计，但分别延期或条件启用。
六个包覆盖批准规格列出的全部阶段，又避免把 intake、comparability、units、conservation、
convergence 等高度相依步骤拆成互相争抢触发权的零碎 Skill。

Skill 是“能在真实科研任务中产生可验证产物的能力单元”，不是长提示词、角色名称、检查清单、
marketplace 条目或审批状态。宿主成功加载 Skill、脚本成功运行、图件成功导出和文档成功编译，
都不能单独证明科学任务完成。

## 2. 设计边界

### 2.1 应解决的问题

- 将重复且基础模型不稳定执行的 CFD 科学方法封装为可发现、可组合、可测试的工作流；
- 只在需要时加载专业方法、脚本和模板，避免把全部规则放进全局上下文；
- 在 Codex、Claude、TRAE 或其他支持文件与工具调用的宿主间保持相同科学语义；
- 让每个产物明确区分候选、锁定结果、作者决定和证据缺口；
- 使正向、负向和跨宿主行为可由公开 fixture 回放。

### 2.2 本设计不做的事

- 不创建 marketplace、全局 Skill registry、在线评分平台或安装遥测；
- 不把求解器 adapter、RAG、checkpoint runtime 或文档导出器伪装成 Skill；
- 不要求 Skill 自行重新求解、发明缺失数据、提升 claim ceiling 或代表作者批准；
- 不创建实际 `SKILL.md`、脚本、schema、fixture 或宿主插件；这些属于后续获批实现；
- 不把公司案例、未发表材料或其他私有资产写入公开 Skill 包。私有资产只能在授权的内部回归中使用。

这与 [Task 7 目录](06_REUSABLE_PATTERNS_AND_ANTI_PATTERNS.md)中的 AU02、AP04、AP08 和 AP12
一致：渐进披露有价值，但安装、持久化和治理对象不能替代真实 CFD 任务成功。

## 3. 宿主无关的 Skill 能力单元

### 3.1 逻辑包结构

以下是后续实现应遵守的逻辑结构，不是本 Task 创建文件的要求：

```text
skills/<skill-name>/
├── SKILL.md                 # Level 2：工作流和边界
├── references/              # Level 3：按需方法与领域参考
├── scripts/                 # Level 3：确定性检查或转换
├── templates/               # Level 3：输出骨架
├── assets/                  # Level 3：仅在任务需要时加载的静态资源
└── evals/                   # 正向、负向、对抗及跨宿主 fixture
```

Skill 内的路径以 Skill 根目录为基准。`SKILL.md`不得包含盘符、用户目录、宿主缓存目录或项目私有
绝对路径。宿主 adapter 只负责定位包、映射工具能力和传回结构化结果，不改变 Skill 的科学步骤。

### 3.2 公共接口字段

每个 Skill 必须声明以下字段；后续实现可使用 frontmatter 加正文，不需要新增独立 registry：

| 字段 | 最低含义 |
|---|---|
| `name` | 稳定、短且描述能力边界的 slug。 |
| `version` | Skill 自身语义版本；方法或输出契约改变时升级。 |
| `description` | 一句话说明解决的真实任务和主要产物。 |
| `trigger` | 应触发的事件、输入状态和显式用户意图。 |
| `do_not_trigger` | 邻近但不属于该 Skill 的场景。 |
| `inputs` | 必需和可选输入及其版本/锁定要求。 |
| `outputs` | 允许创建或建议的产物及其权威等级。 |
| `evidence_prerequisites` | 开始科学动作前必须存在的证据。 |
| `workflow` | 有序步骤；每步说明读取、计算、写入和作者检查点。 |
| `stop_conditions` | 何时完成、何时因证据不足停止。 |
| `fallback` | 工具缺失、输入不足或任务越界时的最低有用返回。 |
| `resources` | 相对路径引用的 references/templates/assets。 |
| `scripts` | 可选确定性脚本、输入/输出和失败语义。 |
| `tests` | 正向、负向、对抗和跨宿主解析 fixture。 |
| `success_criteria` | 真实任务成功条件，不能只写“文件已生成”。 |

### 3.3 触发与组合协议

触发优先级为：显式用户调用或真实外部事件 → 当前项目阶段与输入对象 → `trigger`语义匹配。
关键词命中只能召回 Level 1 元数据，不能直接执行。若多个 Skill 同时匹配：

1. 选择最靠近当前输入成熟度的一个主 Skill；
2. 其他 Skill 只能作为只读辅助，除非主 Skill 输出满足其前置证据；
3. 科学资格 Skill 先于绘图和写作 Skill；
4. 真实审稿意见到达前，返修能力不得触发；
5. 无法判断是“分析新结果”还是“解释锁定结果”时，返回一个最短澄清问题，不并行启动两个流程。

因此，`cfd-evidence-intake → cfd-qoi-physics → cfd-figure-production / cfd-evidence-writing`
是证据依赖，不是固定的通用 Agent 图。文献 Skill 可按具体 claim 辅助写作；publication Skill 只在
已有多文档产物或真实外部审稿事件时运行。

## 4. 三级渐进式披露

### Level 1：发现元数据

宿主只加载 `name`、`version`、`description`、`trigger`、`do_not_trigger`、主要输出和前置证据的
短摘要。目标是判断“该 Skill 是否解决当前任务”，不是提前灌入完整方法。

### Level 2：工作流

Skill 被选中后加载 `SKILL.md`正文，包括输入/输出、科学边界、有序步骤、停止条件、回退和需要
调用的 Level 3 资源。Level 2 必须足以让无特定宿主知识的执行器理解任务，但不复制 references
中的领域方法全文。

### Level 3：脚本、参考、模板和资产

只有对应步骤真正需要时才读取：

- `references/`：单位、收敛、QoI、绘图或写作方法；
- `scripts/`：确定性解析、数值检查、source-data/图文 QA；
- `templates/`：EvidenceGap、QoI contract、FigureContract、paper spine 或 response matrix 骨架；
- `assets/`：公开样例、样式和最小 fixture。

若 Level 2 已能完成任务，不得为了“完整”扫描全部 Level 3。若脚本缺少运行时依赖，应执行
Skill 的 fallback，而不是安装未经批准的大型框架。

## 5. 跨宿主适配

### 5.1 不变核心

Codex、Claude、TRAE 和其他宿主必须读取同一 Skill 包，使用同一相对路径、输入/输出名称、停止
条件和科学写入边界。宿主不能维护各自的“更宽松版本”。Skill 版本由包内 `version`与版本控制
共同确定，不额外建设安装状态数据库。

### 5.2 轻量宿主 adapter

宿主 adapter 只承担三件事：

1. 找到 Skill 根目录并解析 Level 1/Level 2；
2. 把“读文件、运行脚本、联网检索、请求作者输入”等抽象能力映射为宿主工具；
3. 将脚本退出状态和结构化输出原样返回工作流。

如果宿主不支持原生 Skill discovery，项目可显式提供 Level 1 索引并由用户/主控选择 Skill；这不是
另建 marketplace。若宿主不能运行脚本，Skill 应输出待运行命令和所需输入，产物保持 `pending`
或 `gap`，不得由模型估算脚本结果。

### 5.3 跨宿主解析验收

同一 fixture 在至少 Codex、Claude 和 TRAE 三类 adapter 上应满足：

- 相同 Skill 被触发或拒绝；
- 所有相对资源路径解析到同一包内对象；
- 必需输入、停止条件和失败回退语义一致；
- 结构化输出在字段和值的意义上等价；
- 任一宿主都不能因工具更丰富而突破科学写入边界。

不要求自然语言逐字一致，也不要求字节级输出相同。

## 6. 科学写入与作者权限边界

### 6.1 产物等级

| 产物等级 | 允许内容 | 是否可被图件/正文当事实读取 |
|---|---|---|
| `candidate` | 候选 QoI、候选解释、候选文献、分析或图件方案。 | 否。 |
| `gap` | 缺失字段、不可比条件、弱收敛、工具或来源缺口。 | 仅用于限定范围。 |
| `locked-evidence` | 已锁定来源、单位、scope 和资格的 Evidence/QoI。 | 是，只读。 |
| `derived-artifact` | 从 locked evidence 生成的图、表、段落或 QA 结果。 | 不能反向提升证据。 |
| `author-decision` | 作者对选题、证据/图件方案或最终论文的显式决定。 | 仅由真实作者动作创建。 |

### 6.2 写入矩阵

| 能力包 | 可提出 candidate/gap | 可写 locked QoI 结果 | 可读取 locked evidence | 可提升 claim ceiling | 可创建作者批准 |
|---|---:|---:|---:|---:|---:|
| `cfd-evidence-intake` | 是 | 否 | 是 | 否；只能建议降级 | 否 |
| `cfd-qoi-physics` | 是 | **仅锁定分析任务** | 是 | 否；沿用或建议降低 | 否 |
| `cfd-figure-production` | 是（图件缺口） | 否 | 是，只读 | 否 | 否 |
| `cfd-evidence-writing` | 是（论证缺口） | 否 | 是，只读 | 否 | 否 |
| `cfd-literature-evidence` | 是 | 否 | 是，只读 | 否 | 否 |
| `cfd-publication-assurance` | 是（不一致/缺口） | 否 | 是，只读 | 否 | 否 |

`cfd-evidence-intake`有一个不属于 QoI 写入的确定性职责：对版本锁定的 comparison contract 写入
`eligible`、`restricted`或`insufficient`资格结果。`eligible`允许按合同进入分析；`restricted`只允许
合同明确列出的 QoI、比较和 claim 角色，并保留验证缺口；`insufficient`不得进入 QoI 计算。该资格
结果不是 QoI、claim ceiling 或作者批准，也不需要新增 registry 或审批层。

“锁定分析任务”必须在执行前冻结 case 集、QoI 定义、输入字段、单位、scope、统计/采样窗口、
权重、missing policy、比较合同和输出目标。只有 `cfd-qoi-physics`在该任务内可写 QoI 结果；若
定义或输入改变，旧结果转为 stale，不能在绘图或写作阶段被就地改写。

Skill 可以发现更严格的证据边界并建议降低 claim ceiling，但提高 ceiling 需要新的合格证据和
产品科学层/作者决定，不能由 Skill、外部 AI、导出成功或 QA 通过自动产生。worker handoff、
checkpoint、`complete`字段和报告存在都不构成作者批准。

产品仍只有三个作者检查点：第一检查点确认选题和科学问题；第二检查点确认 evidence、claims、
图件方案及其章节职责；第三检查点确认最终论文。candidate paper spine 在第二检查点内一并确认，
不得形成第四个检查点。V0.3的单段文本产物可以把第二检查点已批准的 claim、figure 和 section
responsibility 作为最小 spine，不要求新增独立表单。

## 7. 六个首批能力包

### 7.1 `cfd-evidence-intake`

**版本：** `0.1.0-candidate`
**描述：** 将已有 CFD 结果盘点为可定位证据，先判断工况可比性、单位、收敛与守恒资格，再把
可执行分析和最小缺口交给后续 Skill。

**触发：** 新 CFD 项目接入、case/结果版本变化、用户要求比较多个工况，或后续 Skill 缺少资格
记录。
**不触发：** 已锁定证据上的单纯绘图、段落润色、文献检索或投稿格式修改。

**输入：** Project/Case/Boundary/Mesh/Field inventory；原始结果或 adapter 只读提取记录；单位；残差、
监测量、守恒或统计窗口证据；网格/时间步等 numerical verification 证据；实验、理论、参考解或
已验证模型对照等 validation 证据；用户声明的允许差异。
**前置证据：** 至少一个可定位结果源和 case identity。没有边界条件、字段单位或收敛证据时仍可
盘点，但不能给出“可比较/成熟”的结论。
**输出：** inventory summary、版本锁定 comparison contract 及其 `eligible/restricted/insufficient`
资格结果、numerical verification status、validation status、最小缺口和候选 QoI 清单；不得写
QoI 数值、claim ceiling 或作者批准。

**工作流：**

1. 识别 case、结果版本、变量、location/scope、单位和来源；
2. 按几何、材料、边界、模型、网格/采样和参考态建立允许/需解释/阻断差异；
3. 检查单位可转换性、残差/监测量、守恒闭合及稳态/统计窗口证据；
4. 分别记录 numerical verification status 和 validation status；缺失不一律阻断，而是限制可用 QoI、
   比较或 claim 角色；
5. 对版本锁定 comparison contract 确定性写入 `eligible`、`restricted`或`insufficient`；
6. 输出最小缺口，不替用户扩大数据采集或重新求解范围。

**停止条件：** 所有目标 case 已有明确资格、差异解释、verification/validation status 和相应 claim
角色；或关键输入缺失已使结果为 `insufficient`。不得在 `insufficient` 后继续推断趋势，也不得把
`restricted`写成普遍验证或工程运行边界。
**失败回退：** adapter/求解器工具不可用时，输出最小人工导出清单（对象、变量、单位、location、
统计/监测记录），不编造 inventory。
**资源：** `references/evidence-qualification.md`、`templates/comparison-contract.md`、
`templates/evidence-gap.md`。
**脚本：** `scripts/check_inventory.py`、`scripts/check_units.py`、
`scripts/check_convergence_conservation.py`、`scripts/check_verification_validation.py`；脚本只返回检查
结果，资格状态由版本锁定合同确定，不批准作者决策。

**测试与成功标准：**

- 正向 fixture：完整稳态内流多 case 结果及 verification/validation 证据；应生成 `eligible`合同。
- 受限 fixture：科学比较成立但缺少网格独立性或直接实验验证；应生成 `restricted`及允许的分析/
  claim 角色，不得一律阻断或写成已验证。
- 负向 fixture：控制体、参考态或收敛证据使比较不可成立；必须生成 `insufficient`和最小缺口。
- 跨宿主：三类 adapter 对同一版本锁定合同得到等价资格、状态和资源解析。
- 成功标准：零静默 case/单位错配；三态结果可由输入复核；不产生 QoI、ceiling 或作者批准。

**范围分类：** `V0.3 minimum-slice must-consider`，对应 S05、S08；inventory、单位和守恒是完成
这些门控的必要子步骤，不单独拆 Skill。完整 AU01 求解器 adapter 仍是条件性输入层；V0.3最小链
只需绑定现有结构化记录和 Task 9 选定的 CSV/VTK 中性入口之一，原生 Fluent/STAR adapter 延期。

### 7.2 `cfd-qoi-physics`

**版本：** `0.1.0-candidate`
**描述：** 在锁定分析任务中定义、计算和解释 QoI，并验证完整离散序列的趋势、峰值、平台和证据
不足状态。

**触发：** evidence intake 已对版本锁定 comparison contract 给出 `eligible`或`restricted`，且用户
确认科学问题或要求分析指定 QoI。
**不触发：** comparison contract 为 `insufficient`、只需要重新排版已有图，或用户要求从图像外观
猜测数值。

**输入：** 版本锁定 comparison contract 及其资格结果、锁定 analysis task、QoI 定义候选、
Field/Evidence 输入和容差/顺序。
**前置证据：** 资格为 `eligible`，或 `restricted`且合同明确允许当前 QoI、比较与 claim 角色；QoI
的公式、输入、单位、scope、窗口、weights、normalization 和 missing policy 已锁定。
**输出：** locked QoI results、trend classification、candidate physical interpretation、claim gaps；
解释与数值分层保存。

**工作流：**

1. 消费 intake 资格结果；`insufficient`立即停止，`restricted`只保留合同允许的 QoI、比较和 claim 角色；
2. 复核 QoI 合同是否能唯一决定计算与物理含义；
3. 只对锁定输入执行确定性算子，保留原始/规范单位和 missing 状态；
4. 对完整有序序列区分 monotonic、overall change、peak、plateau 和 insufficient；
5. 以守恒、特征尺度、边界条件和相关场量检查解释，列出替代机制与证据缺口；
6. 写入 locked QoI；物理解读保持 candidate，且不得越过 intake 资格限定的 claim 角色。

**停止条件：** QoI 结果、趋势分类及 `restricted`限定可复算，或合同/输入不足已使结果为
`insufficient`。稀疏离散点不得继续拟合为连续最优区。
**失败回退：** 工具缺失时保留合同并输出待运行命令；定义不唯一时只返回候选定义及其会改变的
结论，不选择“最方便”的版本。
**资源：** `references/qoi-contracts.md`、`references/trend-language.md`、
`templates/analysis-task.md`、`templates/physics-interpretation.md`。
**脚本：** `scripts/validate_qoi_contract.py`、`scripts/compute_qoi.py`、
`scripts/classify_discrete_trend.py`。

**测试与成功标准：**

- 正向 fixture：`eligible`且单位/采样完整的非单调离散扫描；应得到正确峰值和非单调措辞。
- 受限 fixture：`restricted` comparison contract 只允许方向性比较；QoI可计算，但解释和输出不得
  扩展为验证、普遍规律或工程边界。
- 负向 fixture：缺中间 case、重复横坐标、分箱均值冒充原始点或单位不一致；必须返回
  `insufficient`/阻断，不补点、不平滑。
- 跨宿主：同一脚本输入获得相同数值和趋势类别，文本允许不同但不得改变主张强度。
- 成功标准：关键数值可回到输入和算子；趋势词与全序列一致；写入仅发生于锁定分析任务。

**范围分类：** `V0.3 minimum-slice must-consider`，对应 S06、S07，并受 S10 单向传播约束；S03、
S04、S11为条件性增强，S09敏感性分析延期至 V0.4+。

### 7.3 `cfd-figure-production`

**版本：** `0.1.0-candidate`
**描述：** 从锁定 evidence/QoI 先建立 FigureContract，再生成 source data、可编辑图件和数据/叙事/
视觉三重 QA 结果。

**触发：** 用户选择论文主张或图件目标，且相应 Evidence/QoI 已锁定。
**不触发：** 只有原始图片、不可定位数字、未通过可比性门的 case，或仅要求通用装饰性图片。

**输入：** locked evidence/QoI、目标 claim ceiling、case/变量/单位、期刊或项目视觉约束、作者已
确认的本地精修副本（若存在）。
**前置证据：** 每个 panel 的数据源、变量、scope、单位和允许 claim 已确定；本地人工精修版本优先
级明确。
**输出：** FigureContract、source-data 表、可运行脚本、SVG/PDF、PNG/TIFF、caption draft 和一轮
三重 QA；全部为 derived artifact，不写回 QoI。

**工作流：**

1. 定义图的核心结论、panel 证据职责、主/辅诊断和禁止外推；
2. 从 locked evidence 导出 source data，不在绘图脚本中重新定义 QoI；
3. 根据数据结构选择图型，生成可编辑与预览格式；
4. 数据 QA 复核行数、case、单位和读数；叙事 QA 复核 panel/caption/claim；视觉 QA 复核裁切、
   字体、marker、legend、色标与人工预览；
5. 实质问题才重开一次修改；纯审美偏好交给作者本地精修。

**停止条件：** 合同—source data—脚本—图件—caption 一致且一轮 QA 无硬错误；或数据资格不足。
不进入无限美化循环。
**失败回退：** 绘图引擎/字体缺失时仍交付 FigureContract 与 source data，并给最小环境需求；不得
用截图或手工重画冒充可编辑正式图。
**资源：** `references/figure-contract.md`、`references/visual-grammar.md`、
`templates/figure-contract.md`、`assets/base-style.mplstyle`。
**脚本：** `scripts/export_source_data.py`、`scripts/build_figure.py`、`scripts/figure_qa.py`。

**测试与成功标准：**

- 正向 fixture：含多 case、单位和主/辅诊断的 locked QoI；应生成与 source data 一致的四种格式。
- 负向 fixture：错 case、错单位、缺 source row、平滑暗示连续规律或 legend 遮挡；必须失败或降级。
- 跨宿主：同一脚本和资源路径可执行；允许字体渲染细微差异，但数据、轴单位、panel角色一致。
- 成功标准：零数据/工况硬错；SVG/PDF可编辑、PNG/TIFF可预览；QA不提升claim ceiling。

**范围分类：** `V0.3 minimum-slice must-consider`，对应 PW01、PW02；Matplotlib直接复用、样式分层
只借鉴 SciencePlots，不能把“套样式”当出版质量。

### 7.4 `cfd-evidence-writing`

**版本：** `0.1.0-candidate`
**描述：** 以作者批准的选题和 locked evidence 为起点生成 candidate paper spine；只有该 spine
经作者真实批准后，才生成章节职责明确、数值可反链且不越过 claim ceiling 的论文文本。

**触发：** 分为两个互斥入口：已有 author-approved topic 但尚无批准 spine 时，只进入 spine 候选
子流程；已有 author-approved spine 且用户要求撰写/修订指定章节时，才进入章节写作子流程。
**不触发：** 要求系统从零发明研究问题、case 仍不合格、没有证据 locator，或只有“写得像论文”
的语言需求而无技术输入。

**输入：** author-approved topic、可选的 author-approved spine，或第二作者检查点已批准的
claim/figure/section responsibility；另需 locked Evidence/QoI/Figure、claim ceiling、术语表和已
验证文献角色。
**前置证据：** spine 候选所用核心 claim 必须绑定 locator；章节写作还要求第二作者检查点已批准
spine，或已批准的 claim/figure/section responsibility 足以构成 V0.3 单段产物的最小 spine，且数字
来自 locked record。
**输出：** candidate paper spine；获得作者批准后才可输出 section draft、claim–evidence mapping、
numeric backlinks 和未解决 gap。不修改任何锁定数据、图件或文献角色。

**工作流：**

1. 从 author-approved topic、locked claims/evidence/figures 生成 candidate paper spine，明确章节职责
   和“发现—证据—机制—工程含义”链条；
2. 将 candidate spine 与 evidence、claims、图件方案和章节职责一并交给第二作者检查点并停止；
   不新增第四个批准门，也不得用任务状态、worker 结论或 Skill 自评代替批准；
3. 第二作者检查点通过后，才为指定章节/段落选择已锁定 claim/evidence/figure；V0.3单段产物可直接
   使用该检查点已批准的 claim/figure/section responsibility 作为最小 spine，无需额外表单；
4. 从记录渲染数字、单位、case ID 和图号，以自然、克制的学术语言写作；
5. 回读数字、术语、图文引用和 claim ceiling；未支持句转为 gap 或删除。

**停止条件：** candidate spine 生成后立即停在第二作者检查点；该检查点未批准 spine 或等价的
claim/figure/section responsibility 时不得开始章节写作。批准后，指定章节完成反链和职责检查或
任何核心 claim 缺少支持时停止，不自动扩写未请求章节或循环自我润色。
**失败回退：** topic 已批准但证据不足时只返回 spine gap；candidate spine 未批准时只返回候选
结构及需作者决定的分歧；文献角色未验证时保留 claim gap，不生成伪引用或手填参考文献事实。
**资源：** `references/section-responsibilities.md`、`references/claim-language.md`、
`templates/paper-spine.md`、`templates/section-draft.md`。
**脚本：** `scripts/render_locked_values.py`、`scripts/check_numeric_backlinks.py`、
`scripts/check_claim_evidence_links.py`。

**测试与成功标准：**

- 正向 fixture：author-approved topic 无 spine 时只生成 candidate spine；同一 fixture 在第二作者
  检查点批准完整 spine，或批准单段所需 claim/figure/section responsibility 后，才生成一致段落。
- 负向 fixture：证据弱于目标 claim、旧版数字、未批准 spine 或引用只存在无 locator；必须降级或
  停写，且未批准 spine 时不得出现 section draft。
- 跨宿主：spine 状态门禁必须一致；段落措辞可不同，但数字、单位、case、引用角色、段落职责和
  ceiling 必须等价。
- 成功标准：candidate spine 不冒充第二作者检查点批准；不新增第四个门或表单；批准前零章节写入；
  批准后零数值/单位/case 硬错，每个核心 claim 有 locator，且无 Skill 自建作者批准。

**范围分类：** PW04 为 `V0.3 minimum-slice must-consider`，但 V0.3 只需验证一个受证据约束的
文本产物；完整 paper spine/全稿生产为 conditional，不能据本设计提前冻结。

### 7.5 `cfd-literature-evidence`

**版本：** `0.1.0-candidate`
**描述：** 围绕明确 claim 查找和核验原始文献位置、适用范围与论文角色，向写作 Skill 提供候选
或已验证的文献证据，而不是代写事实。

**触发：** paper spine/section 中存在明确文献问题、claim gap 或作者要求核验某一引用角色。
**不触发：** 泛化“多找一些文献”、没有科学问题的全文堆引，或把 embedding/摘要当证据。

**输入：** claim/question、适用研究对象/工况/方法、现有文献库和允许的数据出站边界。
**前置证据：** 明确的 claim 和所需文献角色；若只知道关键词，输出保持 candidate。
**输出：** literature evidence table、原文 locator、支持/限制/冲突角色、版本与作者纳入建议；不写
主稿、不改变 CFD claim ceiling。

**工作流：**

1. 先按项目、版本、研究对象和文献角色做结构化过滤，再做全文/可选语义召回；
2. 回到原始论文、官方代码或权威来源定位支持文本/方法；
3. 区分直接支持、机制类比、背景、冲突和不适用；
4. 无法定位或超范围时删除候选引用并记录 gap；
5. 由作者决定纳入，写作 Skill只读取已验证角色。

**停止条件：** 当前 claim 已有足够且角色明确的来源，或公开证据不足。不得为增加引用数量无限
搜索。
**失败回退：** 无全文/联网工具时输出准确检索式和待核验来源，不用二手摘要补齐原文定位。
**资源：** `references/literature-role-taxonomy.md`、`templates/literature-evidence-table.md`。
**脚本：** `scripts/check_source_locators.py`、`scripts/check_citation_identity.py`；语义检索只负责召回。

**测试与成功标准：**

- 正向 fixture：目标 claim 有原始文献与适用范围；应返回正确 locator 和角色。
- 负向 fixture：相似标题、错误版本、撤稿、摘要支持但全文不支持或研究对象不可迁移；不得晋升。
- 跨宿主：来源身份、locator和角色一致；召回排序差异不能改变“是否可用”。
- 成功标准：零伪造引用；所有可用来源可定位；检索结果不改变 CFD evidence 等级。

**范围分类：** 对应 PW03，`defer to V0.4+`。V0.3 可以继续使用现有明确来源输入，不应为完整
文献工作区扩大当前最小切片。

### 7.6 `cfd-publication-assurance`

**版本：** `0.1.0-candidate`
**描述：** 在已有论文产物上执行跨文档一致性和提交前审查；仅在真实决定信/审稿意见到达后建立
事件驱动的返修矩阵。

**触发：** 多章节/图表/补充材料已存在且用户要求提交前审查；或用户提供真实决定信、审稿意见。
**不触发：** 草稿尚未形成、仅想提前模拟无限审稿、没有真实审稿事件却要求进入 revision。

**输入：** locked manuscript artifacts、figures/tables/source data、reference records、journal constraints；
返修模式另需真实 decision letter/comments 和作者策略。
**前置证据：** 被审对象及其版本明确；返修必须有真实外部事件。
**输出：** scoped cross-document findings、pre-submission findings；返修时输出 comment matrix、候选
response 和修改传播清单。QA/response 都不直接改 locked evidence。

**工作流：**

1. 根据输入类型选择 cross-document、pre-submission 或 revision 子流程；
2. 核查数值、单位、case、术语、图表/补充材料引用和文献角色传播；
3. 仅报告影响科学正确性、读者理解或真实提交的发现，纯偏好不扩展；
4. 返修时将每条意见映射为接受、部分接受、澄清或证据型反驳候选，并定位所需修改；
5. 作者决定策略后才生成最终回复；修改声明必须能在实际文件中找到。

**停止条件：** 一轮目标范围审查完成且没有硬错误；或阻断项已明确交回作者。不得开启无限模拟
复评。返修在该轮真实意见闭合后停止。
**失败回退：** 文档版本不明时先返回权威版本缺口；无法解析 DOCX/LaTeX 时给最小人工导出要求，
不根据旧 PDF 猜行号或修改状态。
**资源：** `references/cross-document-qa.md`、`references/revision-strategy.md`、
`templates/reviewer-comment-matrix.md`。
**脚本：** `scripts/check_cross_document_refs.py`、`scripts/check_numeric_propagation.py`、
`scripts/parse_reviewer_comments.py`。

**测试与成功标准：**

- 正向 fixture：主稿、补充材料和回复信包含同一锁定数字与真实审稿意见；应正确映射并定位修改。
- 负向 fixture：旧版稿件、计划冒充修改完成、没有决定信触发 revision、引用编号漂移；必须阻断。
- 跨宿主：发现集合和证据位置等价；回复语言可不同但策略、事实和边界一致。
- 成功标准：零虚假“已修改/已批准”；所有修改声明可定位；无真实事件时不启动返修。

**范围分类：** cross-document QA 为多产物形成后的 `conditional`；完整 pre-submission、真实 DOCX/
LaTeX 交付和 event-driven revision 与 PW05 一并 `defer to V0.4+`，不进入 V0.3 最小切片。

## 8. 阶段组合与重叠控制

| 项目状态/用户事件 | 主 Skill | 允许的只读辅助 | 明确禁止 |
|---|---|---|---|
| 新项目或结果版本变化 | `cfd-evidence-intake` | 无 | 直接生成趋势、图或论文。 |
| 合格 case 与锁定分析任务 | `cfd-qoi-physics` | intake 资格记录 | 绘图/写作修改 QoI。 |
| 作者选择图件目标 | `cfd-figure-production` | qoi 结果 | 绘图脚本重定义指标。 |
| 作者批准 paper spine/章节 | `cfd-evidence-writing` | literature evidence | 写作提升 ceiling 或补造引用。 |
| 明确文献问题 | `cfd-literature-evidence` | writing claim context | 泛化无停止检索。 |
| 多文档提交前审查 | `cfd-publication-assurance` | 前五类锁定产物 | QA 自动修数据或批准提交。 |
| 真实决定信/审稿意见到达 | `cfd-publication-assurance` revision 子流程 | 文献/写作只读支持 | 在事件前模拟返修或无限自审。 |

S10“Evidence 到 claim ceiling 单向传播”不是第七个 Skill，而是六个 Skill 的共同不变量；RP02 的
checkpoint/真实 interrupt 也属于宿主/项目状态能力，不包装成 Skill。这样既保留科学与作者边界，
又避免恢复 V1 的 promotion registry 和多层审批。

## 9. 测试、评价和跨宿主回放

### 9.1 每个 Skill 的最低测试集

每个包至少包含：

1. **正向 fixture**：输入成熟且应产生目标产物；
2. **负向 fixture**：缺字段、不可比、弱证据或错误事件，必须停止/降级；
3. **对抗 fixture**：要求跳过科学门、伪造作者批准、补点、平滑或伪造引用；
4. **跨宿主解析 fixture**：Codex、Claude、TRAE adapter 对元数据、相对路径、输入和停止语义解析
   等价；
5. **真实任务成功标准**：关键数值、单位、case、locator和claim边界无硬错误，而非“文件存在”。

公开 fixture 应至少覆盖稳态单相内流、换热和瞬态/多相三类通用场景。另可使用角色化的
`authorized internal positive regression` 与 `authorized internal negative scientific-gate regression`
补充内部回归，但不包含原始资产，也不进入公开 Skill 包或外部评审材料。

### 9.2 评价维度

| 维度 | 核心问题 |
|---|---|
| 触发精度 | 应触发时是否发现，邻近任务是否拒绝，重叠是否只选一个主 Skill？ |
| 科学正确性 | 是否阻断不可比/弱证据，QoI与趋势是否正确，是否尊重 claim ceiling？ |
| 产物价值 | 是否产生可直接进入下一阶段的合同、数据、图件或文本，而非内部过程报告？ |
| 回退质量 | 工具或证据缺失时是否给出最小可执行缺口，而不是猜测结果？ |
| 跨宿主一致性 | 科学结果、停止和权限边界是否等价？ |
| 上下文效率 | 是否只加载当前步骤需要的 Level 2/3，避免长全局提示？ |

### 9.3 通过标准

- 负向/对抗 fixture 中不得产生 locked QoI、强 claim、作者批准或“投稿就绪”；
- 正向 fixture 的关键数值、单位、case、scope、趋势类别和 locator 必须与 oracle 一致；
- 跨宿主输出可语言不同，但结构化事实和权限边界必须一致；
- Skill 相较无 Skill 基线必须至少减少一种重复硬错误或显著降低完成该任务所需人工重做；
- 只通过 frontmatter/schema/安装测试而未通过真实 CFD fixture 的 Skill 不得发布。

## 10. Shrink-to-fit：精简、合并和淘汰

Skill 不永久累积。每个候选在进入内置集前必须同时满足：

1. 任务真实且在多个 CFD 项目中重复出现；
2. 基础模型在无 Skill 回放中不能稳定完成；
3. Skill 相比基线有可测收益，并阻止或减少实际硬错误；
4. 能定义清楚输入、输出、停止和失败回退；
5. 与现有 Skill 的重叠不能通过一个 reference、template 或脚本解决。

每次产品版本评估时：

- 若两个 Skill 经常共同触发且共享前置/产物，合并为一个能力包；
- 若能力只剩格式偏好，移入普通指南或模板；
- 若基础模型在所有支持宿主的正/负/对抗回放中已稳定达到同等结果，删除 Skill 或仅保留确定性脚本；
- 若真实项目长期不触发、缺少成功 fixture 或维护成本高于收益，降为 optional/deprecated；
- 淘汰不得删除仍用于解释旧项目的版本记录，但无需建立额外 registry；版本控制和 release notes 足够。

## 11. V0.3 最小集与延期边界

| 能力包 | Task 7 对应 | V0.3 建议 | 本阶段最低证明 |
|---|---|---|---|
| `cfd-evidence-intake` | S05、S08；AU01 conditional | **must-consider** | 中性输入进入三态资格；不足能在分析前停止。 |
| `cfd-qoi-physics` | S06、S07、S10 | **must-consider** | 锁定 QoI + 全序列趋势，无越权写入。 |
| `cfd-figure-production` | PW01、PW02 | **must-consider** | 一个 FigureContract 到四格式图件与三重 QA。 |
| `cfd-evidence-writing` | PW04、S10 | **must-consider（最小文本产物）** | 一个有反链的章节/结果段，不承诺全稿。 |
| `cfd-literature-evidence` | PW03 | **defer to V0.4+** | 先保留接口；不在 V0.3 建完整文献工作区。 |
| `cfd-publication-assurance` | PW05；跨文档/返修需求 | **conditional / defer to V0.4+** | 多产物出现后再启用 cross-document QA；真实返修与完整导出延期。 |

V0.3候选最小链为：

```text
cfd-evidence-intake
  → cfd-qoi-physics
    → cfd-figure-production
    → cfd-evidence-writing (one evidence-bound text artifact)
```

这条链映射 Task 7 的 `S05 + S08 → S06 + S07 → S10 → PW01 + PW02 → PW04最小文本产物`。
Task 9 必须为该链绑定至少一个已实现的中性输入入口：现有结构化记录加 CSV 或 VTK 之一，具体选择
由 Task 9 冻结；原生 Fluent/STAR adapter 不属于 V0.3 最小链。
Task 9 仍须在资源、依赖和验收层进一步缩小或调整，不能把本设计误读为六个 Skill 已全部获准
进入 V0.3 实现。

## 12. 来源与迁移决定

- [OMF Skills](04_DEEP_DIVE_REPORTS/open-source/openmodelingfoundation__skills.md)：重实现短元数据、
  `SKILL.md`入口、按需 resources/scripts/templates、gotcha 和正/负/对抗 eval；不复制无关方法全文。
- [OpenSkill](04_DEEP_DIVE_REPORTS/open-source/vudknguyen__openskill.md)：只借鉴跨宿主路径 adapter、
  project scope 和失败回退思想；不建设 marketplace、遥测或全局 registry。
- [LangGraph](04_DEEP_DIVE_REPORTS/open-source/langchain-ai__langgraph.md)：只借鉴真实 interrupt/resume 和
  可恢复阶段语义；不引入通用图运行时，也不把 checkpoint 当证据。
- [data-to-paper](04_DEEP_DIVE_REPORTS/open-source/Technion-Kishony-lab__data-to-paper.md)：重实现阶段产物和
  数值反链；拒绝自动发明研究问题与端到端自动论文。
- [STORM](04_DEEP_DIVE_REPORTS/open-source/stanford-oval__storm.md)：只借鉴资料/问题先于提纲；不并行
  自动写 section，不用多视角提高 CFD 证据等级。
- [PaperQA2](04_DEEP_DIVE_REPORTS/open-source/Future-House__paper-qa.md)：借鉴 locator 和无法映射即失败；
  embedding仅用于找材料。
- [Matplotlib](04_DEEP_DIVE_REPORTS/open-source/matplotlib__matplotlib.md)和
  [SciencePlots](04_DEEP_DIVE_REPORTS/open-source/garrettj403__SciencePlots.md)：前者作为绘图引擎，后者
  只提供样式分层思想；FigureContract、source data 和三重 QA 由本产品负责。

上述设计只保留能改善真实 CFD 证据理解、图件或写作的机制。宿主适配、版本和必要边界服务于
执行，不形成面向用户的治理主流程。
