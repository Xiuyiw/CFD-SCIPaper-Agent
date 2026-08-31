# SciSpace

## 1. 来源

- 候选ID：`product/scispace`
- 官方入口：<https://scispace.com>
- 官方公开材料：<https://scispace.com/help/en/articles/10660587-how-to-conduct-a-literature-review-using-scispace>、
  <https://scispace.com/resources/scispace-literature-review-workspace/>、
  <https://scispace.com/help/en/articles/10921653-how-to-share-literature-review-search-results-in-scispace>、
  <https://scispace.com/pricing>。
- 访问日期：2026-09-01；专有托管服务，受SciSpace公开条款约束。
- 标签规则：**official claim**、**observable workflow**、**controller inference**。

## 2. 轨道与真实任务

覆盖`writing`、`agent-rag`和`quality-export`。**Observable workflow**：用户输入主题或关键词，
筛选/排序文献，在表格中增加比较列，进入单篇PDF问答，保存到Library，并导出或分享结果。
它服务文献发现和综述组织，不读取CFD求解文件，也不生成可验证的CFD分析。

## 3. 实际代码或文档定位

- 文献综述帮助页：登录入口、搜索、过滤、Chat with PDF、Library、引用生成和导出。
- 公开工作区说明：结果表、定制列、星标/移除、CSV导出和保存搜索设置。
- 分享帮助页：新近搜索结果可通过URL共享；已保存搜索不能以该方式公开分享。
- 定价页：Literature Review、Chat with PDF、AI Writer等属于不同套餐/额度下的托管工具。
- **Not independently verified**：登录后的Deep Review、团队编辑、具体导出格式和引用保真。

## 4. 架构

**Observable workflow**呈现“检索结果表 → 定制比较列 → 单篇追问 → Library → 导出/分享”的
用户路径。**Controller inference**：结果表是有价值的中间产物，但没有公开证据支持推断其模型、
RAG、数据库或Agent架构。

## 5. 输入与输出

输入包括研究主题、关键词、种子论文和上传PDF/文件夹。输出包括带摘要洞察的文献表、保存的
Library项、单篇问答和CSV导出。官方帮助页称可导出摘要、引用和保存论文，但本轮只直接核实
CSV结果表；XLSX/BibTeX等精确导出组合标为 **not independently verified**。

## 6. 科学边界

表格比较和AI摘要可用于定位文献，但不能替代阅读全文，也不能验证CFD的量纲、边界条件或趋势。
官方页面没有展示claim到原文精确位置的稳定契约。**Controller inference**：任何生成列必须保留
来源跳转并由作者复核，不能直接进入论文事实层。

## 7. 状态与恢复

**Observable workflow**：可保存搜索设置和偏好，Library保留论文；新近搜索可分享URL。已保存
搜索不能按同一公开链接机制共享。跨会话版本、输入更新后的陈旧标识、协同冲突和失败恢复为
**not independently verified**。

## 8. Skill、插件或适配器

没有公开可移植Skill协议。**Controller inference**：值得借鉴的是“结果矩阵 + 可定制问题列 +
按论文下钻 + 保存/排除”交互，并把生成答案明确降为需复核的候选证据。

## 9. 测试、示例与发布边界

官方帮助中心提供逐步示例，但未提供可复现实验或公开代码测试。登录和付费功能未运行；当公开
页面足以确认文献矩阵、下钻和分享边界后停止。

## 10. 许可证与条款

专有托管服务，只能借鉴公开工作流。Premium与Editor套餐彼此有区别，具体额度可能变化；本项目
不能把其订阅能力作为核心运行依赖。

## 11. 优点

- 文献矩阵允许用户比较、增加列、保留或排除论文。
- 单篇下钻与整体综述在同一入口衔接。
- 搜索保存、CSV导出和轻量链接分享降低交接成本。

## 12. 缺点与风险

- 生成列的科学准确性和精确来源绑定未由本轮独立验证。
- 保存、分享和协作边界不完全一致，可能造成项目状态误解。
- 商业套餐和额度变化使其不适合成为本地核心依赖。

## 13. 迁移判定

**idea-only**。为CFD-Paper-Agent重实现“候选文献矩阵—定制证据问题—原文下钻—作者纳入/排除”
交互；输出必须写回本地EvidenceRecord而非仅保存在聊天。验证应检查每个表格答案有来源、作者
决定可恢复、导出后仍可定位原文。

## 14. P04 / Gate 5 对应关系

对应P04中“外部AI建议先形成候选，再由作者筛选”的正向模式；同时吸收Gate 5教训：矩阵看似
完整不等于数据可比或结论成立，缺少CFD证据时必须停在文献辅助层。

## 15. 未验证项

未登录、未运行Deep Review、AI Writer或团队功能；未验证XLSX/BibTeX导出、引用字段、付费额度、
PDF解析准确性和保存搜索的版本语义。
