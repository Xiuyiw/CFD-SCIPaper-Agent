# LangGraph

## 1. 来源

- 候选ID：`langchain-ai/langgraph`
- 仓库：<https://github.com/langchain-ai/langgraph>
- 固定版本：`11ee185999b86bfea2d8c0e69cef9a5e37acf686`
- 访问日期：2026-09-01；许可证：MIT（仓库各核心package的`LICENSE`）。

## 2. 轨道与真实任务

覆盖`agent-rag`与`skills`。它提供有状态图执行、checkpoint、流式调用和human-in-the-loop原语，
是真正的通用Agent编排框架；它不理解CFD、论文claim、文献或科研图表。

## 3. 实际代码或文档定位

- `libs/langgraph/langgraph/pregel/main.py::Pregel`及`get_state/get_state_history/update_state`：
  执行图并读取、枚举、修改checkpoint状态。
- `libs/checkpoint/langgraph/checkpoint/base/__init__.py::BaseCheckpointSaver`：定义
  `get_tuple/list/put/put_writes`等持久化契约，使用`thread_id`和`checkpoint_id`定位历史。
- `libs/checkpoint/langgraph/checkpoint/memory/__init__.py::InMemorySaver`：按thread、namespace、
  checkpoint和channel version保存状态与写入。
- `libs/langgraph/langgraph/types.py::Command/interrupt`：暂停执行并通过`Command(resume=...)`恢复。
- 持久化实现：`libs/checkpoint-sqlite/langgraph/checkpoint/sqlite`与
  `libs/checkpoint-postgres/langgraph/checkpoint/postgres`。
- 测试：`libs/langgraph/tests/test_interruption.py`、`libs/checkpoint/tests/test_memory.py`及
  `libs/checkpoint-conformance`契约测试。
- 示例：`libs/cli/uv-examples/simple/src/agent/graph.py`展示最小StateGraph编译和导出。

## 4. 架构

Pregel以channel状态和节点更新执行图；checkpointer把每个thread的checkpoint、父checkpoint、
channel versions和pending writes保存。存储通过抽象接口替换为内存、SQLite或Postgres。
`interrupt`把人工输入变成可恢复的运行时事件，而不是在提示词中假装“已批准”。

## 5. 输入与输出

输入为图、节点、状态schema、运行配置和可选checkpoint后端；输出为状态、流事件和checkpoint历史。
它不产生论文文件，也不定义EvidenceRecord、FigureContract或case/QoI对象。

## 6. 科学边界

持久状态只保证“某个值被保存”，不保证值的来源、量纲或科学正确性。线程和checkpoint ID不是输入
文件版本；若业务层不记录源哈希和stale规则，仍可恢复到科学上无效的状态。人工interrupt能实现
真实审批，但批准内容必须由业务对象绑定，不能只保存自由文本。

## 7. 状态与恢复

这是九项中状态/恢复最完整的实现：checkpoint有父链、channel版本、pending writes、历史查询、
状态更新和多种持久后端；测试覆盖中断及checkpointer一致性。恢复语义依赖调用方稳定使用thread_id，
且应用schema演化仍需产品自己管理。

## 8. Skill、插件或适配器

LangGraph提供节点/工具编排，不提供Agent Skills的元数据发现、触发、渐进披露和资源包。它可承载
Skill调用，但不能替代CFD-Paper-Agent自己的Skill契约和scientific gate。

## 9. 测试、示例与发布边界

checkpoint有独立conformance套件，interrupt和状态历史也有测试，宣传的持久化/HITL能力与代码一致。
这些测试不覆盖科研数据版本、claim传播或真实DOCX导出。引入框架还会带来LangChain runtime接口和
升级迁移成本。

## 10. 许可证与条款

MIT核心可复用；SQLite/Postgres等package有各自安装依赖。若只借鉴状态语义，不需引入整个生态。

## 11. 优点

- checkpoint不是日志假象，而是可查询、可分支、可恢复的版本化执行状态。
- `interrupt`/`Command(resume=...)`为真实人工检查点提供清晰语义。
- 后端契约和conformance测试降低持久化实现漂移。

## 12. 缺点与风险

- 通用图运行时对当前本地CLI可能过重，容易把产品资源重新拉向编排而非CFD科学。
- checkpoint版本不等于源文件版本，无法自动阻断陈旧证据。
- 不包含论文、引用、图件或科学质量对象。

## 13. 迁移判定

**idea-only**（当前版本）。借鉴三项语义：稳定项目/任务ID、阶段checkpoint父链、真实interrupt+resume；
在现有SQLite项目状态中窄实现，而非引入LangGraph。只有当V0.3后出现复杂分支/并发Agent需求并有
性能证据时，才重新评估直接依赖。

## 14. P04 / Gate 5 对应关系

真实interrupt可避免“系统自称作者已批准”的失败；但如果恢复状态中的QoI本身错误，强持久化只会
更可靠地传播错误。因此scientific validity必须先于workflow durability。

## 15. 未验证项

未运行Postgres/SQLite集成套件，未测schema升级和跨版本checkpoint迁移，未评估大图性能。源码与
conformance测试已足以证明其恢复机制真实存在并判定当前不宜整包引入。
