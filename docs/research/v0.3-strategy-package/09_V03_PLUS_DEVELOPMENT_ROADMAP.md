# CFD-Paper-Agent V0.3+ 开发路线图候选

日期：2026-09-01
基线：CFD-Paper-Agent v0.2.0
状态：外部评审候选；版本范围尚未构成实现授权

## 1. 路线原则

1. 每个公开版本只新增可运行、可测试、可向用户解释的能力。
2. 版本名只使用正式能力号，不用内部 Gate、RC、晋升或审计词汇。
3. 后续版本只依赖前一版真实产物；文档或接口存在不等于能力已交付。
4. 科学资格失败时，产品可以交付最小缺口；不为完成版本演示而伪造正向结果。
5. 每个版本仍只保留三个作者检查点，后台恢复与来源记录不得转化成新的前台审批层。

## 2. 版本方向图

```text
v0.2.0  evidence-bounded topic planning
   └─ v0.3.0  structured CSV evidence → QoI/trend → one figure + one results paragraph
        └─ v0.4.0  VTK field workspace + literature evidence + multi-figure/section manuscript workspace
             └─ v0.5.0  real DOCX/LaTeX delivery + pre-submission review + event-driven revision
                  └─ v0.6.0  optional native solver adapters + heterogeneous real-project validation
                       └─ v1.0.0  stable author-in-the-loop CFD paper workflow
```

V0.3 是唯一已在本包中给出可验收范围的下一版。V0.4–V0.6 只是 conditional capability horizons，不是已冻结发布或 backlog。每个下一版的范围必须等前一版真实用户反馈确认一个主要瓶颈后再拆分、写规格并获得作者批准。第4–6节列出的能力只是候选方向，不得被共同视为同一版本的验收承诺。

## 3. v0.3.0：证据到图文的最小纵向链

| 项目 | 定义 |
|---|---|
| 用户输入 | v0.2 成熟结构化记录；一份带`value_role`和 expected case/coordinate set 的规范 CSV 观察表；作者批准的科学问题。首次用户可通过 guided intake 把已有 case、边界、模型、收敛/守恒和来源信息写入现有 records，不要求理解内部 schema 或预先手写 QoI 定义。 |
| CLI/界面 | `inspect`保留 v0.2 项目/文件状态语义；新增`qualify --observations`生成资格候选、最小修正请求和 candidate QoI contract；第一检查点锁定后运行`analyze`，形成 candidate FigureContract；第二检查点批准后才允许`figure`和`write --artifact results-paragraph`。 |
| 输出 | qualification 与 verification/validation status；locked QoI 和全序列趋势；FigureContract、source data、脚本、SVG/PNG、图注与三重 QA；一个反链结果段。 |
| 作者检查点 | ①选题/问题与 candidate QoI contract 确认锁定；②证据、claim、ceiling、candidate FigureContract 与段落职责；③最终图、图注与段落。 |
| 验收 | 一个公开稳态单相内流正/负 fixture；不可转换/歧义单位、无 locator、不可比 case、expected membership 缺失、重复序列坐标、错`value_role`或缺 QoI 必需点必须`insufficient`；缺 verification/validation、无依据阈值或未解决干扰必须限制/阻断；趋势与四档 ceiling 符合 oracle；科学输入变化使下游 stale；单位、case、QoI、图和段落零硬错。 |
| 不宣称 | 不支持任意 CSV、VTK/三维场、原生求解器、全稿、自动文献、DOCX/LaTeX、自审/返修、工程验证或自动提交。 |

### v0.3.0 实现工作包

| 顺序 | 工作包 | 依赖 | 完成判据 |
|---:|---|---|---|
| 1 | 规范 CSV 观察入口、最小单位表、guided intake 与错误反馈 | v0.2 结构化记录 | 不明列/缺单位/缺 locator/错`value_role` fail closed；只读输入；首次用户无需理解内部 records。 |
| 2 | comparison qualification、V&V status 与 candidate QoI contract | 工作包1+作者批准的科学问题 | 差异科学角色、阈值依据、三态资格及两类状态都有来源或缺口；候选合同冻结 expected membership，未冒充作者锁定。 |
| 3 | QoI 确认锁定、单位与全序列趋势 | 第一检查点确认 candidate QoI contract；工作包2为`eligible/restricted` | 只消费已导出观察和声明聚合；全序列 oracle、容差和最小点数通过；不发明场算子或公式。 |
| 4 | 四档 claim ceiling 与 candidate FigureContract | 工作包3 | 资格/V&V 缺口确定性限制可用措辞；生成待第二检查点确认的图件与段落职责，不渲染正式图。 |
| 5 | 锁定 FigureContract、source data、SVG/PNG 和三重 QA | 第二检查点批准工作包4候选 | 可编辑图与 source data 一致；一轮 QA 无硬错。 |
| 6 | 受证据约束的单段写作 | 工作包4–5 | 未批第二检查点时不生成；数值反链与 ceiling 通过。 |
| 7 | 公开正/负/对抗回放、stale-input 回归、CLI 文档与打包 | 工作包1–6 | Windows/Linux、Python 3.10–3.12 通过；修改 CSV/expected set/科学合同会阻断旧图文；新用户可按 Quickstart 复现。 |

资源预算为 55% 科学、25% 图文、10% 适配/易用、10% 必要可靠性。实现规格应用工作包和验收工时核对，
不用代码行数伪装精确分配。

V0.3 的权威执行路径为本地 Python CLI 与确定性脚本。四个窄 Skill 包只调用相同合同；三宿主 adapter、
provider transport、PDF/TIFF、换热和瞬态/多相公开 fixture 均不属于本版本。核心结果段由受限 renderer
生成，宿主模型只能提供不改变 locked facts、趋势和 ceiling 的可选候选措辞。

## 4. v0.4.0 条件性能力地平线候选：场数据与论文工作区

| 项目 | 定义 |
|---|---|
| 前置 | v0.3.0 科学纵向链通过，且真实用户反馈确认一个主要瓶颈。VTK 场数据、文献证据和多图/章节工作区只是候选；下一规格只能锁定其中一个主要瓶颈。 |
| 候选瓶颈 | **一次只允许选择一项：** A. VTK 场数据与空间 QoI；B. 文献 evidence table；C. 多图/指定章节工作区。三项不是联合承诺。 |
| 用户输入 | A：受支持的 VTK 场数据；B：明确的文献问题与原始来源；C：多个锁定 QoI/图件及作者批准的 paper spine。 |
| CLI/界面 | 只扩展被真实用户反馈选中的一个瓶颈及其最小命令表面，不默认同时扩展`inspect/analyze/figure/write`。 |
| 输出 | A：VTK 派生 source data/场图；或 B：literature evidence table；或 C：多图 FigureContracts、指定章节候选稿与反链。 |
| 作者检查点 | 仍为三个：①选题；②证据/claims/图件/spine；③当前文稿与图件。 |
| 验收 | 只验收所选瓶颈：A 验证场变量 location/scope/单位；B 验证文献 locator；C 验证多图多段的数字和 claim 传播。未选择项不得成为隐藏门槛。 |
| 不宣称 | 不宣称任意 VTK/求解器都支持；不生成完整投稿包；不因文献检索结果提升 CFD claim。 |

## 5. v0.5.0 条件性能力地平线候选：真实文档与事件驱动返修

| 项目 | 定义 |
|---|---|
| 前置 | 前一条件性版本的锁定能力已验证，且真实用户反馈确认一个新的主要瓶颈。文档交付、投稿前检查和事件驱动返修只是候选，不构成联合验收承诺。 |
| 用户输入 | 作者批准的论文内容、图表、BibTeX/CSL 或模板；返修模式需真实决定信/审稿意见。 |
| CLI/界面 | 激活`review`、`export`和事件触发的`revise`；显示来源、结构/渲染问题和作者可接受/拒绝的局部建议。 |
| 输出 | DOCX/LaTeX/PDF 源与预览、图表/引用嵌入、结构回读、提交前发现；真实返修意见矩阵、候选回复和修改传播清单。 |
| 作者检查点 | ①期刊/论文目标与科学问题；②证据/claims/图件/spine；③最终文稿、文件及返修策略。 |
| 验收 | 含公式、图表、引用、分节和批注的公开 fixture 完成结构回读与页面预览；回复的修改声明可在实际文件中定位。 |
| 不宣称 | 不宣称 Word/LaTeX 全部对象无损；不在无真实意见时触发返修；不代作者提交、申诉或对外发布。 |

## 6. v0.6.0 条件性能力地平线候选：选配原生适配与异构真实项目验证

| 项目 | 定义 |
|---|---|
| 前置 | 前一条件性版本的锁定能力已验证，且真实用户反馈确认原生读取或异构验证中的一个主要瓶颈。下一规格只能锁定其中一项，不将两者共同视为发布承诺。 |
| 用户输入 | 授权的只读原生求解结果或官方 API；与中性出口的对照；三类真实异构项目。 |
| CLI/界面 | 可选 adapter 的`probe/inventory/extract(request)`；正常流程仍是六层和三检查点。 |
| 输出 | 保留 solver/variable/location/zone/unit/source 的提取记录；同 QoI 与中性入口一致性结果；异构项目质量报告。 |
| 作者检查点 | 仍为选题、证据/图件、最终论文三点；adapter 安装和对照不是新检查点。 |
| 验收 | 至少覆盖两种求解器或“求解器+中性格式”；真实单相内流、换热、瞬态/多相各一项；关键数值、单位、case 和图文引用零硬错。 |
| 不宣称 | 不宣称所有求解器/版本/物理模型通用；不以一个私有项目通过代替异构验证。 |

## 7. v1.0.0：稳定的作者在环 CFD 论文工作流

v1.0.0 是对 v0.6.0 已验证能力的稳定化发布；它继承已有输入、CLI、输出和检查点，不新增隐藏功能。

| 项目 | 定义 |
|---|---|
| 用户输入 | 继承 v0.6.0 已验证的中性数据、可选原生适配结果、论文内容与真实返修事件输入。 |
| CLI/界面 | 稳定并文档化 v0.6.0 已验证的命令、项目恢复和作者决策界面。 |
| 输出产物 | 继承已验证的证据记录、分析、图件、学术文本、文档与返修支持产物。 |
| 三个作者检查点 | 继承选题与科学问题、证据/claims/图件方案、最终论文与交付文件三个检查点。 |
| 验收 | 公共契约和打包稳定；Windows/Linux 与 Python 3.10–3.12 核心流程通过；三类真实异构项目回放完成；证据不足不会被提升为主张；关键数字、单位、case ID 和图文引用零硬错；公开文档与实际能力一致。 |
| 不宣称能力 | 不宣称无人科研、通用求解器、实验验证替代、无限求解器/物理模型支持或自动对外投稿。 |

## 8. 回归验证映射

| 回归资产 | 已记录的角色 | 可验证的主要模块 | 不能代替 |
|---|---|---|---|
| `authorized internal positive regression` | figure contract、数值/图文传播、作者语气、最终图文交付 | claim ceiling、FigureContract、三重 QA、数值反链段落、跨文档传播 | 通用求解器支持或异构科学正确性 |
| `authorized internal negative scientific-gate regression` | 不可比工况、错趋势、弱收敛、错聚合、缺失数据和虚假批准 | qualification、QoI 合同、全序列趋势、ceiling、真实作者检查点 | 正向可发表结果或异构普适性 |
| 缺失：稳态单相内流 | 待建立的公开正向端到端 fixture | V0.3 CSV 纵向链 | 换热、多相或原生 adapter |
| 缺失：换热 | 待建立的公开异构正向 fixture | VTK field、空间 QoI、多图/章节工作区 | 瞬态/多相或所有求解器 |
| 缺失：瞬态/多相 | 待建立的统计窗口、相分数/相交换和不稳定证据回放 | 瞬态资格、统计 QoI、missing policy、不确定性边界 | 稳态内流或换热验收 |

私有资产只在授权内部回归中使用。公开仓库和外部评审包只保留上表的抽象角色，不包含原始数据、项目路径或未发表文本。

## 9. STOP THAT SHIT 范围说明

- V0.3 完整实现范围是第3节的7个工作包；新机制只有会使该纵向链失败时才可增加。
- VTK、原生 Fluent/STAR、完整 paper spine/全稿、自动文献工作区、DOCX/LaTeX、pre-submission、revision、marketplace 和通用 Agent runtime 均已明确延期。
- 后续版本不是 V0.3 的隐性 backlog；只有前一版真实用户限制与下一版验收条件都存在时才启动。
- 对标目录的20项机制不会被顺手全部实现。V0.3只消费与一条科学纵向链直接相关的部分。

## 10. 当前停止点

路线图与产品设计尚待外部高能力模型依据公开研究包评审。外部意见只进行一轮并行评审和一轮去重归并。在作者对
归并后的方案书面批准前，不建立 V0.3 实现分支、生产代码或新依赖。
