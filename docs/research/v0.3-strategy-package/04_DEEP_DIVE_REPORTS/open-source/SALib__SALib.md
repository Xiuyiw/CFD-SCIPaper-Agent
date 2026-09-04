# SALib

## 1. 来源

- 候选ID：`SALib/SALib`
- 仓库：<https://github.com/SALib/SALib>
- 固定版本：`aa2c5545b3bfd0a982e9fad7625070a8ea340d38`
- 访问日期：2026-08-31；许可证：MIT（`LICENSE`）。
- **事实**来自该提交的代码、文档、测试与示例；**研究者推断**在迁移判定中单独说明。

## 2. 轨道与真实任务

覆盖`scientific-analysis`。SALib提供参数采样和Sobol等敏感性分析，真实输入是定义完整的参数问题、
与设计严格对应的模型输出，输出为敏感性指数及置信区间。它不能把任意已有CFD工况自动变成有效的
敏感性试验。

## 3. 实际代码或文档定位

- `src/SALib/util/problem.py::ProblemSpec`：保存problem、samples、results和analysis，并执行形状检查。
- `src/SALib/sample/sobol.py::sample`：按边界、变量数和可选分组生成Sobol设计。
- `src/SALib/analyze/sobol.py::analyze`：检查输出长度，计算一阶、总效应及可选二阶指数和置信区间。
- 示例：`examples/Problem/problem_spec.py`；测试：`tests/test_problem.py`、
  `tests/test_sobol.py`及seed相关测试。

## 4. 架构

sampling与analysis模块按方法拆分，`ProblemSpec`提供链式入口，将问题定义、样本、模型结果和分析结果
集中在一个对象中。它假设调用者提供满足对应采样设计的结果，科学有效性依赖实验设计而不是API本身。

## 5. 输入与输出

输入problem至少含变量名与bounds，可含groups；sample生成设计矩阵，调用方计算模型输出后再分析。
输出字典/结果对象包含敏感性指数和置信区间。示例明确指出结果驻留内存，未提供通用磁盘缓存或论文
source-data导出。

## 6. 科学边界

- **单位传播**：参数和输出为数值数组，单位不被强制保存或检查。
- **缺失值**：分析器不提供统一缺失值修复；非有限值或常数输出可能传播为无效指数。
- **来源**：`ProblemSpec`组织数组，但没有文件哈希、求解设置或claim来源链。
- **QoI**：结果数组可以是QoI，但其定义、统计窗口和守恒意义完全由调用方承担。
- **多case可比性**：只有同一有效采样设计且同一QoI定义的case才可分析；库不检查CFD边界一致性。
- **错误自动推断风险**：将普通参数扫描、缺点工况或不对应采样矩阵的结果送入分析，会产生形式完整但
  不可辩护的敏感性结论。

## 7. 状态与恢复

`ProblemSpec.sample()`通过链式采样会清除`_results`和`_analysis`；`set_samples()`及`samples` setter
只清除`_results`，不会清除已有`_analysis`。因此，手动替换samples可能留下与新设计不匹配的旧
analysis；产品外层状态管理必须在样本指纹变化时显式失效分析结果，并持久化case映射和QoI版本。

## 8. Skill、插件或适配器

适合做受控的`sensitivity`分析插件：只在样本设计、输入维度、输出长度、缺失值和case映射均通过后
启用。无法满足设计时应输出最低补充需求，而不是自动改用近似敏感性术语。

## 9. 测试、示例与发布边界

测试覆盖problem链、Sobol采样/分析、形状和seed；示例展示完整采样到分析链。它们不验证用户CFD
结果是否收敛或可比。当前`pyproject.toml`要求Python 3.10+，依赖NumPy 2、SciPy、Matplotlib和Pandas。

## 10. 许可证与条款

MIT允许复用。需要注意数值依赖版本与项目Python矩阵，并在文档中遵守敏感性方法的引用要求。

## 11. 优点

- 成熟的采样和敏感性算法，方法边界与输出结构明确。
- `ProblemSpec`把设计、结果和分析组织在同一对象中。
- 输出长度、置信水平和seed相关检查可形成fail-closed入口。

## 12. 缺点与风险

- 不处理单位、CFD来源、收敛或工况可比性。
- 内存式工作流不适合直接承载大型场数据。
- 最危险的误用是对非设计型离散工况套用全局敏感性结论。

## 13. 迁移判定

**direct reuse**（条件性可选分析引擎）。仅服务满足采样设计的标量QoI；调用前强制验证design-case
映射、单位、非有限值和QoI版本。预期收益中高、成本中等，主要风险是方法被越权用于任意成熟结果。
验证应包含正确设计、错序结果、缺case、常量输出和NaN的负面测试。

## 14. Internal regression relevance

其正向经验是“敏感性必须绑定明确设计与输出”；负向警示是不能把几个离散CFD工况的趋势包装为
全局敏感性。科学问题和证据成熟度应先于算法调用。

## 15. 未验证项

未运行全套算法测试，未比较各方法在小样本CFD成本下的适用性，也未验证分布式/磁盘后端。当前结论
仅支持受控标量敏感性插件，不支持默认自动分析。
