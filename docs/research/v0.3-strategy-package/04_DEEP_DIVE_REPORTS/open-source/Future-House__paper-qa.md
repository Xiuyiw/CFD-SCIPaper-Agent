# PaperQA2

## 1. 来源

- 候选ID：`Future-House/paper-qa`
- 仓库：<https://github.com/Future-House/paper-qa>
- 原始论文：<https://arxiv.org/abs/2409.13740>
- 固定版本：`57e89f7223b0960d5ee5ea048c69e3c47e088572`
- 访问日期：2026-09-01；许可证：Apache-2.0（`LICENSE`）。
- 判断来自固定提交的实现、测试和README，不把RAG检索结果当作科学证明。

## 2. 轨道与真实任务

覆盖`writing`与`agent-rag`。它摄取论文、构建索引、检索片段、收集证据并生成带引用答案；任务是
文献问答，不是CFD结果分析或完整论文生产。

## 3. 实际代码或文档定位

- `src/paperqa/docs.py::Docs/aadd`：读取来源、计算内容哈希和文档key、解析引用元数据并建立文本。
- `src/paperqa/types.py::PQASession`：保存问题、上下文、答案、引用、工具历史、token及配置MD5；
  `populate_formatted_answers_and_bib_from_raw_answer`把引用ID映射到书目并移除残留无效引用。
- `src/paperqa/agents/env.py::settings_to_tools/PaperQAEnvironment`：构建搜索、证据收集、回答和完成工具。
- `src/paperqa/agents/main.py`：Agent rollout及搜索/证据/回答编排。
- `src/paperqa/agents/search.py::get_directory_index/maybe_get_manifest`：索引复用和manifest入口。
- 测试：`tests/test_agents.py::test_get_directory_index/test_resuming_crashed_index_build`，
  `tests/test_paperqa.py`中的证据复用和引用测试。

## 4. 架构

文档被拆成带来源元数据的文本，向量索引负责召回；Agent先检索，再收集上下文，最后生成答案。
`PQASession`把上下文和引用留在同一会话对象中，使回答可追查到检索片段。索引与会话分离，允许
多个问题复用同一文献库。

## 5. 输入与输出

输入为论文文件、目录/manifest和自然语言问题；输出为答案、证据上下文、引用列表、会话记录和
缓存索引。它没有生成期刊DOCX或LaTeX论文，输出仍是问答/结构化会话层。

## 6. 科学边界

内容哈希、明确context ID和引用映射可降低来源混淆。引用清洗可以删除模型留下的无匹配引用，
但无法判断引用是否真正支持claim，也不能验证CFD数值、公式、单位或物理因果。版本过滤只有在
调用者把版本写入manifest/metadata并用于查询时才成立；embedding相似度不是证据等级。

## 7. 状态与恢复

目录索引可持久化和复用；测试证明中断的索引构建可以继续，且输入删除或索引文件缺失会被识别。
`PQASession`含配置MD5并可序列化，提供会话级恢复材料。它没有CFD-Paper-Agent所需的阶段批准、
case版本、QoI陈旧传播和跨文件claim状态机。

## 8. Skill、插件或适配器

工具组通过`settings_to_tools`组装，适合借鉴“最小工具集合+显式会话状态”。它不是Agent Skills
包，没有SKILL.md触发、渐进披露、资源脚本和跨宿主回退协议。

## 9. 测试、示例与发布边界

README中的基本问答示例展示`Docs`添加论文、查询和返回带引用答案；测试覆盖索引创建、复用、删除、
崩溃恢复、证据上下文和引用。它们证明文献RAG工程行为，不证明
答案在科研语境中完整或引用支持强度正确。使用外部模型/metadata服务时存在费用和可用性依赖。

## 10. 许可证与条款

Apache-2.0允许带通知复用。完整包依赖较多、服务配置复杂；V0.3不需要为文献检索引入整个Agent层。

## 11. 优点

- 文档内容哈希、manifest和可恢复索引可减少重复处理与陈旧来源混用。
- 回答保留上下文ID和书目映射，并显式清理无匹配引用。
- 崩溃恢复和索引复用有测试覆盖，不只是README承诺。

## 12. 缺点与风险

- 证据粒度是文献片段，不是CFD case/QoI/source-data记录。
- 引用存在不代表claim被文献支持；元数据解析和召回仍可错。
- 不产生真实论文文件，也不维护章节间claim传播。

## 13. 迁移判定

**reimplement**。借鉴内容哈希、manifest优先元数据、可恢复增量索引、context ID到引用的确定性映射
和“无法映射则删除/失败”的做法；不直接采用整套Agent与索引抽象。CFD-Paper-Agent应先结构化
过滤项目/case/版本，再做全文和可选语义召回。

## 14. Internal regression relevance

其正向价值对应“引用和关键判断必须有可定位来源”；其不足对应“有检索上下文仍可能生成不受
物理证据支持的说法”。因此文献RAG不能绕过CFD evidence record和claim ceiling。

## 15. 未验证项

未调用外部模型、未构建真实大规模论文索引、未评估metadata服务质量。迁移判断只针对源码中可证的
哈希、索引恢复与引用映射机制。
