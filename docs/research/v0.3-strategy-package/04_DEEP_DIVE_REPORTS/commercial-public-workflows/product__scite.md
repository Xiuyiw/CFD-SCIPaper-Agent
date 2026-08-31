# scite

## 1. 来源

- 候选ID：`product/scite`
- 官方入口：<https://scite.ai>
- 官方公开材料：<https://scite.ai/features>、
  <https://scite.ai/blog/introducing-collections>、
  <https://scite.ai/blog/how-do-i-use-the-scite-reference-check>、
  <https://scite.ai/pricing>。
- 访问日期：2026-09-01；专有托管服务，受scite公开服务条款约束。
- 标签规则：**official claim**、**observable workflow**、**controller inference**。

## 2. 轨道与真实任务

覆盖`writing`、`agent-rag`和`quality-export`。**Observable workflow**：用户检索论文和引用陈述，
查看某论文的Smart Citation上下文，把论文组织进Collections，针对限定集合提问，或上传稿件PDF
生成Reference Check。它支持文献评价和引用核查，不撰写或验证CFD分析。

## 3. 实际代码或文档定位

- Features页：Assistant、全文检索、Reports、Collections和Reference Check的公开入口。
- Collections页：可从搜索、Zotero/Mendeley、DOI/CSV及Assistant引用建立集合；集合可监测和限定问答。
- Reference Check帮助页：登录、上传PDF、等待报告、从Profile重新访问；公开说明格式识别会漏项。
- 定价页：Basic/Pro的Assistant、Reports、Collections规模和API/MCP额度边界。
- **Not independently verified**：Smart Citation分类准确性、完整文献覆盖、集合协作及导出格式。

## 4. 架构

**Observable workflow**形成“Search/Report → Collection → scoped Assistant → Reference Check”的
循环。**Controller inference**：可迁移价值是用限定证据集约束问答、保留引用上下文，并在稿件
稳定后独立检查参考文献；本报告不推测其分类器、检索数据库或Agent内部结构。

## 5. 输入与输出

输入包括问题、论文/DOI、搜索结果、来自Zotero/Mendeley的参考文献、DOI列表/CSV，以及上传到
Assistant或Reference Check的PDF/文档。输出包括带来源回答、引用陈述及supporting/contrasting/
mentioning分类、Collections和Reference Check报告。CSV、BibTeX、RIS精确导出组合未在本轮
官方公开步骤中完整复核，标为 **not independently verified**。

## 6. 科学边界

官方Reference Check明确指出参考文献识别依赖格式和DOI，几乎总会漏掉部分项目。Smart Citation
分类属于 **official claim**，不能替代作者阅读原文或判断研究设计是否可迁移。对CFD-Paper-Agent，
该信号最多辅助“需进一步核查”，不能自动支持或反驳工程claim。

## 7. 状态与恢复

**Observable workflow**：Collections可保存、监测和重新进入；基于保存检索的集合可自动更新，手工
集合可增删文献；Reference Check可从Profile重新访问。集合版本、自动更新后的可复现快照、冲突
处理和陈旧引用警报的精确定义为 **not independently verified**。

## 8. Skill、插件或适配器

scite公开提供MCP/API入口，但本轮不研究其内部实现。**Controller inference**：未来可以把外部
引用上下文作为可选文献信号适配器；核心必须保存原始论文标识、引用陈述和作者判断，不能只保存
scite分类标签。

## 9. 测试、示例与发布边界

公开功能页和帮助文档给出示例，但没有供本轮复现的分类测试集。Reference Check需要登录且属
订阅功能；本轮未运行。公开材料已足以形成限定证据集和引用核查UX判断后停止。

## 10. 许可证与条款

专有托管服务，只借鉴UX或通过未来可选适配器接入。API、MCP、全文访问和集合规模受订阅及出版
许可约束，不能成为离线核心的必要依赖。

## 11. 优点

- 引用数量之外展示引用陈述和分类上下文。
- Collections把检索、限定问答和持续监测连接起来。
- Reference Check把稿件引用核查放在独立、作者可查看的步骤。

## 12. 缺点与风险

- 分类和覆盖并非完备，官方也承认稿件引用识别会漏项。
- 自动更新集合若不冻结快照，会削弱可复现性。
- 供应商语料、访问权和订阅限制影响结果覆盖。

## 13. 迁移判定

**idea-only**。借鉴“限定证据集合 + 引用上下文 + 稿件稳定后的参考文献检查”。若未来接入API，
应作为可选信号源，保存来源和时间，并要求作者打开原文确认。验证包括故意放入无DOI、撤稿或
相互矛盾文献，确保系统输出缺口而非虚假全通过。

## 14. Internal regression relevance

`authorized internal positive regression` 表明证据型引用必须跟随关键论断，并由作者最终核查来源；
`authorized internal negative scientific-gate regression` 表明分类或报告不能替代 CFD 数据证据。
引用信号只能提高审查优先级，不能让 claim 越过科学门。

## 15. 未验证项

未登录、未上传稿件、未运行Assistant、Collections、Reference Check、API或MCP；未验证分类准确
率、覆盖、协作、导出文件和定价配额。未公开的模型、RAG和数据库均未推测。
