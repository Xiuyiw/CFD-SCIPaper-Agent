# Jenni AI

## 1. 来源

- 候选ID：`product/jenni`
- 官方入口：<https://jenni.ai>
- 官方公开材料：<https://docs.jenni.ai/docs/>、
  <https://docs.jenni.ai/docs/export-and-import/importing/>、
  <https://docs.jenni.ai/docs/export-and-import/exporting/>、
  <https://docs.jenni.ai/docs/account/plans-and-billing/>。
- 访问日期：2026-09-01；专有托管服务，受Jenni AI公开服务条款约束。
- 标签规则：**official claim**、**observable workflow**、**controller inference**。

## 2. 轨道与真实任务

覆盖`writing`和`quality-export`。**Observable workflow**：作者创建或导入DOCX，在可编辑文档中
使用写作、引用、PDF阅读、评论和版本历史，再导出DOCX、LaTeX或富文本。它是文档创作环境，
不验证CFD数据或物理解释。

## 3. 实际代码或文档定位

- 文档首页：写作、AI工具、研究、协作、导入/导出和账户模块。
- 导入页：DOCX导入步骤、支持内容、丢失内容、引用匹配及人工Review面板。
- 导出页：DOCX/LaTeX/富文本、引用选项、BibTeX、Word批注和已知排错边界。
- 计划页：Free、Plus、Pro的消息、上传、Review、引用样式和导出限制。
- **Not independently verified**：真实多人协作、版本差异、复杂投稿模板和所有引用样式。

## 4. 架构

**Observable workflow**围绕持久化文档工作区组织写作、来源、评论和导出。导入后，系统把外部
DOCX转换为内部可编辑结构；导出时再选择Word原生引用或超链接引用。**Controller inference**：
这说明导入/导出必须公开声明损失，而不能假设DOCX往返无损；不推测内部文档模型。

## 5. 输入与输出

DOCX导入可保留常见语义结构、图、表、题注、公式和部分引用，但不保留页眉页脚、分页符、特定
字体字号或Track Changes；引用匹配进入Review面板供作者确认。DOCX导出可保留未解决批注并选择
Word原生引用；LaTeX导出附BibTeX。完整参考文献表和全部导出格式均受付费计划限制。

## 6. 科学边界

文档结构保真和引用匹配不等于科学正确。**Controller inference**：导入时任何无法保留的结构必须
形成明确差异，引用重连只能作为建议；CFD数值、单位、图表数据和claim ceiling仍由锁定证据对象
控制，写作工具不得改写。

## 7. 状态与恢复

官方文档目录公开声明版本历史、评论、分享和发布功能；导出DOCX可保留未解决评论。跨版本回滚、
多人协作文档/项目的冲突处理、分支合并和陈旧来源处理未在本轮逐步页面中独立验证，因此标为
**not independently verified**。

## 8. Skill、插件或适配器

没有公开可移植Skill系统。**Controller inference**：值得借鉴的是“导入能力矩阵 + 引用重连Review
队列 + 导出模式选择 + 导出前提示已知损失”。这应进入CFD-Paper-Agent的文档适配器和人工检查点，
而非引入其托管编辑器。

## 9. 测试、示例与发布边界

官方文档包含具体元素支持表和排错建议，但没有公开代码或独立回归文件。本轮未执行DOCX往返；
公开文档已足以确认显式损失披露和引用确认UX后停止。

## 10. 许可证与条款

专有服务，不直接复用实现。Free层对导出格式、引用样式和参考文献表有明确限制；文件大小和页数
也按计划分层。未来产品核心不应依赖该服务。

## 11. 优点

- 导入文档明确列出保留与丢失的结构，而非宣称无损。
- 引用重连进入作者确认面板。
- DOCX、LaTeX、BibTeX和批注交接边界较清楚。

## 12. 缺点与风险

- DOCX导入会规范化样式并丢失Track Changes、页眉页脚和分页符。
- 免费层导出参考文献不完整，容易形成看似完成的稿件。
- 科学证据、图表source data和CFD语义不在产品边界内。

## 13. 迁移判定

**idea-only**。重实现一个显式文档往返契约：导入前盘点对象，导入后报告丢失，引用重连由作者
确认，导出时选择DOCX/LaTeX策略并做结构回读。验证使用含公式、图表、批注、动态引用和修订的
夹具，任何不支持对象都必须保持缺失或报告损失。

## 14. P04 / Gate 5 对应关系

正向对应P04中Word字段、批注和作者手工引用必须保护的经验；Gate 5说明“文件已生成”不能视为
科学完成。文档适配器应诚实报告损失，而不是创建虚假完成状态。

## 15. 未验证项

未登录、未导入或导出真实DOCX/LaTeX，未运行评论、共享、发布或版本历史；未核实复杂域、修订、
交叉引用、浮动对象及全部引用样式的保真。官方计划与配额可能变化。
