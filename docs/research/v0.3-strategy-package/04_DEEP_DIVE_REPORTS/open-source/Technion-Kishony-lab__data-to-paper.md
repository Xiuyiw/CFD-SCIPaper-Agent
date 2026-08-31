# data-to-paper

## 1. 来源

- 候选ID：`Technion-Kishony-lab/data-to-paper`
- 仓库：<https://github.com/Technion-Kishony-lab/data-to-paper>
- 原始论文：<https://arxiv.org/abs/2404.17605>
- 固定版本：`81df14c4b9600466e645c3b2b336cc54daa3df3a`
- 访问日期：2026-09-01；许可证：MIT（`LICENSE`）。
- **事实**来自固定提交的代码、测试和示例；超出源码直接陈述的内容标为迁移判断。

## 2. 轨道与真实任务

覆盖`scientific-analysis`、`writing`、`agent-rag`和`quality-export`。项目从表格数据开始，依次形成
研究目标、分析计划、可执行代码、结果解释、章节、参考文献和LaTeX/PDF。它面向“让Agent提出并
执行研究”，而CFD-Paper-Agent面向“已有成熟CFD结果，作者确认科学问题后形成可辩护论文”，
两者的输入成熟度和授权边界不同。

## 3. 实际代码或文档定位

- `src/data_to_paper/research_types/hypothesis_testing/steps_runner.py::HypothesisTestingStepsRunner`：
  编排数据、探索、目标、文献、计划、代码、图表、解释、写作和编译阶段。
- `src/data_to_paper/research_types/hypothesis_testing/scientific_stage.py::ScientificStage`：
  显式列出科学阶段及哪些阶段请求人工审阅。
- `src/data_to_paper/research_types/hypothesis_testing/produce_pdf_step.py::ProduceScientificPaperPDFWithAppendix`：
  把论文、引用及代码/输出附录组合。
- `conversation/actions_and_conversations.py::Actions.save_actions_to_file/load_actions_from_file`：
  保存和回放动作；实现实际使用pickle，而注释仍称JSON。
- `code_and_output_files/ref_numeric_values.py::ReferencedValue/find_numeric_values`：把文本数值与
  输出标签连接，生成可回溯的数字引用。
- `latex/latex_doc.py::LatexDocument.compile_document`与`latex/latex_to_pdf.py`：写入`.tex`、
  `citations.bib`并执行LaTeX编译。
- 测试：`tests/integration/full_run/test_full_run.py`；示例/集成产物检查`paper.tex`。

## 4. 架构

核心是固定科学阶段加专用Agent步骤。每一阶段产出后续阶段可消费的对象，写作阶段引用代码结果、
图表和文献；最终附录保留数据描述、代码和输出。它不是通用工作流引擎，而是对假设检验型数据研究
的强约束产品流程。

## 5. 输入与输出

输入主要是可由Python分析的表格数据、可选研究目标和交互反馈；输出包括分析代码、数值结果、
LaTeX表图、章节、BibTeX和真实PDF。它不是只输出Markdown，但不生成DOCX，也不直接读取CFD
求解器文件、网格、场变量或监控历史。

## 6. 科学边界

数字反链和代码附录提高可核查性，却不自动保证单位、量纲、控制体、工况可比性或CFD收敛。
系统可以自行提出目标与解释，这对证据尚不成熟的CFD项目会提高“先写结论再找证据”的风险。
其阶段性人工审阅是必要保护，但不能替代CFD专用QoI和claim ceiling。

## 7. 状态与恢复

动作序列可保存后回放，因此存在真实的粗粒度恢复机制；但动作文件使用pickle、缺少输入文件哈希、
schema迁移和陈旧依赖阻断。它更接近交互重放，不是版本化项目状态数据库。GUI不存在时，
`HumanReviewAppInteractor.actual_human_review`返回无审阅，人工门不应被视为始终有效。

## 8. Skill、插件或适配器

项目按研究阶段组合专用步骤，没有可移植的Skill元数据、触发、渐进披露和跨宿主依赖协议。
值得迁移的是“阶段产物契约”和“写作必须消费明确分析产物”，不应照搬其Agent角色或全流程。

## 9. 测试、示例与发布边界

集成测试覆盖玩具数据到`paper.tex`的完整路径，证明流程可产出真正论文源文件。测试不证明其自动
生成假设或解释在新工程领域正确，也不覆盖大型CFD文件、跨求解器元数据和工程单位传播。

## 10. 许可证与条款

MIT允许复用。若只迁移思想而不复制代码，许可证成本很低；若复用LaTeX编译链，仍需管理本地
TeX依赖、模板和外部模型配置。

## 11. 优点

- 研究阶段、分析代码、图表和写作之间有清晰产物链。
- 数字超链接与代码/输出附录提供了实用的后向追溯机制。
- 真实生成LaTeX/BibTeX/PDF，而非把Markdown草稿包装成论文。

## 12. 缺点与风险

- 自动发明研究问题的产品前提不适合成熟CFD结果驱动流程。
- pickle动作日志缺少强版本和陈旧输入控制；GUI缺失时人工审阅会消失。
- 没有CFD工况、单位、守恒、收敛、采样或图件source-data契约。

## 13. 迁移判定

**reimplement**。重实现三项窄机制：阶段产物图、数值到证据标签的反链、包含分析脚本和输出的
可选方法附录。拒绝直接集成其端到端研究Agent和pickle恢复。这样能保留写作闭环价值，又不把
CFD-Paper-Agent变成自动假设制造器。

## 14. Internal regression relevance

正向对应“数字必须能回到锁定source data、脚本和图表”的经验；反向提醒是，流程产出完整论文
并不等于科学前提成立。对证据不足或不可比工况，科学门必须在写作阶段之前停止传播。

## 15. 未验证项

未运行需要模型API和完整TeX环境的端到端测试，未验证其所有研究类型，也未评估生成内容质量。
这些不影响“仅迁移追溯和产物链、不直接复用自动研究流程”的判断。
