# STORM

## 1. 来源

- 候选ID：`stanford-oval/storm`
- 仓库：<https://github.com/stanford-oval/storm>
- 原始论文：<https://aclanthology.org/2024.naacl-long.347/>
- 固定版本：`fb951af7744dab086e34962e9bc6fe878e145f83`
- 访问日期：2026-09-01；许可证：MIT（`LICENSE`）。

## 2. 轨道与真实任务

覆盖`writing`和`agent-rag`。STORM围绕主题生成多视角问题、检索资料、生成提纲和带引用的百科式
长文。其真实目标是研究型报告/百科文章，不是基于已有CFD结果的工程论文。

## 3. 实际代码或文档定位

- `knowledge_storm/storm_wiki/engine.py::STORMWikiRunner`：分开运行知识整理、提纲、文章生成和润色。
- 同文件的`run_knowledge_curation_module/run_outline_generation_module/
  run_article_generation_module/run_article_polishing_module`分别写出conversation、搜索结果、提纲、
  article和URL映射文件。
- `knowledge_storm/storm_wiki/modules/storm_dataclass.py::StormInformationTable/StormArticle`：
  保存对话来源、URL信息、文章树和引用。
- `knowledge_storm/storm_wiki/modules/knowledge_curation.py`：生成视角、问题和检索query，并要求无合适来源时说明不能回答。
- `knowledge_storm/storm_wiki/modules/article_generation.py::StormArticleGenerationModule.generate_article/WriteSection`：
  并行写section并使用编号行内引用。
- 示例：`examples/storm_examples/run_storm_wiki_gpt.py`。

## 4. 架构

流程将“谁会提什么问题”与“搜到什么资料”分离，再由资料表支持提纲和section级写作。文章树与
URL信息映射共同维护引用。基本runner按固定阶段执行，并允许只运行某些阶段。

## 5. 输入与输出

输入为主题、检索后端和语言模型；输出包括`conversation_log.json`、`raw_search_results.json`、
提纲文本、文章文本和`url_to_info.json`。默认产物是文本/JSON，不是DOCX、LaTeX或带嵌入图表的
投稿文件。

## 6. 科学边界

多视角能扩大问题覆盖，但不会验证CFD边界条件、QoI、收敛或case可比性。编号引用可回到URL片段，
却不检查来源质量、版本是否适用或claim支持强度。对网页主题有用的“检索后写作”不能替代已有
仿真证据优先的论文主线。

## 7. 状态与恢复

每阶段写出文件，后续run可跳过已完成阶段并从目录加载前序产物，构成真实但粗粒度的文件恢复。
没有输入哈希、schema版本、stale检测或原子checkpoint；修改主题、模型或来源后仍可能复用旧产物。

## 8. Skill、插件或适配器

模块是Python pipeline，不是可发现Skill包。没有SKILL元数据、触发、渐进披露、依赖声明和回退
测试。可迁移的是“perspective → question → evidence gap”的选题探索模式，而非其宿主架构。

## 9. 测试、示例与发布边界

示例真实展示全阶段输出及可选阶段开关；当前深读范围未发现能证明全部stage恢复与引用完整性的
同等级自动测试。README/论文宣传的长文质量不能替代特定工程题材的盲审。

## 10. 许可证与条款

MIT允许复用。检索和模型后端各自可能有费用、服务条款与数据出站风险，不能由仓库许可证覆盖。

## 11. 优点

- 多视角访谈将选题探索从单一提示扩展为可检查的问题集。
- 来源表、提纲和article分层，避免写作阶段完全丢失检索材料。
- 阶段文件允许局部重跑，易于人工检查中间产物。

## 12. 缺点与风险

- 百科写作目标与CFD论文证据链不同；容易形成“信息丰富但不回答科学问题”的长文。
- 文件恢复缺少版本与陈旧输入阻断。
- 默认不生成投稿级DOCX/LaTeX，也不验证图表、数据和物理claim。

## 13. 迁移判定

**idea-only**。仅迁移“多视角问题发现”和“资料表先于提纲”的思想，重写成受成熟CFD证据约束的
2–4个选题候选生成；不引入STORM runtime、section并行写作或文件恢复协议。

## 14. Internal regression relevance

多视角能帮助发现审稿人可能追问的工程、方法和物理问题；但如果case不可比或QoI错误，更多视角
只会放大错误叙事。因此它只能位于证据门之后，不能晋升不成熟结果。

## 15. 未验证项

未运行联网搜索和模型调用，未对生成文章进行质量盲审，未验证全部扩展模式。当前证据足以限定为
选题问题发现的思想来源。
