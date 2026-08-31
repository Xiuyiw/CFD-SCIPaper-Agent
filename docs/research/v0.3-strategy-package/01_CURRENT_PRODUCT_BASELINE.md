# CFD-Paper-Agent v0.2.0 产品基线

日期：2026-08-31
基线版本：v0.2.0
用途：为 v0.3 前置对标研究提供共同产品事实源

## 1. 基线判定原则

本文件描述的是 v0.2.0 已公开交付的产品能力，而不是代码树中可以找到的模块总和。能力状态以
公开 README、路线图、架构说明、限制说明和变更记录的交叉表述为准。只有在已发布版本中可运行、
有公开边界说明且有相应验证的能力，才列为“已发布”。存在接口或实现片段但尚未形成公开端到端
工作流的能力，仍按“实验性”或“路线图”处理。

本基线使用四种状态：

- **已发布**：v0.2.0 的公开 CLI 或明确交付行为；
- **实验性**：接口已经出现，但适用范围和项目级行为仍在验证；
- **路线图**：公开说明中的长期目标，当前命令不产生完成产物；
- **明确未实现**：公开文档直接排除，或缺少构成可用产品所需的转换、传输或端到端链路。

## 2. 当前产品定位

CFD-Paper-Agent v0.2.0 是一个作者在环、证据有界的研究方向规划工具。它面向已经具有成熟 CFD
结果和结构化科学记录的项目，帮助作者维护本地状态、检查资料新鲜度，并生成或排序可辩护的候选
研究方向。它不是 CFD 求解器，也不是从任意结果文件自动生产论文的系统。

产品的核心边界是：文件被发现不等于证据已经合格；候选方向被生成或审批不等于分析、论文生产、
投稿或外部沟通已经获准。可比性、单位、收敛、守恒、QoI 定义、来源和主张上限仍由科学证据与作者
判断决定。证据不足是一个正常且必须可见的结果。

## 3. v0.2.0 能力状态

依据链接固定到公开仓库提交 `10e9fc6ad3646a0d4f5bf8a46214a09963418baa`，避免后续文档更新改变
本基线的含义。

| 能力 | 状态 | v0.2.0 的真实边界 | 依据 |
|---|---|---|---|
| `cfdpaper init`、`inspect`、`status` | 已发布 | 初始化本地项目状态，索引文件，记录内容身份与新鲜/过期状态，并支持恢复工作。检查不推断求解器语义，也不把普通文件提升为成熟证据。 | [README capability matrix][readme-capabilities]；[Architecture local components][architecture-components] |
| 作者提供候选的 `cfdpaper plan` | 已发布 | 校验并排序 schema-v1 候选 JSON；作者显式输入优先于自动生成。 | [README capability matrix][readme-capabilities]；[Architecture overview][architecture-overview] |
| 证据有界的候选生成 | 已发布 | 仅在成熟的 case、boundary、convergence、conservation、QoI-definition、QoI 与来源记录已经存在时，生成 2–4 个暂定候选，并保留证据、禁止推断、主张上限和最小缺失数据。 | [README capability matrix][readme-capabilities]；[Architecture overview][architecture-overview] |
| 离线生成、复用与再生成 | 已发布 | 离线模式确定性运行；科学输入变化使复用失效；非科学生成变化需要显式再生成；产物原子写入项目本地状态。 | [Architecture overview][architecture-overview] |
| 候选审批 | 已发布但受限 | 需要真实作者身份与显式动作。审批只记录所选方向及其证据边界，不执行分析或论文生产，也不能越过失败的科学门槛。 | [README capability matrix][readme-capabilities]；[Limitations][limitations] |
| 规划产物与检查点 | 已发布但内部使用 | 机会、候选、来源和生成报告是可恢复的项目产物，不是稳定的公共交换格式。 | [README capability matrix][readme-capabilities]；[Limitations][limitations] |
| strict/fast 复检策略与扩展契约 | 实验性 | 接口已存在，但跨项目行为仍需验证。 | [README capability matrix][readme-capabilities] |
| 可选 provider 与 adapter 扩展点 | 实验性 | 当前没有 provider 传输集成，也没有可宣称为通用能力的求解器原生支持。 | [README capability matrix][readme-capabilities]；[Limitations][limitations] |
| `analyze`、`figure`、`write`、`review`、`revise`、`export` | 路线图 | 当前是非零退出的占位命令，不生成相应工作流产物。 | [README capability matrix][readme-capabilities]；[Roadmap versioned delivery][roadmap-delivery] |
| Fluent、STAR-CCM+ 及其他原生求解器适配 | 路线图 | v0.2.0 公开示例使用小型合成数据或中性导出文件。 | [README capability matrix][readme-capabilities]；[Limitations][limitations] |
| v0.3.0 实现 | 路线图暂停 | 基线公开路线图没有活动规格、分支或实现；前置研究本身不构成生产开发启动。 | [Roadmap versioned delivery][roadmap-delivery] |

[readme-capabilities]: https://github.com/Xiuyiw/CFD-SCIPaper-Agent/blob/10e9fc6ad3646a0d4f5bf8a46214a09963418baa/README.md#capability-matrix
[roadmap-delivery]: https://github.com/Xiuyiw/CFD-SCIPaper-Agent/blob/10e9fc6ad3646a0d4f5bf8a46214a09963418baa/docs/ROADMAP.md#versioned-delivery
[architecture-overview]: https://github.com/Xiuyiw/CFD-SCIPaper-Agent/blob/10e9fc6ad3646a0d4f5bf8a46214a09963418baa/docs/architecture/overview.md#architecture-overview
[architecture-components]: https://github.com/Xiuyiw/CFD-SCIPaper-Agent/blob/10e9fc6ad3646a0d4f5bf8a46214a09963418baa/docs/architecture/overview.md#local-components
[limitations]: https://github.com/Xiuyiw/CFD-SCIPaper-Agent/blob/10e9fc6ad3646a0d4f5bf8a46214a09963418baa/docs/limitations.md#limitations

## 4. 明确未实现的链路

v0.2.0 不提供以下产品承诺：

- 从任意 CFD、CSV 或原生求解器文件自动构建完整成熟科学记录；
- 自动验证模型、边界条件、网格、收敛、守恒、QoI 或实验一致性；
- 通用 Fluent、STAR-CCM+ 或其他求解器的原生读取与语义解释；
- 在线模型 provider 的实际传输集成；
- 从原始结果到选题、分析、绘图、写作、自审、返修和导出的端到端自动化；
- 把离散 CFD 筛选解释为连续最优区、稳定边界、安全区或实验运行窗口；
- 无作者参与的研究方向批准、论文提交、申诉或外部发布。

因此，后续对标研究不能因为源码中存在类、接口、测试夹具或历史模块，就把这些链路写成当前产品
能力。所有建议都应从上述公开边界出发说明新增价值。

## 5. 可继承的正向经验

以下内容标记为 **private historical regression synthesis**：经验来自历史项目的抽象概括，只作为
产品设计与回归问题的内部依据，不代表 v0.2.0 已经实现相应功能，也不公开底层项目内容。

### 5.1 复杂证据链与返修

成熟论文项目需要把“本地文件存在”“作者报告已提交”“期刊官方事件”和“最终权威版本”分开。
同一事件的重复文件不能被当作独立证据，文件名、文件夹名和修改时间也不能代替官方收据或内容
身份。缺少正式闭环证据时，应保留开放状态，而不是用流程目录或后生成文件补足历史。

返修的有效模式不是在原稿上追加说明，而是建立主张与证据的传播关系：一个数值、定义或适用边界
被纠正后，必须同步检查摘要、方法、结果、图件、图注、结论、亮点和回复信。已接受的历史文本也
不是句子级金标准；更可靠的目标是事实准确、主张强度合适、作者语气一致且修改距离可控。

### 5.2 图件、分析与正文的连接

高价值图件先有明确的 figure contract，再连接数据来源、单位、工况、参考状态和主张上限。正文
不能只复述趋势，也不能让图注承担整段讨论。复杂结果通常需要形成以下证据链：

1. 图件要回答的科学问题；
2. 数据与处理方法的权威来源；
3. 可直接观察的场或趋势；
4. 足以支撑主张的定量锚点；
5. 与守恒、流动、传热或反应过程一致的物理解释；
6. 文献承担的背景、方法或外部比较角色；
7. 工程含义与不能外推的范围。

重要的正向经验是把显示量、严格物理量、派生指标和辅助诊断分开；把离散工况写成规定边界下的
比较；把局部指标与整体性能判断分开；并允许“局部响应更强”与“有效系统支撑更强”出现分离。

### 5.3 作者语气与权威边界

跨项目可迁移的作者语气是准确、克制、面向科学问题，而不是反复使用流程术语。好的作者在环输出
会明确“已知什么、缺什么、为什么重要、本文做了什么、如何验证”，同时避免把局部预测写成排放
合规、把相关性写成因果、把接受结果写成所有技术表述均已证明。

历史项目还表明，生命周期结果与提交文件身份是两个不同问题：接受函可以证明论文已接受，却未必
证明某个本地 DOCX 就是准确上传版本。产品应把这种不确定性转化为简洁的作者问题或受限表述，而
不是生成虚假的确定性。

## 6. 必须吸收的负向经验

历史异构项目暴露了仅靠顺畅编排和完整文档无法发现的问题。后续设计至少需要保留以下科学原则：

- **先证实可比性，再解释差异。** 某个量不受压力基准影响，不代表两个算例已经具备边界、材料、
  几何和物理设置上的可比性。
- **趋势词必须计算验证。** 总体恢复与逐点单调是不同事实；`monotonic`、`throughout` 等表述必须由
  算法检查，而不是由首尾值或图形印象决定。
- **派生数据必须记录算子。** 分组、分箱、平均、加权、采样数量和范围都决定 QoI 的含义；分箱均值
  不能被写成原始局部样本。
- **弱收敛不能包装为完成。** 单一监测量趋稳不足以证明全面收敛；残差、守恒闭合、关键监测量和
  稳态窗口应按项目证据分别判断。
- **缺失数据应改变交付类型。** 缺少关键网格、材料、边界、模型参数、守恒或验证证据时，应交付
  证据缺口报告或受限分析备忘录，而不是完整论文主张。
- **独立复核要回到注册来源。** 标题数值、单位、趋势和图文一致性需要从来源重新计算；“已有评审
  报告”不能代替复核。
- **批准只能来自真实权限主体。** 执行器不能创建作者或主控批准，也不能用阶段完成字段制造发布
  资格。
- **导出质量是科学交付的一部分。** 可编辑图件、预览文件、嵌入图、表格结构、页面渲染和图注文
  一致性都需要实际检查。

## 7. 对 v0.3 对标研究的约束

研究应优先寻找能改善科学理解、分析、图件与写作质量的外部机制，同时保持适配成本、可用性、
可靠性和作者权限的合理比例。历史经验用于提出问题和回归场景，不把特定燃烧案例字段固化进通用
核心，也不恢复以 L0–L4、promotion registry 或 synthetic master acceptance 为中心的前台治理。

后续报告必须持续区分：当前产品事实、历史经验、外部来源事实、研究者推断和未来建议。只有经过
独立实现与验证的建议，才能在未来版本中从研究结论转为产品能力。
