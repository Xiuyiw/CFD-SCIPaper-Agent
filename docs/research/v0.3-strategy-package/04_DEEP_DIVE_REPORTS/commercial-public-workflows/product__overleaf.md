# Overleaf

## 1. 来源

- 候选ID：`product/overleaf`
- 官方入口：<https://www.overleaf.com>
- 官方公开材料：<https://docs.overleaf.com/managing-projects-and-files/uploading-a-project>、
  <https://docs.overleaf.com/managing-projects-and-files/downloading-a-project>、
  <https://docs.overleaf.com/collaborating/reviewing-and-reviewers>、
  <https://docs.overleaf.com/templates/submitting-to-publishers>、
  <https://docs.overleaf.com/getting-started/free-and-premium-plans/plan-limits>。
- 访问日期：2026-09-01；专有托管服务，公开编辑器代码不在本Task分析范围。
- 标签规则：**official claim**、**observable workflow**、**controller inference**。

## 2. 轨道与真实任务

覆盖`writing`和`quality-export`。**Observable workflow**：用户从模板、空项目或上传ZIP创建LaTeX
项目，编辑源码并编译预览，邀请编辑者/审阅者，查看评论和修订，再下载PDF/源码或转交出版社。
它是协作排版与交付环境，不生成CFD科学内容。

## 3. 实际代码或文档定位

- 上传页：`.tex`、`.bib`和图件ZIP建立项目，说明文件数、大小、主文档与编译器限制。
- 下载页：PDF和源码ZIP分别下载，标准源码ZIP不包含编译生成文件；`.bbl`需单独取得。
- Reviewing页：Editing、Reviewing、Viewing模式及Reviewer权限。
- 出版社提交页：按合作方选择直接传输或手动下载/上传。
- Plan limits页：编译时限、协作者、历史、Track Changes和集成按计划分层。

## 4. 架构

**Observable workflow**的关键是源码、编译产物和投稿包三类对象分开，并在同一项目内提供预览与
审阅角色。**Controller inference**：可迁移的是“产物类型显式分层 + 编译前后反馈 + 投稿前作者
触发”，不是Overleaf未公开的内部服务架构。

## 5. 输入与输出

输入是LaTeX源码、BibTeX、图件和模板；输出是编译PDF、源码ZIP以及在特定提交路径中包含`.bbl`
等生成文件的投稿包。直接出版社传输只适用于部分合作伙伴；其他期刊仍需作者下载并上传。

## 6. 科学边界

编译通过只说明排版链可执行，不证明数值、单位、引用角色或科学结论正确。**Controller inference**：
CFD-Paper-Agent应在科学证据和图件QA通过后才进入渲染/交付；编译错误与科学错误要用不同通道
呈现。

## 7. 状态与恢复

**Observable workflow**：项目保存源码和评论；History可比较、下载和恢复版本，免费层只显示近期
历史而高级计划提供完整历史。Reviewer模式可跟踪建议并由作者接受/拒绝。离线冲突、Git同步和
大型项目恢复未在本轮验证。

## 8. Skill、插件或适配器

本Task不分析公开编辑器代码或插件协议。**Controller inference**：Overleaf适合作为可选外部LaTeX
交付目标；核心只需生成标准项目包、编译说明和明确的人工提交检查点，不需要复制协作平台。

## 9. 测试、示例与发布边界

官方文档提供逐步上传、下载、审阅和投稿流程。没有运行真实项目；官方页面已足以确认产物分层、
角色和投稿边界后停止。合作出版社的具体字段映射为 **not independently verified**。

## 10. 许可证与条款

托管服务受Overleaf条款和计划限制。直接提交、完整历史、Track Changes、Git/GitHub集成和协作者
数量可能受计划或出版社集成影响。只借鉴UX，不复制专有实现。

## 11. 优点

- 源码、PDF和投稿包边界明确，错误反馈靠近编译预览。
- Editing/Reviewing/Viewing角色与作者最终接受权清楚。
- 同时支持手动可移植ZIP和部分出版社直连。

## 12. 缺点与风险

- 编译成功容易被误当作论文完成，科学门仍需独立存在。
- 标准源码下载不含所有生成文件，若不理解`.bbl`边界可能提交不完整。
- 大项目、编译时限、历史和协作能力受计划限制。

## 13. 迁移判定

**idea-only**。借鉴“源码包—编译预览—审阅角色—作者触发导出/提交”的交付UX；实际导出优先
使用标准LaTeX/Quarto后端和可下载ZIP。验证要检查PDF、源码、BibTeX、图件及必要生成文件均在
目标期刊要求下完整，并确保提交动作永远由作者触发。

## 14. Internal regression relevance

`authorized internal positive regression` 支持最终系统 PDF 逐页检查和作者提交的有效模式；
`authorized internal negative scientific-gate regression` 表明外观完整不能覆盖科学失败。因此，
Overleaf 式交付只在科学与证据门通过后启用，且仍保留人工预览。

## 15. 未验证项

未登录、未上传或编译项目，未测试协作、Track Changes、History、Git/GitHub同步或出版社直连；
未核实各合作期刊字段映射、动态计划权限和大型项目性能。
