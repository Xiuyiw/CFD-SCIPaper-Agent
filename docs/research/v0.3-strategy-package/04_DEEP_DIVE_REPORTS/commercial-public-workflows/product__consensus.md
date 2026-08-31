# Consensus

## 1. 来源

- 候选ID：`product/consensus`
- 官方入口：<https://consensus.app>
- 官方公开材料：<https://consensus.app/home/resources/consensus-responsible-ai/>、
  <https://consensus.app/home/resources/consensus-libguide-for-academic-research/>、
  <https://consensus.app/home/resources/turn-your-reference-list-into-an-thinking-partner/>、
  <https://consensus.app/home/terms-of-service/>。
- 访问日期：2026-09-01；专有托管服务，受Consensus公开服务条款约束。
- 标签规则：**official claim**、**observable workflow**、**controller inference**。

## 2. 轨道与真实任务

覆盖`writing`、`agent-rag`和`quality-export`。**Observable workflow**：研究者提出问题，选择搜索
模式和筛选条件，阅读带可点击引用的综合及单篇结果，把论文/线程保存到Lists或Collections，并
将分析或参考文献移入外部写作工具。官方明确称其不是论文写作工具。

## 3. 实际代码或文档定位

- Responsible AI页：搜索、综合、可点击引用，以及“仍需阅读和评价原文”的人工责任。
- LibGuide：搜索模式、过滤器、结果组成、Threads、Lists和参考文献导出步骤。
- Collection工作流页：从限定文献集提问，生成参考文献，导出RIS/CSV或复制带引用分析。
- 条款页：托管服务及使用边界。
- **Not independently verified**：完整语料覆盖、综合准确性、团队协作和付费搜索深度。

## 4. 架构

**Observable workflow**表现为“问题 → 检索/综合 → 来源跳转 → 保存集合 → 继续追问 → 导出”。
官方公开页对其检索方法有产品说明，但本报告只把它作为 **official claim**，不推断数据库、RAG、
模型或内部Agent架构。

## 5. 输入与输出

输入为研究问题、单篇论文或用户维护的参考文献集合。输出包括带引用的简短综合、论文结果、表格/
可视化摘要、Lists/Collections，以及RIS/CSV、格式化参考文献、PDF或带引用文本。精确格式组合和
计划限制可能随产品变化。官方公开材料没有充分说明通用本地文件导入流程，故该项为
**not independently verified**，不能从“限定参考文献集合”反推任意文件导入能力。

## 6. 科学边界

官方明确要求用户打开论文、核对引用位置并评价局限；摘要不能替代原文。Consensus适合发现研究
趋势或潜在冲突，不验证CFD边界条件、单位、QoI或机制。**Controller inference**：综合句只能进入
文献候选层，需由原文支持片段和作者判断后才能绑定claim。

## 7. 状态与恢复

**Observable workflow**：Threads保留连续追问，Lists/Collections保存论文和线程；集合内或主Library
可分别导出。集合共享、版本快照、语料更新导致的结果漂移和删除恢复为
**not independently verified**。

## 8. Skill、插件或适配器

官方提供外部集成/API入口，但本轮不验证。**Controller inference**：可借鉴“先返回可点击证据，
再提供短综合与下一步问题”的呈现顺序；不应把综合文本直接送入论文写作，也不需要复刻其产品
架构。

## 9. 测试、示例与发布边界

官方LibGuide提供教学示例和人工核验建议，不是独立准确性测试。本轮未登录或调用产品/API；公开
文档足以确认其检索、集合、来源跳转和导出UX后停止。

## 10. 许可证与条款

专有托管服务，只借鉴公开交互。账户、搜索模式、API/MCP和导出额度受计划与条款约束；未来集成
只能是可选provider，不得成为本地科学核心的前提。

## 11. 优点

- 明确把产品定位为研究检索而非代写工具。
- 每个综合结果提供来源跳转，并反复提示阅读原文。
- Lists/Threads/Collections把发现、组织和连续追问连接起来。

## 12. 缺点与风险

- 综合可能遗漏语境和原文限制，官方亦明确承认需人工核查。
- 语料覆盖、排序和计划权限影响可见证据。
- 不能把文献“共识”直接迁移为具体CFD模型或工况结论。

## 13. 迁移判定

**idea-only**。借鉴“来源优先的短综合 + 一键下钻 + 保存到项目证据集 + 导出到参考文献管理器”。
实现时综合必须链接到EvidenceRecord，且作者确认原文角色。验证用相互矛盾和范围不一致的论文，
确保系统暴露分歧而不是生成虚假统一结论。

## 14. P04 / Gate 5 对应关系

对应P04中外部AI意见必须回到原文和作者判断的经验；Gate 5提醒，即使检索有来源，也不能替代
案例可比性和数据正确性。文献综合应帮助提出问题，而不是替CFD结果背书。

## 15. 未验证项

未登录、未运行Pro/Deep搜索、Threads、Collections、团队协作、API或MCP；未独立验证语料覆盖、
摘要准确性、Consensus Meter或导出保真。未公开的内部实现未作推测。
