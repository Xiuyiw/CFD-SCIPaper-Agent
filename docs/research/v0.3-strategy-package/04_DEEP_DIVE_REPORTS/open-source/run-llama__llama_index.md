# LlamaIndex

## 1. 来源

- 候选ID：`run-llama/llama_index`
- 仓库：<https://github.com/run-llama/llama_index>
- 固定版本：`7b80927de149bfef0c7d1e178d311154ea0b4d03`
- 访问日期：2026-09-01；许可证：MIT（`LICENSE`）。

## 2. 轨道与真实任务

覆盖`agent-rag`。核心提供文档/node数据模型、摄取变换、缓存、索引、metadata过滤、查询和持久化；
它是通用RAG数据框架，不是科研证据库或论文生产系统。

## 3. 实际代码或文档定位

- `llama-index-core/llama_index/core/schema.py::BaseNode`：内容、metadata、关系、`ref_doc_id`与内容哈希。
- `core/ingestion/pipeline.py::IngestionPipeline/run_transformations`：按变换和输入计算cache key，
  支持同步/异步及持久cache。
- `core/storage/storage_context.py::StorageContext.from_defaults/persist`：组合doc/index/vector/graph
  store并保存到目录。
- `core/indices/vector_store/base.py::VectorStoreIndex`：向量索引、ref_doc删除和检索器入口。
- metadata过滤测试：`llama-index-core/tests/vector_stores/test_simple.py`和
  `test_metadata_filters_logic.py`；持久化测试：`tests/indices/test_loading.py`；摄取测试：
  `tests/ingestion/test_pipeline.py::test_run_pipeline_with_ref_doc_id`。
- 示例：`docs/examples/discover_llamaindex/document_management/group_conversations.py`展示文档分组与管理。

## 4. 架构

Document被拆成Node；Node以relationship保留来源文档；transform pipeline可缓存中间节点；
StorageContext统一索引、文档和向量存储。VectorStore实现和LLM/embedding/provider被拆为扩展包，
核心层维持抽象。

## 5. 输入与输出

输入是Document/Node、metadata、变换器、embedding和store；输出是持久索引、召回Node和查询答案。
项目本身不生成投稿级DOCX/LaTeX，也不对图件或source data建立专用输出契约。

## 6. 科学边界

`ref_doc_id`、内容hash和metadata filter为来源/版本过滤提供积木，但版本字段及过滤规则完全由调用者
定义。相似度检索不能证明claim；Node拆分还可能丢失跨段上下文。CFD数值、单位、case、QoI和证据
成熟度必须保存在结构化业务层，并在语义检索之前过滤。

## 7. 状态与恢复

StorageContext和cache可持久化，测试证明索引可保存/加载。它不提供论文阶段checkpoint、作者批准、
输入陈旧传播或跨电脑任务恢复协议；持久索引若没有外部manifest仍可能复用旧输入。

## 8. Skill、插件或适配器

大型集成生态通过包和provider抽象扩展，但不是Agent Skill触发/资源协议。插件化值得借鉴，完整生态
则超出本项目“SQLite结构化检索+FTS5+可选embedding”的轻量目标。

## 9. 测试、示例与发布边界

核心有大量摄取、索引、持久化、过滤和删除测试，宣传的RAG数据抽象有真实实现。不同vector store
对metadata操作符的支持并非天然一致，调用方仍需合同测试。测试不验证科研引用或物理claim。

## 10. 许可证与条款

MIT核心可复用；大量集成包、provider和外部数据库各有依赖及服务条款。引入核心也会扩大依赖面。

## 11. 优点

- Node来源关系、内容哈希和metadata过滤组合适合构造可定位检索。
- 摄取变换缓存与存储抽象成熟，且有持久化测试。
- provider分层避免把某一向量数据库写死在核心。

## 12. 缺点与风险

- 生态规模远超当前需求，易把轻量项目知识层变成RAG平台维护工程。
- 版本过滤是可选metadata约定，不是默认科学保证。
- 不理解claim证据强度、CFD可比性或投稿文件。

## 13. 迁移判定

**reimplement**。在现有SQLite/FTS层窄实现`source_id + content_hash + version + locator`、先结构化
过滤再全文/可选语义召回、变换cache key和stale标志；不引入LlamaIndex核心。未来只有在连接多种
文档源成为明确用户需求时，再评估适配其Node/reader接口。

## 14. Internal regression relevance

其来源关系和 metadata 过滤可帮助避免引用错误版本；但 `authorized internal negative scientific-gate regression`
表明，检索到“正确文件”仍不代表工况可比或趋势正确。RAG 只能找到材料，scientific gate
必须另行计算。

## 15. 未验证项

未运行全部integration package、向量数据库或embedding服务，未比较大规模索引性能。当前判断严格
限于core源码和测试中可证的摄取、持久化与过滤机制。
