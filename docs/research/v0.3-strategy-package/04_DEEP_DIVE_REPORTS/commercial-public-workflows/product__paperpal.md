# Paperpal

## 1. 来源

- 候选ID：`product/paperpal`
- 官方入口：<https://paperpal.com>
- 官方公开材料：<https://paperpal.com/pricing>、
  <https://paperpal.com/blog/news-updates/product-updates/paperpal-prime-now-includes-free-unlimited-manuscript-submission-readiness-checks>、
  <https://paperpal.com/productchangelog>、
  <https://support.paperpal.com/support/solutions/articles/3000129867-can-i-track-changes-and-revisions-in-paperpal-for-google-docs->。
- 访问日期：2026-09-01；专有服务，受CACTUS公开条款约束。
- 标签规则：**official claim**、**observable workflow**、**controller inference**。

## 2. 轨道与真实任务

覆盖`writing`和`quality-export`。**Observable workflow**：作者在Web、Word、Google Docs、Chrome
或Overleaf中获得逐句建议；也可上传完整稿件，先看技术检查报告，再下载带修订建议的DOCX并逐项
接受或拒绝。它是稿件语言和提交检查工具，不负责CFD科学分析。

## 3. 实际代码或文档定位

- 投稿准备公开说明：上传稿件 → 查看Technical Checks Report → 下载含Track Changes的修改稿。
- 产品更新页：Web文档可下载为带Track Changes的DOCX。
- Google Docs帮助页：Paperpal本身不维护修订历史，协作和历史依赖Google Docs原生能力。
- 定价页：不同计划提供学术语言、写作、Research & Cite、PDF问答和投稿检查额度。
- **Not independently verified**：Word/Overleaf插件实际行为、动态引用保真、团队并发和全部技术检查。

## 4. 架构

**Observable workflow**显示两种入口：编辑器内即时建议，以及整稿上传后的报告/下载。修订最终由
作者接受或拒绝。**Controller inference**：可迁移的是“局部建议不直接改稿 + 整稿检查生成可回读
产物”，而非其未公开的模型或训练架构。

## 5. 输入与输出

官方帮助页显示上传可接受DOCX/PDF等文件，整稿检查输出技术报告和带修订的DOCX；编辑器入口
输出逐句建议。Research & Cite、PDF问答和引用样式属于 **official claim**，其字段级保真未在
公开工作流中独立验证。

## 6. 科学边界

语言、格式和投稿检查不能判断CFD工况可比性、收敛、守恒、QoI或物理因果。**Controller
inference**：建议只能作用于已锁定claim的表达层；涉及数值、单位或结论强度的建议必须返回科学
证据层复核，不能由“接受修改”直接改变。

## 7. 状态与恢复

在Google Docs中，协作与版本历史由Google Docs承担；同一文档中主动拒绝的建议可在后续检查中
被识别。公开材料没有建立Paperpal自有的多文档项目/对话组织模型；Paperpal Web自身的跨版本
恢复、分支、冲突合并及输入陈旧提示均为
**not independently verified**。

## 8. Skill、插件或适配器

公开产品提供多宿主插件，但没有公开可移植Skill契约。**Controller inference**：CFD-Paper-Agent
可借鉴宿主内低摩擦建议、接受/拒绝和整稿回读，但必须保持科学内容与语言编辑权限分离。

## 9. 测试、示例与发布边界

官方帮助页给出工作流和产品示例，没有公开代码或独立测试。本轮未上传稿件或安装插件；公开材料
已经足以确认“双入口 + 作者接受/拒绝 + DOCX修订交付”的UX，故停止。

## 10. 许可证与条款

专有服务，不直接复用代码。免费和付费层的额度、下载与检查能力不同；价格和配额可能变化，不能
成为本地核心功能的前提。

## 11. 优点

- 把语言建议保持为作者可接受/拒绝的局部变更。
- 整稿检查同时提供摘要报告和可继续编辑的DOCX。
- 可嵌入作者已有写作宿主，降低迁移文档的摩擦。

## 12. 缺点与风险

- 科学正确性不在其公开检查边界内。
- 不同宿主的修订、协作和引用能力不一致。
- 公开功能声明多，文件和动态引用保真仍需真实回归验证。

## 13. 迁移判定

**idea-only**。借鉴“句级建议卡 + 接受/拒绝 + 整稿检查摘要 + 可编辑文件回读”。实现时每条建议
必须标明影响范围；数值、单位、引用和claim强度变更自动升级为作者确认。验证用真实DOCX往返，
检查非目标内容、引用字段和图表关系不被静默改写。

## 14. Internal regression relevance

`authorized internal positive regression` 支持由作者逐条批准语言修订；
`authorized internal negative scientific-gate regression` 表明，格式与语言 PASS 不能掩盖证据缺失
或趋势错误。因此，提交检查只能在科学门之后运行。

## 15. 未验证项

未安装Word、Google Docs、Chrome或Overleaf插件，未上传真实稿件，未验证引用、公式、图表、批注、
Track Changes和多用户协作的往返保真；付费额度和独立准确率未核验。
