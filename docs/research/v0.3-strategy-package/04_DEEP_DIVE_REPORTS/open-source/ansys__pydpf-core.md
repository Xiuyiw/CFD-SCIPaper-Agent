# PyDPF-Core

## 1. 来源

- 候选ID：`ansys/pydpf-core`
- 仓库：<https://github.com/ansys/pydpf-core>
- 固定版本：`3a2eaf2b4ccd84e4f18e43e309df3f21ccfbff1f`
- 访问日期：2026-08-31；客户端许可证：MIT（`LICENSE`）。
- **事实**基于该提交；关于CFD-Paper-Agent的采用建议属于**研究者推断**。

## 2. 轨道与真实任务

覆盖`cfd-adapters`与`scientific-analysis`。用户以结果文件或`DataSources`创建`Model`，浏览mesh/
result metadata，再把operators连接成`Workflow`并求值。输入涵盖Ansys结果及部分CSV/HDF5/VTK；
输出为带scoping、location和unit的`Field`/`FieldsContainer`。它不负责论文选题或claim审批。

## 3. 实际代码或文档定位

- `src/ansys/dpf/core/model.py::Model`、`Metadata`：结果源、网格、时间/频率与可用结果入口。
- `src/ansys/dpf/core/data_sources.py::DataSources`：结果文件及key的来源描述。
- `src/ansys/dpf/core/field.py::Field`、`field_definition.py::FieldDefinition`：数据、scoping、
  location和unit。
- `src/ansys/dpf/core/fields_container.py::FieldsContainer`：按label组织多个field。
- `src/ansys/dpf/core/workflow.py::Workflow.connect/get_output/set_output_name`：可组合operator图。
- 示例：`doc/sphinx_gallery_examples/12-fluids/00-fluids_model.py`；测试：`tests/test_model.py`、
  `tests/test_field.py`、`tests/test_workflow.py`、`tests/test_unit_systems.py`。

## 4. 架构

Python客户端通过gRPC连接DPF server。`Model`提供metadata和动态results，operator以typed pins连接，
`Workflow`暴露命名输入/输出；field把数值、实体scoping、位置和单位封装为自描述对象。这个设计
把“读取、范围选择、变换、求值”组织为可复用图，但真正计算能力依赖DPF server及版本。

## 5. 输入与输出

`DataSources`保留结果文件与角色；Fluent/CFX示例通过`MeshInfo`读取body/cell/face zone及名称，
通过`ResultInfo`读取变量位置、zone和phase限定。结果输出仍在DPF对象中，可绘图或继续连接operator。
项目未提供论文source-data/claim对象；这些必须由外层导出并绑定来源。

## 6. 科学边界

- **单位传播**：`Field.unit`、`FieldDefinition.unit`与`ResultInfo.unit_system`提供明确单位，比裸数组
  更接近科学证据对象；单位转换可由`operators/math/unit_convert.py`执行。
- **缺失值**：不存在的结果、错误pin或不兼容server会失败，但未观察到面向论文的统一NaN/缺失
  QoI政策。
- **来源**：`DataSources`绑定文件角色，优于仅保留数组；仍需外层保存文件版本/哈希和提取请求。
- **QoI**：operator/workflow适合封装明确scoping的积分、平均与变换；并不自动判断物理定义是否正确。
- **多case可比性**：`FieldsContainer` labels适合组织时间、zone和phase，却没有跨算例边界条件、网格、
  参考值一致性的审批。
- **错误自动推断风险**：可用结果和单位齐全仍不等于结果收敛或可比较；operator链可能技术上成功但
  采用了错误zone、location或averaging定义。

## 7. 状态与恢复

Workflow可命名输入/输出并支持序列化相关operators；server端执行允许大数据就近处理。跨电脑恢复
仍受server版本、Ansys安装、结果文件位置和兼容性约束，不是独立的项目状态系统。

## 8. Skill、插件或适配器

`Operator`和`Workflow`是可组合适配单元；Python operator插件示例位于
`doc/source/examples/07-python-operators/plugins/`。这种“typed scientific operation”比长提示词更适合
QoI技能后端，但插件不能绕过EvidenceRecord与作者检查点。

## 9. 测试、示例与发布边界

仓库含model/field/workflow/unit和远程workflow测试；流体示例实际读取Fluent与CFX metadata。
README明确PyDPF-Core要求可用DPF server；绘图还需PyVista。测试覆盖客户端契约，不证明任意Ansys
版本或任意CFD变量均受支持。

## 10. 许可证与条款

Python客户端为MIT，但运行需要兼容的Ansys版本或`ansys-dpf-server`。因此不能把MIT客户端误解为
完整计算栈无供应商约束，也不能将DPF作为通用核心的强制依赖。

## 11. 优点

- field把值、单位、空间位置和scoping放在同一对象中。
- DataSources、MeshInfo和ResultInfo为只读case inventory提供强参考。
- operator/workflow把QoI提取表达为可组合、可测试、可复用的数据流。

## 12. 缺点与风险

- server与版本兼容构成明显供应商和部署边界。
- 缺少跨case科学可比性、claim ceiling和论文source-data交付。
- 动态结果及丰富operator目录可能诱发“存在算子即适合本研究”的错误自动选择。

## 13. 迁移判定

**idea-only**。借鉴“来源对象 + 自描述field + typed operator graph + scoped output”的结构，重新实现
求解器无关的轻量QoI pipeline；Ansys用户可在后续以可选adapter调用PyDPF-Core。预期收益高，核心
重实现成本中等；风险是复制过重远程框架或把server可用性当成科学有效性。验证应使用同一QoI在
CSV/VTK和DPF adapter间的单位、location、zone及数值一致性测试。

## 14. Internal regression relevance

自描述field与scoping能减少“聚合定义不清”的失败；但没有跨case gate时仍会放行不可比结果。
因此只迁移数据对象和operator契约，不迁移“workflow成功即证据成熟”的隐含假设。

## 15. 未验证项

未启动DPF server，未运行Fluent/CFX示例，也未验证商业Ansys版本矩阵和大规模远程性能。报告不据此
声称已具备可直接使用的通用CFD提取器。
