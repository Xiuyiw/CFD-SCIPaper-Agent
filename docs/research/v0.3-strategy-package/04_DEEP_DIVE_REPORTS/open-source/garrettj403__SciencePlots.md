# SciencePlots

## 1. 来源

- 候选ID：`garrettj403/SciencePlots`
- 仓库：<https://github.com/garrettj403/SciencePlots>
- 固定版本：`b9b16959570bd2fbc9ff5118bacc423c3bddd592`
- 访问日期：2026-08-31；许可证：MIT（`LICENSE`）。
- **事实**来自该提交的代码、样式、测试与示例；**研究者推断**在迁移判定中标明。

## 2. 轨道与真实任务

覆盖`figures`和`quality-export`。SciencePlots为Matplotlib注册可组合的论文/期刊/颜色样式，降低
基础排版配置成本。它不读取CFD数据、不设计figure contract，也不检查图形的科学含义和出版风险。

## 3. 实际代码或文档定位

- `src/scienceplots/__init__.py`：发现包内`.mplstyle`并注册到Matplotlib样式库。
- `src/scienceplots/styles/science.mplstyle`：定义尺寸、线宽、刻度、serif、LaTeX和tight bbox等基线。
- `src/scienceplots/styles/journals/`、`styles/color/`和`styles/misc/`：按需叠加期刊、颜色和功能样式。
- 示例：`examples/plot-examples.py`；测试：
  `src/scienceplots/tests/test_scienceplots_matplotlib_3_11_and_3_12.py`和
  `src/scienceplots/tests/test_scienceplots_matplotlib_le_3_10.py`，检查不同Matplotlib版本下的样式兼容性。

## 4. 架构

其核心是Matplotlib rcParams样式组合，而非新的绘图对象。用户通过`plt.style.context([...])`叠加
`science`、期刊、颜色或`no-latex`。轻量架构便于复用，但样式冲突和语义一致性仍由调用者控制。

## 5. 输入与输出

输入为样式名和普通Matplotlib绘图代码，输出沿用Matplotlib Figure与后端文件。项目不生成source
data、图件manifest、单位记录或figure QA报告。

## 6. 科学边界

- **单位传播**：没有数据层，不检查或保存单位。
- **缺失值**：沿用Matplotlib行为，不定义缺失政策。
- **来源**：不关联输入文件、case ID、脚本哈希或图件来源。
- **QoI**：不定义、计算或验证QoI。
- **多case可比性**：不检查数据可比性或颜色/marker的case语义稳定性。
- **可编辑输出/source data**：由Matplotlib后端决定；样式本身既不保证矢量可编辑，也不导出source data。
- **错误自动推断风险**：统一美观可能掩盖错误坐标、截断范围、不当插值或不可比case。

## 7. 状态与恢复

`.mplstyle`文件可版本化并重放；没有项目状态、图件输入指纹、stale检查或批准状态。重现还依赖本机
字体、LaTeX和Matplotlib版本。

## 8. Skill、插件或适配器

可迁移的是“基线样式 + 期刊覆盖 + 功能覆盖”的组合模式。适合让CFD-Paper-Agent集中管理字体、
线宽和导出参数，但必须由figure contract与视觉/数据QA包围。

## 9. 测试、示例与发布边界

示例展示多种样式组合；测试主要证明样式可被发现和加载，不证明无遮挡、色盲可读、字体嵌入或科学
正确性。`pyproject.toml`要求Python 3.8+并依赖Matplotlib；默认`science`样式可能要求LaTeX，
无环境时需显式使用`no-latex`。

## 10. 许可证与条款

MIT允许复用。期刊命名样式不等于期刊官方模板，产品文档不得把风格近似宣称为期刊合规证明。

## 11. 优点

- 样式组合轻量，能快速形成一致的科研图基线。
- 把尺寸、字体、刻度和线宽集中配置，便于维护。
- `no-latex`提供较低依赖的降级路径。

## 12. 缺点与风险

- 只解决表层风格，不解决图型、数据语义、单位、来源和QA。
- LaTeX、字体和不同后端可导致跨平台漂移。
- 通用样式可能覆盖项目已经人工精修的局部视觉选择。

## 13. 迁移判定

**idea-only**。吸收可组合样式层的设计，不把SciencePlots设为必需依赖，也不直接覆盖项目图件。
预期收益中等、实现成本低；主要风险是把“套样式”误当出版质量。验证应包含字体缺失、无LaTeX、
SVG文本保留、bbox和用户局部覆盖测试。

## 14. P04 / Gate 5 对应关系

历史经验表明出版图需要数据、叙事和视觉三重QA；SciencePlots只能提供最低视觉基线。保留用户本地
精修优先级、marker语义和source-data闭环比自动套期刊样式更重要。

## 15. 未验证项

未执行跨平台字体与LaTeX测试，未逐项比较期刊样式，也未验证复杂多面板图。当前结论仅支持吸收
样式分层思想。
