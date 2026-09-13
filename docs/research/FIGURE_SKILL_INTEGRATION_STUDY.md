# 科研机制图：外部 Skill 复用与集成研究

2026-09-13。服务于 v0.6.0 之后的写作规划；本轮仅查证与设计，未安装、执行或集成外部项目。
选择依据是实际 Skill、实现入口与依赖，不是星数、演示美观程度或模型自评分。

## 1. 结论

优先复用成熟绘图工具与已有 Skill，不再自研通用画布、图形语法、图像生成模型或全套编辑器。
本项目保留的核心职责是：科学问题、量的定义、图件证据、图文对应及作者修改的保留。
“接入一个 Skill”与“宿主实际生成并验证可用图件”分开验收。

必须区分三类任务，不能把所有“机制图”都交给文生图：

| 任务 | 合适路径 | 本项目不可交出去的职责 |
|---|---|---|
| 数据型机制综合图：贡献拆解、轴向分布、热量与面积/通量关系 | 宿主调用科研数据绘图 Skill，使用 Matplotlib 及现成多面板工具；复杂图保留可运行脚本 | 数值与工况映射、统计域、算子、参考值、离散数据语义 |
| 概念机理/方法/结构示意图：实体、流向、反馈、因果假说 | SVG 或 draw.io Skill；必要时用生成图探索构图 | 哪些箭头是已证实关系、哪些是假说；几何比例是否有定量含义 |
| 混合图：真实云图 + 数值图 + 原理解释 | 复用真实场图和数据图，外部工具完成矢量标签及组合 | 不生成“像 CFD 的云图”冒充计算；统一单位、色棒语义与插入尺寸 |

两个孤立数值没有复杂关系时仍应采用小表或正文；集成高阶工具不是强制复杂化。

## 2. 实际查证的候选与取舍

许可证为本轮 GitHub 仓库元数据/许可证入口核查结果；正式采用时保留相应版权文件。
代码许可不自动覆盖外部图标、模型权重或第三方素材。

### A. 首选：轻量可编辑示意图

[pengqianhan/codex-paper-figure-skill](https://github.com/pengqianhan/codex-paper-figure-skill)（MIT）。
已完整读取 [`codex-paper-figure-skill/SKILL.md`](https://github.com/pengqianhan/codex-paper-figure-skill/blob/main/codex-paper-figure-skill/SKILL.md)。
它从论文内容抽取实体与关系，借助 Codex 图像生成探索布局，再生成可编辑 mxGraphModel XML；
draw.io Desktop 可导出 PDF/SVG/PNG。Skill 包本身主要是宿主指令，不是独立图形引擎。

采用建议：首个示意图后端候选。保留科学关系、可编辑文本和连接线的做法。
上游绑定 Codex 图像生成，不能直接宣称适用任意模型；非 Codex 宿主需使用能力等价路径或明确跳过构图参考生成。
不强制下载 Flaticon 图标，不把位图参考作为数值依据；模板和图像生成均不改变原始场数据。

### B. 首选参考：数据图与混合多面板

[CuiMuxuan/academic-codex-skills](https://github.com/CuiMuxuan/academic-codex-skills)（MIT）。
完整读取 `skills/academic-figure-workflow/SKILL.md`、方法选择 reference，并查看
[`scripts/make_nature_multipanel.py`](https://github.com/CuiMuxuan/academic-codex-skills/blob/main/skills/academic-figure-workflow/scripts/make_nature_multipanel.py)
的 `PanelSpec`、`floats()`、`plot_panel()` 与部分 QA 实现。
路线覆盖 SVG、draw.io、Matplotlib 和小表；现成脚本支持 line/scatter/errorbar/bar/hist/image，
并不等于已实现所有贡献图或机制综合图。

采用建议：按需借用图型选择、最终尺寸检查与多面板组织参考，不整包搬入其所有流程。
发现一个具体适配问题：`floats()` 分列跳过非法值，`plot_panel()` 分别构造 x/y；
若两列缺失发生在不同行，即使长度相同也可能错配。需改为消费本项目已配对的同源数据，
不能直接把该读取实现放到数值链。其普通绘图函数使用相同 marker 等默认值，仍需适配项目样式。
这是一项有实际代码依据的最小修复要求，不是新增泛化安全平台。

### C. 样式工具，不是机制理解器

[garrettj403/SciencePlots](https://github.com/garrettj403/SciencePlots)（MIT）。
查看 `src/scienceplots/__init__.py`：主要把样式表注册至 Matplotlib。
复用方式仍是可选样式层；本项目作者确认的字体、字号、网格线优先。
它不能负责选指标、选择图型、证明机制或解决复杂布局，不能仅添加此依赖就声称图件升级。

### D. 条件性备选，不作为首批强制依赖

- [ResearAI/AutoFigure-Edit](https://github.com/ResearAI/AutoFigure-Edit)（仓库 MIT）：
  本轮查看 README、架构说明与论文入口，未运行实现。支持图像到 SVG 模板及可编辑组合，
  也会嵌入裁切图标；不是所有元素都变为矢量路径。SAM/背景移除与模型 API 的安装成本较高，
  先保留为已有复杂示意图重建的备选，不纳入默认安装。
- [dwzhu-pku/PaperBanana](https://github.com/dwzhu-pku/PaperBanana)（Apache-2.0）：
  读取 `agents/visualizer_agent.py` 的配置和执行入口；统计图路径生成 Matplotlib 代码，
  示意图路径调用图像模型。可借鉴“内容规划—风格—生成—定向修正”，
  不移植多角色运行时、默认并发数与长重试，也不让模型输出代码绕过源数据绑定。
- [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills/tree/main/skills/scientific-schematics)
  （MIT，旧 `claude-scientific-skills` 地址会重定向）：查看 Skill 与 `generate_schematic.py` 入口。
  是基于外部 API 的示意图生成路线，需 OpenRouter 凭据。
  可作可选构图服务；自动评分阈值不是科学正确或期刊录用标准，不作为我们的验收替代物。

## 3. 教程与视频怎么吸收

已查到并阅读作者教程 [Building a skill for coherent science illustrations](https://shreyasprakash.com/science-illustrations/)：
值得吸收的是统一视觉语言与明确保留的科学元素，再从参考风格生成，而不是只写“Nature 风格”。

[AutoFigure-Edit 论文页](https://arxiv.org/abs/2603.06674)提供了
[作者演示视频](https://youtu.be/10IH8SyJjAQ)及实现入口，可用于后续验证交互方式。
还检索到 Bilibili 的 [Codex 科研 Skill 教程](https://www.bilibili.com/video/BV12yN264E4C/)。
本轮未取得这些视频的完整可验证字幕，也未逐帧观看；因此只登记为观看线索，不声称吸收了视频全部经验。

教程若没有公开 Skill/脚本，只参考构图和交互；有源码则追到源码核查输入、编辑性与导出。
宣传中的“顶刊级”“代替大部分科研”不计入能力证据，不需要持续搜集更多同类教程来延迟实施。

## 4. 建议的薄集成，而不是新的绘图平台

复用现有 `cfd-figure-production` Skill、`FigureContract`、材料包和图件导入路径：

1. 宿主根据数据关系选择数据图、示意图或混合图；作者已给方向时不重新设问。
2. 任务包携带源表/已计算值、真实场图、图件职责、术语、单位、插入尺寸及必要的外部 Skill 参考。
3. 选择一个实际可用后端执行。数据图使用已有 Matplotlib；示意图优先 SVG/draw.io；
   生成式图像为可选构图或非定量素材，不让无图像 API 的用户无法画普通图。
4. 返回现有输出目录：可编辑源文件或脚本、预览/投稿导出、caption 与正文应解释的关系。
   有位图资产时如实说明哪些部分可编辑；不新建插件市场、下载器或多层注册表。
5. 回收后检查数值映射、箭头语义和 Word 内实际尺寸；复杂图只对真实问题定向修改。

首批最多采用两个绘图路径（数据图、示意图）。从读取过的 Skill 中裁剪必要参考并保留署名，
或调用用户已安装版本；不复制所有生物医学规则、循环审批、外部引用指令和强制云模型要求。
每项集成必须说明相对上游的实质修改，不能把改过的 Skill 仍描述为上游原版。

## 5. 首次集成验收

| 任务 | 输入与要求 | 证明什么 |
|---|---|---|
| 定量机制组合 | 已知贡献/分布源表 + 真实场图；提供主关系、少量定量锚点和不重复的 panel 职责 | 接入后实际完成图，而非只生成 prompt；与原表读数相同，最终 Word 尺度可读 |
| 概念示意图 | 已确认物理关系/假说，明确箭头意义；不使用未公开数据作为网上检索关键词 | 可编辑源可重新打开，改一处标签/箭头后可再次导出；不把假说画成计算证据 |
| 作者局部修改 | 作者精修脚本或 SVG/draw.io，指定仅修改一处文字 | 保留其他布局、图元、数据及所有有意样式 |

同一项失败最多做两轮定向修复；仍失败则改用备选并记录具体障碍，不无限评审/重画。
首次测试没有 API 或后端时，只完成可用分支，不把未执行候选标为成功。

## 6. 与完整论文路线的关系

绘图路线是并行支线，不能阻断全稿结构、文献和方法章节开发。
详细顺序见 [后续写作发展计划](POST_V060_WRITING_PLAN.md)。
本报告确认了值得试用的外部实现，不代表它们已经集成或科学质量已通过本项目试验。
