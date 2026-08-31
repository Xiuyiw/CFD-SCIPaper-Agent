# Matplotlib

## 1. 来源

- 候选ID：`matplotlib/matplotlib`
- 仓库：<https://github.com/matplotlib/matplotlib>
- 固定版本：`522cfa3000de008daddec8a6f6b0d6ce3056177f`
- 访问日期：2026-08-31；许可证：Matplotlib License（PSF-based，`LICENSE/LICENSE`）。
- **事实**来自该提交的代码、文档、测试与示例；**研究者推断**在迁移判定中说明。

## 2. 轨道与真实任务

覆盖`figures`和`quality-export`。Matplotlib提供二维绘图对象、布局、标注及多种栅格/矢量后端，
是可编程科研绘图基础。它不负责CFD数据可比性、QoI选择、figure contract或论文claim。

## 3. 实际代码或文档定位

- `lib/matplotlib/figure.py::Figure.savefig`：公共导出入口。
- `lib/matplotlib/backend_bases.py::FigureCanvasBase.print_figure`：选择格式、dpi、bbox和后端打印流程。
- `lib/matplotlib/backends/backend_svg.py::FigureCanvasSVG.print_svg`与`backend_pdf.py`：SVG/PDF矢量输出。
- `lib/matplotlib/units.py::ConversionInterface`和`Registry`：坐标显示单位转换协议。
- `lib/matplotlib/cbook.py::safe_masked_invalid`：把非有限输入转换为masked array。
- 示例：`galleries/examples/lines_bars_and_markers/masked_demo.py`；测试：
  `lib/matplotlib/tests/test_figure.py`、`test_backend_svg.py`、`test_backend_pdf.py`、`test_units.py`。

## 4. 架构

Artist层表达图元，Axes/Figure组织坐标与布局，Canvas/Renderer/Backend负责输出。数据转换、绘制和导出
相互分层，使脚本可复现并支持后端扩展；科学语义和视觉合同仍属于上层产品。

## 5. 输入与输出

输入为Python数组、类别或可通过units registry转换的对象；输出包括PNG、TIFF、SVG、PDF等。SVG/PDF
可保留矢量文字和路径，但字体配置、`svg.fonttype`及rasterized artists会影响可编辑性。库不自动导出
与图一致的source-data表。

## 6. 科学边界

- **单位传播**：units接口服务坐标显示转换，不是完整量纲代数或QoI单位验证。
- **缺失值**：NaN和masked values通常形成断线/空点；不同artist行为仍需图前检查。
- **来源**：Figure metadata可写入文件，但不自动关联数据文件、脚本哈希和case ID。
- **QoI**：仅绘制给定数据；不会验证公式、归一化、控制体或采样窗口。
- **多case可比性**：不会阻止不同单位、网格、时间窗或边界条件的数据同图比较。
- **可编辑输出/source data**：支持SVG/PDF，但可编辑性取决于配置；source data必须另行生成并校验。
- **错误自动推断风险**：平滑、轴截断、双轴、颜色尺度和插值都可制造视觉上可信但科学上错误的趋势。

## 7. 状态与恢复

脚本、rcParams和输入表可重放图形；Figure pickle并非长期科研归档契约。产品应持久化figure contract、
source data、脚本版本、环境和输出哈希，而不是依赖内存Figure状态。

## 8. Skill、插件或适配器

后端、style、unit converter和projection提供扩展入口。CFD-Paper-Agent可在其上建立受控figure builder、
统一样式与QA钩子，但不得让通用artist API绕过锁定source data。

## 9. 测试、示例与发布边界

项目包含广泛的单元、后端和图像回归测试；示例覆盖缺失值、布局和导出。测试保证绘图库行为，不证明
具体科研图无误。当前主分支`pyproject.toml`要求Python 3.12+；产品需选择覆盖3.10--3.12的稳定版本。

## 10. 许可证与条款

Matplotlib License允许分发和修改，需保留相应许可与版权通知。集成还要固定字体和后端依赖，避免
跨平台输出漂移。

## 11. 优点

- 成熟、可编程且拥有高覆盖的栅格与矢量后端。
- Artist/Axes/Figure层次适合构建可测试的论文图模板。
- 图像回归和bbox接口可支撑程序化视觉QA。

## 12. 缺点与风险

- 不原生生成source data、科学来源或claim-evidence关系。
- 单位接口不等于量纲安全，视觉正确不等于科学正确。
- 复杂多面板图容易因手工参数和环境差异产生遮挡、裁切或字体漂移。

## 13. 迁移判定

**direct reuse**（核心绘图引擎，固定兼容版本）。在其上实现figure contract、集中样式、source-data
导出、数据/叙事/视觉QA和矢量文本检查。预期收益高、集成成本中等；主要风险是无约束API导致图形
与证据脱节。验证必须覆盖数据哈希、轴单位、NaN、bbox、字体、SVG/PDF文本和PNG/TIFF输出。

## 14. Internal regression relevance

可迁移的是脚本化绘图、可编辑输出和双重视觉QA；必须保留的教训是，只做渲染成功或样式统一不能
证明QoI、趋势和case比较正确。科学门控必须在绘图之前，source data闭环必须与导出同时完成。

## 15. 未验证项

未运行完整图像测试，未评估所有后端和字体组合，也未选定支持Python 3.10的具体版本。当前报告只
支持继续以Matplotlib为受控核心，不支持把上游main直接设为依赖基线。
