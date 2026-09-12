---
date: 2026-09-12
branch: workstream/v05-integration
plan: docs/research/V0_5_IMPLEMENTATION_PLAN.md
session-log: none on disk
status: in_progress
---

# V0.5 实施恢复入口

## 当前目标和批准状态

从成熟CFD结果产出科学深入、原表支撑、成稿尺度可读的结果小节；长期保留全稿、自审与真实返修方向。
V0.5详细计划已写好，三条只读规划支线完成，文件所有权冲突已修正。
作者在上下文管理完成后，同意“本对话主控+两个独立执行对话”的建议并要求继续下一步；首批M1及M2独立工作启动。
后续作者已明确要求完成v0.5.0正式正确发布；主控可执行版本、CI、推送和发布，不扩展到下一版本功能。

## 事实源和最短读取顺序

1. `AGENTS.md`：唯一当地总则及本轮上下文策略；再核对实际`git status`，保护未提交修改。
2. 本checkpoint → `docs/research/V0_5_IMPLEMENTATION_PLAN.md:3`（状态）、`:42`（接口）、`:95`（分工）、`:119`（验收）。
3. `private-fixtures/v05-planning/ASSET_REUSE_MAP.md:5`：私有来源索引；按当前任务只选必要资产。
4. `docs/research/POST_V031_DEVELOPMENT_PLAN.md:1`：历史路线和实测不足，仅需背景时读取。
5. `docs/ROADMAP.md`：长期范围。当前文件内容和作者新决定优先于旧行号或旧记忆。

## Git和未提交成果

进入本轮时`main` HEAD=`6826b91`，为v0.4.0发布代码基线。现已在`workstream/v05-integration`以`3450fb2`保存前序代码增量和实施计划；未推送或发布V0.5。
最近五项提交：6826b91打包排除；1346a1c版本范围文档；4b72b4e小节/DOCX；b0366b9设计；9d77c87 CI。
进入本轮时8个tracked修改＋3个untracked文件，都是需保留的前序工作，不是可清理垃圾：
- `docs/ROADMAP.md`、`docs/research/POST_V031_DEVELOPMENT_PLAN.md`、新增`docs/research/V0_5_IMPLEMENTATION_PLAN.md`；
- `examples/section-writing/README.md`；写作Skill及`references/mechanism-subsections.md`；
- `src/cfdpaper/publication/section.py`、新增`table_evidence.py`；
- `tests/publication/test_section.py`、新增`test_table_evidence.py`、`tests/test_section_cli.py`。
上述已有增量已纳入`3450fb2`，不重做或丢弃。M1–M4实际实现已提交为`c265290`；A/B本批均已完成并暂停，未进行Git操作。主控只按明确文件范围提交，不能清理或覆盖支线修改。
AGENTS、私有案例及索引可能被Git忽略：新聊天在同机可以读取，换电脑不能只带Git提交而漏掉所需私有输入。

## 已完成 / 不重做

- 本次散热外审A–F已完整处理为有界修订，原材料保留；私人小节/三图/四页Word已有实际渲染。
- 原表计算已接prepare/assemble，来源和计算结果随包；图像具体观察可保存；局部DOCX格式已修。
- 前轮152项相关测试通过；192条原记录、6组表计算回放通过。不是本轮新测试、全量CI或独立盲测。
- P04 Fig.5既有两次写作、Fig.12/13多证据回放保留；不重跑同一稿来制造新成绩。
- 三个规划子任务v05_science_assets、v05_format_design、v05_integration_plan均只读完成。实施对话已启动，见下。

## 当前执行对话和所有权

- A科学分析与写作：`01a095f8-1b29-7d51-8bf2-a6bd0583cc7c`；首批仅table_evidence及其测试、写作Skill。实现`resolve_table_result`，供主控绑定写作引用。恢复记录`.cfdpaper/checkpoints/v05-science.md`。
- B科研绘图：`01a095f8-1cff-79f2-b59c-9b01dcc612d3`；首批仅render_figure及其测试、绘图Skill、完整示例脚本。补齐四格式输出。恢复记录`.cfdpaper/checkpoints/v05-figures.md`。
- 主控独占section.py/CLI/figures.py/公共接口、DOCX和整合文件；两个执行端均不提交、合并、推送或发布，也不改ASSET_REUSE_MAP。初始提示中共享索引写入权限已明确撤回。
- 两端使用同一仓库、同一分支、互斥文件；不再建立平行仓库。首批完成汇报后由主控衔接下一批，不要求作者搬运消息。

## 必须记住的取舍和剩余缺口

- 科学55%、绘图写作25%、易用性10%、必要可靠性10%；STOP THAT SHIT，不增加治理对象。
- 格式是交付要求：最终尺寸的图内pt、四格式图件、DOCX样式/分页/题注、有限原生表格和公式、实际页面预览。
- `result_ref`已接入正文和图注value token：从当前原CSV重算，手填值/单位不能覆盖绑定量，section.json保存resolved_values来源及未取整数值。96项表计算/小节/CLI相关测试通过；不是全量V0.5验收。
- `near-reference`已接CLI；style/sizing采用mm/pt，DOCX保存.layout.json；随包Skill已移除源码examples依赖。
- M2/M3：四格式/固定画布、原生表格、显示及行内OMML、可选PDF预览已实现。公开合成例子后置3页/近引用2页已实际渲染；保存于`.cfdpaper/outputs/v05-format-demo/`。
- 本地全量1194 passed/2 skipped在行内数学补充前通过；行内补充后45项section/CLI通过。本地sdist→wheel及隔离安装来源、实际DOCX示例通过；发布平台CI仍待做，不称V0.5完成。
- 壁温面集/算子冲突、派生量网格稳健性和横向输运是具体项目未决项；本版不猜值或自动补算。
- P04 Fig10已选内部图表匹配v25o并执行隔离输入首次355词写作，位置`private-fixtures/v05-writing`；未声明其为最终投稿图。科学初查无硬错，行内数学格式缺口已进入产品；原图源最小字号未知，密集图不称已通过8pt检验。
- 散热4个CV从92出口原表绑定，段落恢复与旧稿一致、192原记录随包完整；新回归`private-fixtures/chip-cooling/product-feedback/v05_binding_replay_result.json`，不是重复盲写。
- 生成者只看任务输入，评价端保留成稿；软件测试、人工修稿和新任务写作质量分别报告。

## 下一步（最多三项）

1. 核对实际Git状态；从M5发布准备继续，不重做M1–M4、两类试用或已通过的同输入检查。A/B均已完成本批，暂不派发无关任务。
2. 更新候选版本文档和最终验证；Windows/Linux支持矩阵需真实CI结果，公开推送/发布已由最新目标授权，不能用本机Python 3.14测试替代。
3. 汇报科学首稿与格式实测结果；保持私有输入、首次稿和格式衍生版独立。仅科学/范围/覆盖或发布授权缺口需要询问作者。

本地安装验证：`%TEMP%/cfdpaper-v05-package-49134862/`。
构建成功并确认安装包导入来源、随包Skill、原表绑定和原生表/公式DOCX；复用本机已有依赖，不是跨平台CI。
该次构建的版本字段为0.4.0，该目录仅是未发布开发快照，不得当作公开0.4.0或V0.5发布产物；正式0.5.0候选在M5重新构建。
P04格式衍生版：`private-fixtures/v05-writing/format-revised-section/section.docx`和`section.pdf`；两页已实际预览。
公开示例预览：`.cfdpaper/outputs/v05-format-demo/near-reference.docx`及`near-reference-pages/near-reference.pdf`。

## 新对话恢复提示词

> 恢复CFD-Paper-Agent V0.5工作。先读AGENTS.md、本checkpoint和V0_5_IMPLEMENTATION_PLAN.md，再核对实际工作区及两端恢复记录。首批实施已获作者批准，不重复询问或重做外部评审/P04既有回放。保留未提交代码和私有资产，先查两执行对话当前状态再接续。主控+A/B按文件独占分工；不得将3450fb2或旧测试结果称为V0.5完成/发布。
