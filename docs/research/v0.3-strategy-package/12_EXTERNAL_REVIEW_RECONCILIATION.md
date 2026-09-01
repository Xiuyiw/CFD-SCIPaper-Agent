# V0.3 外部评审归并与定向修订

日期：2026-09-01

状态：作者已书面批准；进入 V0.3 实施规格与代码阶段

范围：Task 11，一次跨模型去重归并和一次定向修订

## 1. 实际评审输入

| 评审 | 文件 | SHA-256 | 自报模型/联网 | 处理方式 |
|---|---|---|---|---|
| A | `CFD-Paper-Agent V0.3 Strategy Package External Review Report.pdf` | `D8013C526606A7226095AABE17779100815DF790E34DD0833914E9F22C7F1E1C` | GPT-5.6 Sol / OpenAI；联网定向核验 | 作为独立正式评审。 |
| B | `CFD-Paper-Agent_V03_External_Review_Report.md` | `6A0AC1535345AA9BE42C4EAFA210C452BB557352593B04E3038DB2424176860C` | Grok 4.6 / xAI；联网定向核验 | 作为独立正式评审。 |
| C | `CFD-Paper-Agent_V03_Strategy_Review_Report.md` | `478C048A3AE3573CD9593BCDE12FADE06CD96A5F5DBD8ABB9F699F9933DB8C4B` | 文件自报 Claude / Anthropic；无联网 | 作者同时说明 Claude 未能使用，因此 provider 元数据无法核实。保留其内容作为匿名第三评审，不把它计作 Claude 背书，也不以模型票数提高采纳权重。 |

三份报告均实际覆盖 00、05–11、产品基线、benchmark 方法和来源清单的主要设计文件，结论均为
`APPROVE WITH TARGETED REVISIONS`。本归并不生成虚拟评审，不补问第四个模型，也不把偏好性建议变成
新增治理层。

## 2. 去重后的意见矩阵

| ID | 合并的原始 finding | 一致性 | 判定 | 理由与落实位置 |
|---|---|---|---|---|
| R01 | A/SCI-01 | 单模型、科学硬门 | `accepted` | comparison contract 的“允许差异”和阈值确有被作者声明绕开的风险。07/08/10 改为四类差异角色；阈值必须有 basis/locator。 |
| R02 | A/SCI-02；B/SCI-03；C/SCI-01 | 三份共同 | `accepted` | expected membership、最小点数、容差、重复/非均匀坐标共同决定趋势能否成立。07–10 已冻结 expected-vs-observed、至少三点、显式 tolerance 和 fail-closed 语义。 |
| R03 | B/SCI-01 | 单模型、切中 V0.3 计算边界 | `accepted` | V0.3 只消费已导出观察及声明聚合；新增`value_role`，禁止从点列猜场算子或由模型发明公式。写入07–09。 |
| R04 | C/IMPL-01 | 单模型，与 B 的 Pint 延期建议存在张力 | `accepted-with-modification` | 保留硬单位门，但不把完整 Pint 拉入 V0.3。08/09 冻结最小显式单位/量纲表，未知或不兼容单位 fail closed；真实回放证明需求后再引入 Pint。 |
| R05 | B/SCI-02；C/RULE-01 | 两份共同 | `accepted` | 自由文本 ceiling 无法执行。07/08/10 统一四档封闭映射，资格、V&V 和 intended use 决定最高档位。 |
| R06 | A/BENCH-01 | 单模型、需要定向新证据 | `accepted-with-modification` | 不重跑 benchmark；新增 NASA Glenn 基于 AIAA G-077 的官方 CFD V&V 来源，冻结 verification/validation 区分以及`partial/not-applicable`边界。修改06、08、10及 source manifest。 |
| R07 | A/ARCH-01；B/ARCH-01 | 两份共同但推荐时序略有差异 | `accepted-with-modification` | 采用单一三检查点顺序：analyze 后形成 candidate FigureContract；第二检查点批准；再锁定、绘图和写作。既保留 FigureContract 先于绘图，也不新增第四检查点。 |
| R08 | A/ARCH-02 | 单模型、可达的版本混用风险 | `accepted` | 将 CSV、expected set、QoI/comparison contract 或单位定义变化后的下游 stale/block 写入08–10验收，不新增溯源平台。 |
| R09 | A/SKILL-01；B/SKILL-01；C/SKILL-01 | 三份共同 | `accepted-with-modification` | V0.3 权威路径冻结为 Python CLI+确定性脚本；Skill 是薄包装。只验 SVG/PNG、单一公开稳态内流 fixture；三宿主、PDF/TIFF 和 provider transport 延期。核心段落用受限 renderer，模型措辞仅为可选 candidate。 |
| R10 | A/UX-01；B/UX-02；C/UX-01 | 三份共同关注普通用户入口 | `accepted-with-modification` | guided intake 用科学语言补齐现有 records；缺阈值/V&V 时不给隐藏默认值，而是 restricted/insufficient 与最小可补材料。写入08–10。 |
| R11 | B/UX-01；C/ARCH-01 | 两份共同 | `accepted` | 不改变 v0.2 `inspect` 心智模型；设计新增`qualify --observations`承担科学资格和 candidate QoI contract，最终参数仍在实现规格冻结。 |
| R12 | A/TRANSFER-01；B/FACT-01 | 两份共同 | `accepted` | 06 中 AU02 改为 OMF=`reimplement`、OpenSkill=`idea-only`，与 deep dive 和07一致。 |
| R13 | B/ROAD-01 | 单模型、范围一致性 | `accepted-with-modification` | v0.3 统一 SVG+PNG；v0.4 的 VTK、文献和多图/章节工作区改为三选一条件瓶颈，不再形成联合承诺。 |
| R14 | B/C 关于完整 Pint、跨宿主、PDF/TIFF、换热及瞬态/多相 fixture | 多模型涉及但均非当前必要 | `deferred` | 明确移出 v0.3；只有真实需求或对应版本引入 adapter/输出/fixture 时再规格化。延期不是隐藏验收。 |
| R15 | 各报告明确反对新增 Agent runtime、registry、审批层、重做 33 候选/23 deep dives | 三份方向一致 | `rejected` | 这些做法不能修复当前科学接口，反而违反 55/25/10/10 与 STOP 范围控制；不纳入修订。 |

归并结果：`accepted` 7 项，`accepted-with-modification` 6 项，`deferred` 1 项，`rejected` 1 项。

## 3. 定向修订摘要

### 3.1 科学合同

- case 差异改为研究因素、已证明等价/无实质影响、未解决干扰和阻断项，不再使用可被任意解释的
  “作者允许差异”。
- convergence/conservation 阈值必须带项目 basis 与 locator；系统不提供隐藏默认科学阈值。
- expected case/coordinate set 在第一检查点锁定，分析按 expected-vs-observed 判断序列完整性。
- V0.3 只消费`raw-sample`、`declared-aggregate`或`precomputed-qoi`三类已导出观察；不猜场算子。
- 趋势至少需要三个不同坐标和显式 tolerance；不足时降为 overall change/insufficient。
- 单位门由最小显式单位/量纲表支撑，未知单位 fail closed；不提前引入完整单位框架。
- 引入 NASA/AIAA CFD V&V 语义，防止`not-applicable`代替缺证据。

### 3.2 Claim、图件与写作

- ceiling 统一为四档：无数值 claim、方向性比较、合格数值观察、受支持物理解读。
- analyze 后生成 candidate FigureContract；第二检查点确认后才锁定并渲染。
- 正式 V0.3 图件只交付 SVG+PNG；PDF/TIFF 延期。
- 核心结果段由受限 renderer 从批准 claim、locked facts 和 numeric backlinks 生成；外部/宿主模型只能
  改候选措辞，不能成为隐藏运行依赖或改变主张强度。

### 3.3 普通用户与产品边界

- `inspect`保留 v0.2 语义；`qualify`承担 CSV 科学资格，避免破坏性重载。
- guided intake 把缺失记录翻译成 case、边界、模型、收敛、守恒和来源等科学问题，不要求用户理解
  内部 schema；仍无法判断时保持 gap。
- scientific input 改变后的 analysis、FigureContract、图件和段落必须 stale；输入未变时才恢复。
- V0.4 的场数据、文献和多图/章节工作区保持条件性三选一，不成为 v0.3 或彼此的隐藏门槛。

## 4. 新增外部证据

仅为关闭 R06 定向新增一项官方技术来源，没有重开 benchmark：

- NASA Glenn, *Tutorial on CFD Verification and Validation*, based on AIAA G-077-1998:
  <https://www.grc.nasa.gov/www/wind/valid/tutorial/tutorial.html>。
- 其 Verification Assessment 将 iterative convergence、solution consistency/conservation、spatial and
  temporal convergence 纳入 verification assessment；Glossary 将 validation 限定为 intended use 下模型
  对现实的代表程度。

该来源只用于冻结术语与状态边界，不把 NASA/AIAA 指南转换成跨所有 CFD 问题的统一数值阈值。

## 5. 作者已批准的最终口径

本轮已选择最小、可执行且不扩张 v0.3 的方案。作者已书面批准以下最终产品口径：

1. V0.3 只消费已有结构化记录和已导出观察，不从 CSV 猜测新的场算子；
2. 最小显式单位表而非完整 Pint 是本版本的单位门；
3. 核心结果段使用受限 renderer，模型润色是可选 candidate；
4. `inspect`保持 v0.2 语义，新增`qualify`；
5. candidate FigureContract 在第二检查点批准，随后才渲染图件和段落。

作者已批准上述五项最终产品口径。V0.3 实施必须以本归并结果、批准后的产品设计和统一总则为边界，进入“证据到图文”的最小纵向链开发，不得恢复已拒绝或明确延期的机制。
