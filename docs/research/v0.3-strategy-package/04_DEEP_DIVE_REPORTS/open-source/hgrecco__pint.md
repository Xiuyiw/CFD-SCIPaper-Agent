# Pint

## 1. 来源

- 候选ID：`hgrecco/pint`
- 仓库：<https://github.com/hgrecco/pint>
- 固定版本：`6fc05335ef2820736efec7c5b9d55433acfb6aad`
- 访问日期：2026-08-31；许可证：BSD-3-Clause（`LICENSE`）。
- **事实**来自该提交的代码、文档、测试与示例；**研究者推断**仅出现在迁移判定中。

## 2. 轨道与真实任务

覆盖`scientific-analysis`。Pint把数值与单位绑定为`Quantity`，支持单位转换、量纲检查和NumPy
运算，适合作为QoI计算前后的量纲防线。它不理解CFD case、控制体、边界条件、采样定义或论文claim。

## 3. 实际代码或文档定位

- `pint/registry.py::UnitRegistry`及`pint/facets/plain/registry.py`：定义、加载和解析单位。
- `pint/facets/plain/quantity.py::PlainQuantity.to`与`ito`：显式返回或原位单位转换；不相容量纲抛出
  `DimensionalityError`。
- `pint/facets/numpy/quantity.py::__array_ufunc__`和`__array_function__`：将单位语义传播到受支持的
  NumPy操作。
- 文档示例：`docs/user/quantity-to.rst`；测试：`pint/testsuite/test_quantity.py`、
  `pint/testsuite/test_unit.py`。

## 4. 架构

`UnitRegistry`维护单位定义和转换关系，`Quantity`组合magnitude与unit；多个facet叠加普通、NumPy、
measurement等行为。该结构把量纲规则集中在计算对象中，比字段名后缀可靠，但领域含义仍需调用方锁定。

## 5. 输入与输出

输入可以是数值、数组和可解析单位表达式；输出仍为带单位`Quantity`，可转换为指定单位或基础单位。
显式转换能保留单位，直接交给不识别Pint的数组接口则可能剥离单位并触发警告。项目不保存输入文件、
case ID或source-data表。

## 6. 科学边界

- **单位传播**：是核心能力；相同量纲可转换，不相容量纲默认失败。
- **缺失值**：NaN可存在于magnitude中，但Pint不判断缺失是否允许，也不补齐样本。
- **来源**：单位定义可追溯到registry，但数据文件与提取步骤没有自动来源链。
- **QoI**：可保护QoI公式的量纲；不能决定QoI控制体、归一化基准或物理意义。
- **多case可比性**：只能判量纲和转换，不能判边界条件、采样面或统计窗口是否一致。
- **错误自动推断风险**：量纲正确不等于物理定义正确；错误的面积、参考态或平均方式仍会得到合法单位。

## 7. 状态与恢复

registry定义和量值可被调用层序列化，但项目没有论文阶段、输入哈希或stale状态。恢复时应固定单位定义
版本，并把原始值、原始单位、规范单位和转换记录保存在CFD-Paper-Agent数据对象中。

## 8. Skill、插件或适配器

可将`UnitRegistry`封装为统一单位服务，并在适配器出口立即把求解器单位转换为产品规范单位。此服务
只能拒绝量纲错误，不能替代QoI审查或证据成熟度判断。

## 9. 测试、示例与发布边界

测试覆盖转换、量纲错误、数组运算和NaN行为；示例展示`to()`/`ito()`。这些测试证明单位代数，不证明
CFD提取值或公式正确。当前主分支`pyproject.toml`要求Python 3.12+，与产品Python 3.10--3.12目标
存在版本选择约束，不能直接无条件跟随主分支。

## 10. 许可证与条款

BSD-3-Clause允许复用。集成时必须选择与目标Python矩阵兼容的发布版本，并保留许可证文本。

## 11. 优点

- 单位转换与`DimensionalityError`能低成本阻断常见硬错误。
- NumPy集成适合标量与数组QoI计算。
- registry允许项目定义工程单位和统一规范输出。

## 12. 缺点与风险

- 不提供缺失值政策、来源记录、case可比性或科学公式验证。
- 第三方库若强制转为`ndarray`可能丢单位。
- 当前开发分支Python下限高于产品最低版本，需要固定兼容发布版。

## 13. 迁移判定

**direct reuse**（兼容版本的可选/核心依赖）。用于单位解析、规范化和量纲检查；外层仍须保存来源、
缺失状态、case比较条件和QoI定义。预期收益高、集成成本低至中等；验证应包含转换、量纲冲突、NaN、
数组接口剥离和序列化回放。

## 14. Internal regression relevance

可迁移的是“先统一量纲再比较和写作”的正向经验；不可迁移的假设是把量纲通过当作科学批准。
产品仍应在单位门之后检查工况可比性、采样定义和物理闭合。

## 15. 未验证项

未运行完整测试矩阵，未评估所有NumPy/第三方函数的单位传播，也未选定支持Python 3.10的具体Pint
发布版本。这些未验证项必须在依赖锁定阶段闭合。
