# xarray

## 1. 来源

- 候选ID：`pydata/xarray`
- 仓库：<https://github.com/pydata/xarray>
- 固定版本：`8ea7c88504730ec16c0620e88b4f10d2068d1a31`
- 访问日期：2026-08-31；许可证：Apache-2.0（`LICENSE`）。
- **事实**基于该提交；采用建议为**研究者推断**。

## 2. 轨道与真实任务

覆盖`cfd-adapters`与`scientific-analysis`。xarray用`DataArray`和`Dataset`处理带dims、coords和attrs
的N维数组，支持按标签选择、对齐、组合、聚合、绘图及NetCDF/Zarr等I/O。它不理解CFD边界条件、
网格拓扑、收敛或claim ceiling。

## 3. 实际代码或文档定位

- `xarray/core/dataarray.py::DataArray`与`xarray/core/dataset.py::Dataset`：标签化数组和多变量数据集。
- `xarray/structure/alignment.py::Aligner`：以`join`与`fill_value`控制坐标对齐。
- `xarray/structure/concat.py::concat`、`xarray/structure/combine.py::combine_by_coords`：多对象组合。
- `xarray/backends/api.py::open_dataset`：I/O入口，并将路径写入`ds.encoding["source"]`。
- `xarray/backends/plugins.py::list_engines`与`BackendEntrypoint`：entry-point后端发现。
- `xarray/core/dataset.py::Dataset.to_netcdf`：可移植source-data输出。
- 示例：`doc/examples/_code/accessor_example.py`；测试：`xarray/tests/test_dataset.py`、
  `test_dataarray.py`、`test_concat.py`、`test_combine.py`、`test_backends.py`。

## 4. 架构

`DataArray`把数据、维度、坐标、名称和attrs组合；`Dataset`在共享坐标上组织多个变量。alignment
基于坐标标签而非数组位置，backend entry points隔离存储格式，accessor注册允许领域扩展。该模型
适合表达`case × section × variable`，但不会校验这些标签在物理上是否可比。

## 5. 输入与输出

可从NetCDF、Zarr及插件后端打开数据，也可由NumPy/pandas构造。`encoding["source"]`保存打开路径，
attrs可保存单位与来源，但二者都是可变metadata。NetCDF/Zarr可保留坐标、变量attrs和缺失值编码，
适合作为分析中间层与source-data载体；图件本身仍由Matplotlib等后端生成。

## 6. 科学边界

- **单位传播**：`attrs["units"]`能供标签/编码使用，但算术不做量纲校验；需Pint或项目单位层。
- **缺失值**：alignment可用`fill_value`引入缺失，聚合通常提供`skipna`；默认行为必须由QoI契约显式
  固定，不能悄悄把缺case视为零。
- **来源**：backend保存source路径，但转换、拼接后不自动形成完整provenance链。
- **QoI**：命名维度上的groupby/reduce适合实现QoI，但控制体、加权方式和归一化仍由产品层定义。
- **多case可比性**：`join="exact"`能阻止坐标不一致，`override`则可能掩盖差异；物理可比性还需要
  BoundaryRecord/MeshRecord和分析计划。
- **可编辑输出/source data**：NetCDF/Zarr/CSV转换可作为source data；内置plot不负责论文图QA。
- **错误自动推断风险**：自动alignment、broadcast和`skipna`可能产生数值合理但物理错误的趋势。

## 7. 状态与恢复

惰性后端、Dask集成和可序列化Dataset支持大数据与断点重开；文件是否陈旧、case是否被替换仍需
外层基于文件版本管理。xarray不是论文项目状态机。

## 8. Skill、插件或适配器

backend entry points适合求解器无关表格/数组adapter，registered accessor适合提供CFD专用QoI API。
accessor必须只读取锁定证据，并显式声明dims、units、weights和missing policy。

## 9. 测试、示例与发布边界

项目对Dataset/DataArray、alignment、combine及多个backends有广泛测试。示例accessor显示领域扩展
无需修改核心。当前主分支要求Python 3.11+，基础依赖NumPy、pandas和packaging；这与仍需Python
3.10支持的产品基线存在版本约束。

## 10. 许可证与条款

Apache-2.0允许复用并提供专利条款。可选NetCDF/Zarr/Dask后端有各自依赖；直接集成前要选择与
产品Python版本一致的发布版，不能直接依赖当前main。

## 11. 优点

- 带名字的维度和坐标显著降低数组位置错配。
- `join="exact"`、combine测试及backend协议可形成可靠的多case数据层。
- NetCDF/Zarr能同时交付数值、坐标和metadata，比孤立CSV更适合N维CFD source data。

## 12. 缺点与风险

- attrs中的单位和来源没有强制语义，也可能在操作中丢失或被覆盖。
- 自动对齐和缺失值跳过若无显式策略，会掩盖case缺失和采样不一致。
- 不表达非结构网格拓扑、收敛证据或边界条件等CFD专属对象。

## 13. 迁移判定

**direct reuse**（分析数据层，可选/分阶段引入）。目标是承载多case QoI cube、坐标对齐和可复现
source data。适配条件是锁定维度词典、使用`join="exact"`默认策略、单位层和provenance层外置，并
选择兼容Python版本。收益高、集成成本中等；验证应覆盖坐标顺序变化、缺case、不同单位、不同
采样截面和NetCDF往返，而不是只测试数组shape。

## 14. P04 / Gate 5 对应关系

明确case/section/variable坐标可降低工况编号与聚合错配；但若允许默认outer alignment或`skipna`，
仍可能复现“缺失数据被包装成趋势”的失败。因此可比性gate必须先于任何combine/reduce。

## 15. 未验证项

未执行大型Dask/Zarr基准、第三方CFD backend和全部attrs保留组合，也未证明当前main可在Python
3.10运行。迁移结论限定为数据模型与受控对齐机制。
