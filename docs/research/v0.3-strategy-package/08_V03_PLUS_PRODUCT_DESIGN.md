# CFD-Paper-Agent V0.3+ 产品设计候选

日期：2026-09-01
基线：CFD-Paper-Agent v0.2.0
状态：外部评审候选；未授权开始 V0.3 代码实现

## 1. 产品目标

V0.3 不尝试一次交付“CFD 到全稿”。它只验证一条有用且可验收的纵向链：

> 已有成熟 CFD 结果的结构化记录与 CSV 观察表 → 科学资格判断 → 锁定 QoI 与全序列
> 趋势 → claim ceiling → 一张可编辑图件 → 一个受证据约束的结果段落。

这条链的价值不在于生成更多文件，而在于首次让公开产品从“可辩护选题”进入“可复核分析与论文产
物”，同时保持缺失证据、不可比工况和过强主张可以明确停止流程。

## 2. 外部研究导出的核心取舍

| 决策 | 研究依据 | V0.3 处理 |
|---|---|---|
| 使用自描述数据，但不把“可读取”写成“科学有效” | PyDPF-Core、PyVista、xarray | 仅支持结构化记录与规范 CSV；来源、case、单位和 scope 必须显式。 |
| 量纲通过不等于可比 | Pint、xarray 及历史负向回放 | 单位检查位于 comparison contract 内，几何/材料/边界/模型/采样差异仍独立判断。 |
| 派生量必须保留算子和完整序列 | PyDPF workflow、SALib、xarray | QoI 合同锁定公式、输入、scope、权重、序列顺序与 missing policy；不用端点代替全序列。 |
| 图件先有科学合同，再调用绘图引擎 | Matplotlib、PyVista、SciencePlots | 复用 Matplotlib；重实现 FigureContract、source data 及数据/叙事/视觉三重 QA。 |
| 文字从锁定证据渲染，不从模型记忆复制数字 | data-to-paper、PaperQA2 | 只生成一个结果段落；数值、单位、case 与图号必须可反链。 |
| Skill 是按需加载的能力单元，不是长提示词或市场 | OMF Skills、OpenSkill | 只实现前四个能力包的窄模式，不建 marketplace、全局 registry 或遥测。 |
| 状态恢复不能制造科学或作者批准 | LangGraph、LlamaIndex | 沿用现有本地 SQLite/checkpoint；不引入通用 Agent 图运行时。 |

## 3. 六层产品边界

六层是责任边界，不是六个新框架。数据依赖顺序为“适配层 → 证据层 → 科学分析层 →
图件/写作层”；Skill 层只在该顺序上加载工作流，用户编排层只暴露必要决策。

### 3.1 证据层

| 项目 | 边界 |
|---|---|
| 输入 | v0.2 现有的 Project/Case/Boundary/Mesh/Convergence/Conservation/QoI-definition/Source 结构化记录；适配层输出的 CSV 观察行。 |
| 输出 | 锁定的 source locator、Field/Observation record、comparison contract、`eligible/restricted/insufficient` 资格、numerical verification status、validation status 和最小缺口。 |
| 依赖 | 适配层只读解析；现有 SQLite 项目状态；按科学角色分类并带依据的 case 差异。 |
| 禁止 | 不从文件名、列名或图像猜求解器语义；不填补缺失单位/边界/收敛数据；不写 QoI 结果、claim 或作者批准。 |

`numerical verification status`与`validation status`独立记录，各自只使用
`demonstrated / partial / not-demonstrated / not-applicable`。每个状态必须有 locator 或明确缺口。
`eligible`不自动意味已验证；`restricted`保留合同列出的 QoI、比较和 claim 角色；
`insufficient`停止后续数值分析。

- 不可转换或语义歧义的单位、缺失 source locator、不可比 case、重复序列坐标或缺失 QoI 计算必需点均归为`insufficient`。
- comparison contract 的每项差异必须归入`intended-study-factor`、
  `demonstrated-equivalent-or-immaterial`、`unresolved-nuisance`或`blocking`。作者可以定义研究因素和
  提供等价/无实质影响依据，但不能用“允许”把未解决干扰洗成受控变量；未解决干扰至少为
  `restricted`，破坏目标 QoI/比较时为`insufficient`。
- 缺失 numerical verification/validation 证据或有依据的非阻断差异归为`restricted`。
- 守恒与收敛只能按预先写入合同、带`basis`和`source_locator`的项目显式阈值判定：超过阻断阈值时
  为`insufficient`，只达到限制阈值时为`restricted`；没有依据时不能取得`eligible`。

numerical verification 与 validation 沿用 [NASA Glenn 基于 AIAA G-077 的 CFD V&V 区分](https://www.grc.nasa.gov/www/wind/valid/tutorial/tutorial.html)：前者检查模型实现和
计算解是否按预期求得，包括迭代、守恒/一致性及适用的空间/时间收敛；后者针对 intended use 判断模型
对现实的代表程度。`partial`列出已完成和缺失项；`not-applicable`需要说明该评估为何与当前
claim/intended use 无关，不能代替缺证据，manuscript-facing physical claim 也不能借此绕开 validation
缺口。

### 3.2 科学分析层

| 项目 | 边界 |
|---|---|
| 输入 | `eligible`或明确允许当前分析的`restricted` comparison contract；锁定的 QoI 定义；expected 与 observed membership 均明确的完整有序 CSV 观察。 |
| 输出 | locked QoI results、全序列趋势分类、候选物理解释、claim gaps 和不可超越的 claim ceiling。 |
| 依赖 | 证据层资格；显式单位模型；受限确定性运算；项目声明的 expected case/coordinate set、顺序、趋势容差、最小样本数和 missing policy。 |
| 禁止 | 不在绘图或写作时重新定义 QoI；不补点、平滑或把稀疏离散工况写成连续最优区；不因单位正确、程序运行或作者选择提高 ceiling。 |

V0.3 默认把 CSV `value`当作已导出观察；每行必须声明`value_role`为`raw-sample`、
`declared-aggregate`或`precomputed-qoi`。允许的确定性运算仅限合同写明的单位转换、声明聚合的重算/
核对及全序列趋势分类；不得从点列猜测控制体积分、面积加权或场算子，也不得由模型发明公式。

趋势词只允许`monotonic`、`overall change`、`peak`、`plateau`和`insufficient`。完整性先比较第一检查点
锁定的 expected case IDs/sequence coordinates 与 observed rows；缺整 case、缺必需变量或重复坐标均为
`insufficient`。`monotonic`、`peak`和`plateau`至少需要三个不同序列坐标和已锁定的
`trend_tolerance`；未满足时只允许`overall change`或`insufficient`。非均匀坐标不插值，只按有序相邻
差与合同定义判断。物理解释保持 candidate，不与数值结果合并为“已证明机理”。

claim ceiling 使用四档封闭映射：`no-numerical-claim`、`directional-comparison`、
`qualified-numerical-observation`和`supported-physical-interpretation`。`insufficient`只能进入第一档；
`restricted`只能进入合同明确允许的第二档或带限制的第三档；第四档需要适用的 qualification、
numerical verification、validation/intended-use 边界和第二检查点批准。缺 validation 时仍可报告限定的
数值预测，但不得写成实验确认、工程边界或通用规律。

### 3.3 图件/写作层

| 项目 | 边界 |
|---|---|
| 输入 | locked evidence/QoI、claim ceiling，以及第二作者检查点确认的 claim、candidate FigureContract 和最小段落职责。 |
| 输出 | 锁定的 FigureContract、source-data CSV、可运行 Matplotlib 脚本、可编辑 SVG、PNG 预览、图注候选、三重 QA 结果；一个带 numeric backlinks 的结果段落。 |
| 依赖 | 科学分析层锁定记录；Matplotlib 兼容版本；第二作者检查点。 |
| 禁止 | 不修改锁定数值、单位、case 或文献角色；不自动扩写其他章节；不产生完整论文、文献工作区、DOCX/LaTeX 投稿包或“可投稿”结论。 |

数据 QA 重算图中关键读数；叙事 QA 检查 panel/图注/段落是否超越 ceiling；视觉 QA 只检查
裁切、字体、坐标、单位、legend 和可读性。自动 QA 只运行一轮；实质硬错才重开，审美精修由
作者决定。

### 3.4 Skill 层

| 项目 | 边界 |
|---|---|
| 输入 | 当前用户意图、项目阶段、Level 1 元数据与已成熟的上游产物。 |
| 输出 | 被选中能力包的 Level 2 工作流，以及按需加载的 Level 3 脚本/模板/参考；结构化返回上述层的真实产物。 |
| 依赖 | Task 8 前四个能力包：`cfd-evidence-intake`、`cfd-qoi-physics`、`cfd-figure-production`、`cfd-evidence-writing`。 |
| 禁止 | 不将 adapter、checkpoint 或导出器包装成 Skill；不创建 marketplace/遥测/全局 registry；不扫描当前步骤不需要的全部 Level 3；不生成作者批准或提高 ceiling。 |

V0.3 只实现这四个能力包服务最小纵向链所需的窄模式，不承诺 Task 8 中所有
参考、脚本、模板和跨宿主支持都在该版本交付。

### 3.5 适配层

| 项目 | 边界 |
|---|---|
| 输入 | 作者从已有成熟结果导出的规范 CSV，以及 v0.2 现有结构化科学记录。 |
| 输出 | 只读观察行：`case_id`、序列坐标/工况参数、`variable`、`value`、`value_role`、`unit`、`scope/location`、`source_locator`和可选统计窗口。 |
| 依赖 | Python 标准 CSV 解析与现有契约；单位层；明确的人工导出说明。 |
| 禁止 | 不自动推断任意列的科学含义；不读写原始求解文件；不执行求解；不宣称支持 VTK、Fluent、STAR-CCM+ 或其他原生语义。 |

CSV 是 V0.3 唯一新增中性入口。不支持“任意 CSV”：列名、单位、case 和来源不完整时，
adapter 返回最小人工导出清单。完整场、非结构网格和三维场图进入后续 VTK/原生适配版本。

### 3.6 用户编排层

| 项目 | 边界 |
|---|---|
| 输入 | 用户命令、现有 v0.2 项目状态、真实作者决定。 |
| 输出 | 与当前阶段相关的最少问题、产物预览、恢复点和三个作者检查点。 |
| 依赖 | 现有 Typer CLI、SQLite/checkpoint、Skill 选择结果与六层产物状态。 |
| 禁止 | 不显示 L0–L4、promotion、registry 或内部哈希过程；不用`complete`或 worker 报告代替作者决定；不自动提交、申诉或触发返修。 |

## 4. V0.3 最小用户流程

### 4.1 真实输入

1. v0.2 已支持的成熟结构化记录；若首次用户只有成熟导出结果，guided intake 用研究者可理解的问题
   收集 case identity、目标比较因素、几何/材料/边界/模型差异、收敛/守恒证据和 source locator，
   写入现有 records，而不要求用户理解内部 schema；不能判断的内容保持 gap；
2. 一份规范 CSV 观察表，包含完整 case 序列、变量、数值、单位、scope 和 source locator；
3. 作者批准的选题/科学问题，或由 v0.2 `plan` 生成并在第一检查点确认的候选。

系统使用 author-approved scientific question、observed fields 和可用 candidate QoIs 生成 candidate QoI contract；作者在第一检查点确认公式、输入、单位、scope、序列顺序/容差和 missing policy 后才锁定。用户不需要预先手写未定义的`qoi-definition.json`。

### 4.2 CLI 与产物

```text
cfdpaper inspect PROJECT_ROOT
cfdpaper qualify PROJECT_ROOT --observations observations.csv
cfdpaper analyze PROJECT_ROOT
cfdpaper figure PROJECT_ROOT --analysis ANALYSIS_ID
cfdpaper write PROJECT_ROOT --artifact results-paragraph
```

- `inspect`保留 v0.2 的项目索引、新鲜度和资料状态语义，不把文件存在写成科学资格。
- `qualify`校验 CSV 和 scientific-record 契约，生成资格候选、最小修正请求和 candidate QoI contract，
  不自动确认科学语义。
- `analyze` 只在第一个作者检查点锁定 QoI contract 后执行，写入 comparison qualification、verification/validation status、locked QoI results、趋势类别和 ceiling。
- `figure` 只生成一份 FigureContract 对应的 source data、脚本、SVG、PNG、图注候选和三重 QA。
- `write` 只生成一个已批准职责下的结果段落及 numeric backlinks。

具体 CLI 参数在实现规格中冻结；本文只固定用户可见顺序与能力边界，不将示例语法视为已交付 API。

### 4.3 三个作者检查点

1. **选题、科学问题与 QoI 合同：** 先确认要解释的对比、主变量与不宣称内容，再审阅系统据此和 observed fields/candidate QoIs 生成的 candidate QoI contract；确认后锁定，再进入`analyze`。
2. **证据、claims 与图件方案：** `analyze`完成后先生成 candidate FigureContract；作者一次性确认
   qualification、verification/validation status、QoI、ceiling、candidate FigureContract 及单段职责。
   通过后才锁定 FigureContract，并允许`figure`和`write`消费这些批准对象。
3. **最终产物：** 预览图件、图注和结果段，由作者确认是否接受或返回实质问题。

第二检查点内的单段职责就是最小 spine，不新增第四个审批对象。

## 5. V0.3 验收合同

### 5.1 正向验收

- 一个公开、非敏感、带完整序列的稳态单相内流 fixture 贯通四条 CLI 路径；
- 资格、verification/validation status、QoI、单位、序列和 claim ceiling 与 oracle 一致；
- 生成一份可编辑 SVG、PNG 预览、source-data CSV、可运行脚本与一轮三重 QA；
- 生成一个结果段，关键数值、单位、case、图号和 claim 均可反链；
- 中断后可从当前阶段恢复，不重做已锁定分析。

### 5.2 负向验收

- 不可转换或歧义单位、无 locator、不可比 case、expected membership 缺失、重复序列坐标、
  `value_role`与合同不符或缺 QoI 计算必需点必须返回`insufficient`并停止分析；
- 缺 verification/validation 或合同允许的非阻断差异返回`restricted`；守恒/收敛按显式阈值返回`insufficient`或`restricted`；
- 无 basis/locator 的收敛或守恒阈值不能取得`eligible`；guided intake 不提供隐藏默认科学阈值，只返回
  `restricted`/`insufficient`及最小可补材料；
- 端点改善但中间点反转、样本少于三个或未锁定 trend tolerance 时，不得生成`monotonic`、`peak`或
  `plateau`；
- 缺 validation 时不得写成实验确认、工程边界或通用规律；
- 图件成功导出或 QA 通过不得提高 ceiling；
- 未通过第二作者检查点时，不得产生结果段落。
- 修改 observation CSV、expected case set、QoI/comparison contract 或单位定义后，下游 analysis、
  FigureContract、图件和段落必须 stale；`figure`和`write`不得消费旧产物。输入未变时才允许从检查点恢复。

### 5.3 产品不宣称的能力

V0.3 不宣称：任意 CSV 自动理解；原生求解器读取；三维场分析；通用敏感性/不确定性；自动文献核验；完整
论文生成；DOCX/LaTeX 投稿包；投稿前自审；返修、申诉或投稿操作；连续最优区、稳定边界或工程验证。

## 6. 最小依赖与实现约束

- 继续使用 Python 3.10–3.12、Typer、Pydantic、SQLite 和现有项目对象。
- CSV 入口使用 Python 标准库；V0.3 同时提供覆盖公开 fixture 与 Quickstart 的最小显式单位/量纲表，
  支持表内换算并对未知、歧义或量纲不兼容单位 fail closed。只有真实回放证明超出该表的需求后才固定
  Pint 兼容版本，不在当前版本假装具备通用单位系统。
- 绘图使用 Matplotlib 兼容版本；不引入 SciencePlots、LangGraph、LlamaIndex、Quarto、python-docx 或 VTK 作为 V0.3 必需依赖。
- V0.3 核心结果段由受限 renderer 生成结构化、带 numeric backlinks 的候选文本；宿主模型润色可选，
  但 provider transport、跨宿主运行时和自由生成不构成成功条件，也不得改变数值、趋势和 ceiling。
- 不新建通用 workflow engine、向量数据库、Skill marketplace、评分平台或多层审批。
- 原始结果只读；所有新产物写入项目 `.cfdpaper/outputs/`，不覆盖输入。

## 7. 资源预算

55/25/10/10 是组合级实现与验证预算，不是文件数或代码行数指标。

| 份额 | V0.3 投入 | 验收证据 |
|---:|---|---|
| 55% | comparison qualification、verification/validation status、QoI 合同、单位、守恒/收敛、全序列趋势、ceiling 及物理解释边界 | 正/负科学 fixture 和 oracle；硬错必须在绘图前被阻断。 |
| 25% | FigureContract、source data、Matplotlib SVG/PNG、三重 QA、单段反链写作 | 图-数据-段落一致；可编辑图件和受证据约束文本。 |
| 10% | 规范 CSV 入口、输入错误反馈、CLI 向导与最小 Skill 发现 | 新用户按示例能进入流程；坏列/缺单位返回可执行的最小修正。 |
| 10% | 来源定位、只读输入、原子产物、阶段恢复、三作者检查点与必要回归 | 中断恢复、陈旧输入失效、真实作者决定与不覆盖源文件。 |

## 8. 当前决策状态

本设计只是依据公开对标和现有历史抽象得出的外部评审候选。下一步是组装评审包并接收真实外部
评审；仅在评审归并且作者书面批准后，才可建立 V0.3 实现规格和开发分支。
