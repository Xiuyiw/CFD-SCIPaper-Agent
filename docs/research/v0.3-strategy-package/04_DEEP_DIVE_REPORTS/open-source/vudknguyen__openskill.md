# OpenSkill

## 1. 来源

- 候选ID：`vudknguyen/openskill`
- 仓库：<https://github.com/vudknguyen/openskill>
- 固定版本：`7d6db16479cbaa7186b408516bfd09b72054bcba`
- 访问日期：2026-09-01；许可证：MIT（`LICENSE`）。

## 2. 轨道与真实任务

覆盖`skills`与`agent-rag`。OpenSkill是跨多个编码Agent安装、发现、更新和分发`SKILL.md`包的CLI，
解决宿主路径差异和Skill供应，不负责Skill的科研正确性或任务执行。

## 3. 实际代码或文档定位

- `src/core/skill.ts::loadSkillFromDir/loadSkillInfo/discoverSkills/findSkillByName`：解析frontmatter并发现Skill。
- `src/core/registry.ts::refreshRepo/searchSkills/getSkillFromRepo`：克隆/更新仓库并建立本地repo cache。
- `src/core/manifest.ts::InstalledSkillRecord/loadManifest/saveManifest/addSkillRecord`：记录来源、路径、
  commit、安装时间、宿主和scope；临时文件写入及manifest锁避免并发覆盖。
- `src/cli/install.ts::installFromGitHub`：选择Skill/宿主、检查compatibility、安装、写manifest并在失败时回滚。
- `src/cli/update.ts::checkGitUpdates/applyGitUpdate`：比较安装commit与最新commit并更新。
- 宿主路径：`src/agents/*.ts`；测试：`src/__tests__/skill.test.ts`、`manifest.test.ts`、
  `registry.test.ts`；示例：`example-skill/SKILL.md`。

## 4. 架构

统一Skill parser位于core；不同Agent实现安装路径和格式适配；repo cache用于搜索；全局manifest记录
安装来源和commit；CLI处理交互、安装、更新和回滚。它把Skill内容与分发机制分离。

## 5. 输入与输出

输入为Git仓库/marketplace、Skill名、目标Agent和scope；输出为目标Agent目录下的Skill文件及全局
manifest。它不执行Skill、不生成科研分析或论文。

## 6. 科学边界

manifest能回答“哪个Skill从哪个commit安装”，不能回答“Skill是否适合当前CFD数据或科学结论”。
compatibility是Skill声明和宿主验证，不能替代依赖可运行测试。registry搜索只提供发现，不应成为
默认信任或科学质量排序。

## 7. 状态与恢复

manifest有schema版本、文件锁、临时写入和commit记录，安装失败会尝试卸载回滚；这是实际安装
状态管理。损坏manifest当前会返回空manifest，可能掩盖状态丢失；更新是技能分发更新，不是论文
任务恢复。

## 8. Skill、插件或适配器

可迁移的重点是：宿主路径适配器、来源commit记录、project/global scope、发现和安装回滚。它只解析
基础frontmatter，没有对渐进披露、resources/scripts、依赖、回退和科学eval提供完整质量合同。

## 9. 测试、示例与发布边界

Vitest覆盖Skill解析、registry、manifest、agent路径和安装相关工具；README列出的多宿主能力有对应
adapter源码。未证明所有宿主版本均在CI真实安装，也不证明第三方Skill安全或科学有效。

## 10. 许可证与条款

OpenSkill本体为MIT；被安装Skill的许可证各自独立，不能由管理器许可证覆盖。marketplace和遥测若
启用还涉及服务条款。

## 11. 优点

- 以统一frontmatter和宿主adapter解决跨Agent路径差异。
- manifest记录commit、来源和scope，更新不只依赖Skill名称。
- 安装失败回滚和manifest锁是实用工程机制。

## 12. 缺点与风险

- 分发能力不能保证Skill方法、依赖或科研输出质量。
- 损坏manifest回退为空可能造成“已安装状态被遗忘”。
- 引入完整marketplace、认证、遥测和审计远超本项目当前需求。

## 13. 迁移判定

**idea-only**。借鉴宿主adapter、project/global scope和Skill来源commit记录；CFD-Paper-Agent V0.3先随包
内置专用Skills，不建设marketplace或全局registry。若未来有真实跨宿主安装需求，再考虑把OpenSkill
作为外部推荐工具，而非复制其管理平台。

## 14. P04 / Gate 5 对应关系

固定Skill来源可避免不同电脑使用了不一致规则；但Gate 5表明，Skill“安装成功”并不意味着它会
正确理解求解器和数据。产品验收必须继续关注实际CFD任务，而非安装/审计数量。

## 15. 未验证项

未发布或安装marketplace Skill，未在12个宿主逐一验证路径和版本兼容性，未运行安全audit。当前
判断严格限定于分发架构，不把其当作科研能力实现。
