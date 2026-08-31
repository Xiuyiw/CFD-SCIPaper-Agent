# PyVista

## 1. 来源

- 候选ID：`pyvista/pyvista`
- 仓库：<https://github.com/pyvista/pyvista>
- 固定版本：`81d0fec2f62b3090f8a41857f9a8c63f924a55e0`
- 访问日期：2026-08-31；许可证：MIT（`LICENSE`）。
- **事实**：以下判断来自该提交的代码、文档、测试与示例。**研究者推断**以“迁移判断”明确标出。

## 2. 轨道与真实任务

覆盖`cfd-adapters`、`scientific-analysis`和`figures`。用户入口包括`pyvista.read()`、
`DataSet`过滤器及`Plotter`；输入为VTK生态网格/场文件及多种工程格式，输出为网格、派生场、
截图或矢量图。它不定义CFD工况可比性、QoI语义或论文claim。

## 3. 实际代码或文档定位

- `pyvista/core/utilities/fileio.py::read`：按文件类型选择reader并返回`DataSet`/`MultiBlock`；
  `cls`参数可对返回网格类型做显式检查。
- `pyvista/core/dataset.py::DataSet`与`pyvista/core/datasetattributes.py::DataSetAttributes`：
  几何、拓扑及point/cell/field数组的核心对象。
- `pyvista/core/filters/data_set.py::DataSetFilters.integrate_data`：调用VTK积分过滤器生成积分量。
- `pyvista/plotting/plotter.py::BasePlotter.save_graphic`：通过GL2PS导出SVG/PDF/EPS/PS/TEX。
- 示例：`examples/00-load/read_file.py`、`examples/01-filter/integrate_data.py`；测试：
  `tests/core/test_reader.py`、`tests/plotting/test_plotter.py::test_save_graphic_raises`。

## 4. 架构

PyVista以VTK数据模型为底层，用Python对象包装网格、数组、过滤器和render pipeline。
`DataSet`把空间关联固定为point/cell/field，reader与writer集中在I/O层，`Plotter`负责显示与导出。
这是“通用网格对象 → 显式过滤 → 可视化”的清晰分层，但其科学语义仍由调用方提供。

## 5. 输入与输出

`read()`支持单文件或文件序列，并在不支持格式、文件缺失或声明类型不匹配时失败；数组名与空间
关联保存在dataset中。`DataObject.save()`可保存网格，`save_graphic()`可产生可编辑矢量图。
`field_data`可承载自定义元数据，但不是强制来源契约；嵌套`MultiBlock`的field data保存还有明确
警告。项目不自动生成论文source-data表。

## 6. 科学边界

- **单位传播**：数组和值没有强制量纲对象；单位只能由字段名或自定义metadata约定。
- **缺失值**：mesh validation可检查point/cell-data数组长度和非有限mesh-point坐标；threshold等
  过滤器有NaN处理，但不同filter的行为不能替代统一缺失值策略。
- **来源**：输入路径在调用侧可知，dataset本身不形成不可变文件哈希或claim-evidence链接。
- **QoI**：积分、采样、梯度等过滤器可计算QoI原料，但QoI定义、归一化与控制体必须由产品层锁定。
- **多case可比性**：没有边界条件、网格、采样面或参考量一致性判断。
- **错误自动推断风险**：过滤/渲染结果很容易被误当作物理结论；例如积分输出并不自动说明守恒，
  插值/平滑也不等于原始求解场。

## 7. 状态与恢复

对象可保存为标准网格格式；reader可重建网格。它没有论文项目阶段、陈旧输入检测或作者批准状态。
恢复与来源版本应由CFD-Paper-Agent管理。

## 8. Skill、插件或适配器

README与`pyvista/core/utilities/accessor_registry.py`展示了dataset accessor扩展机制，可将领域过滤器
附着到对象而不改上游类。适合实现可选的网格/场适配器，但不能让accessor越权产生scientific claim。

## 9. 测试、示例与发布边界

项目包含reader、filter、plotter和图像回归测试；示例覆盖文件读取、积分与大量3D操作。测试证明API
和渲染行为，不证明输入CFD结果的收敛性或物理有效性。当前主分支要求Python 3.10+，核心依赖
NumPy、Matplotlib和VTK。

## 10. 许可证与条款

MIT允许复用；但VTK和可选reader依赖会显著增加安装体积与平台复杂度。正式集成还需逐项核对
输入格式对应的VTK模块是否实际可用。

## 11. 优点

- 统一的非结构/结构网格和point/cell/field数组模型适合求解器无关后处理。
- reader类型检查、mesh validation和明确异常可用于fail-closed适配器。
- SVG/PDF导出及VTK过滤器为3D场图和可复现QoI计算提供成熟基础。

## 12. 缺点与风险

- 不原生保存单位、工况来源、边界条件或QoI定义。
- 3D矢量导出受GL2PS和场景内容限制，不能保证所有对象仍可编辑。
- VTK依赖较重；“可画”容易被错误提升为“可发表、可解释”。

## 13. 迁移判定

**direct reuse**（可选依赖）。目标是补强通用网格/场读取、基础空间过滤和3D图导出。适配条件是
CFD-Paper-Agent在外层强制记录源文件、单位、case ID、采样定义和变换历史，并将原始网格只读。
预期收益高，集成成本中等，主要风险是依赖体积与科学语义缺失。验证应使用公开小型VTK/Fluent
fixture检查数组关联、缺失字段、积分定义和SVG/PDF导出，而不是仅做截图smoke test。

## 14. P04 / Gate 5 对应关系

其价值对应“场图必须能回到锁定数据与明确采样定义”的正向模式；其缺口也说明，单靠可视化库
无法阻止不可比工况或错误QoI被写成结论。产品必须把scientific gate置于绘图调用之前。

## 15. 未验证项

未运行需要完整VTK渲染环境的测试，未验证每一种原生求解器reader，也未验证大型瞬态文件的内存
表现。上述事项不影响当前“可选网格/场层、非科学判定层”的迁移结论。
