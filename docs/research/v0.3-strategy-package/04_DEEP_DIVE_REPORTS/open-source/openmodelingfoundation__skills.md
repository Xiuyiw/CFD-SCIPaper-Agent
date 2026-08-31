# OMF Skills

## 1. 来源

- 候选ID：`openmodelingfoundation/skills`
- 仓库：<https://github.com/openmodelingfoundation/skills>
- 固定版本：`f2a7fd5413f0035af6a83e074cbbf3fad28bb6c5`
- 访问日期：2026-09-01；许可证：MIT（`LICENSE`）；README明确状态为Alpha。

## 2. 轨道与真实任务

覆盖`skills`、`scientific-analysis`和`quality-export`。该仓库把计算建模方法、实现、FAIR、HPC、
文档和同行评审知识封装成Agent Skills，目标是让通用编码Agent按社区方法执行建模工作。

## 3. 实际代码或文档定位

- `docs/SKILL-TEMPLATE.md`：规定frontmatter、触发description、inputs、步骤、gotchas、资源/脚本和示例。
- `skills/peer-review/SKILL.md`：真实Skill，明确何时/何时不触发、输入、步骤、评分、输出和资源。
- `skills/peer-review/evals.json`：正向、反向及adversarial触发/行为样例。
- `scripts/validate_individual_skills.py`：检查frontmatter、目录名、description、license、行数、eval数量、
  路径和gotcha。
- `evals/schema/schema.json`、`scripts/validate_evals_schema.py`和`validate_cross_skills.py`：
  eval结构和跨Skill边界检查。
- `skills/omfa/references/guidance/*`及`assets/*`：按需载入的深层方法和模板。
- 示例：`skills/peer-review/SKILL.md`末尾以公开模型仓库输入和结构化评审报告输出展示调用结果。

## 4. 架构

每个Skill以短`SKILL.md`作为入口，深层知识放在`references/`，输出骨架放在`assets/`，必要自动化放
在`scripts/`，触发和不触发行为放在`evals.json`。这是清晰的渐进披露包结构；宿主Agent负责发现和
执行Skill，仓库自身不是runtime。

## 5. 输入与输出

输入由各Skill声明，输出通常为Markdown研究工件、检查表、模板或代码计划。它不统一生成DOCX、
LaTeX或嵌入图表；是否得到真实文件取决于Skill和宿主能力。

## 6. 科学边界

多个Skill明确“证据不足则标记、不发明科学承诺”，且同行评审Skill把科学新颖性/结论正确性排除
在软件质量审查之外，边界诚实。另一方面，Skill文本仍是指令；方法是否被正确执行，需要eval和
真实项目回放，不能因结构规范就假定科学有效。

## 7. 状态与恢复

仓库定义工作方法和工件文件，不实现任务状态数据库、断点恢复或输入版本失效。恢复由宿主Agent和
项目文件承担。

## 8. Skill、插件或适配器

这是本轨道最成熟的Skill包样例：元数据支持发现，description包含触发短语和期望输出；正文规定
使用/禁用边界；references/assets/scripts实现渐进披露；evals覆盖正反触发和越界；validator提供
最低结构测试。依赖仅以compatibility文字描述，尚无机器可解析安装/回退契约。

## 9. 测试、示例与发布边界

结构validator和JSON schema能发现缺文件、坏frontmatter、触发样例不足和绝对路径；evals记录期望
行为。README同时诚实标注Alpha，路线图中的统计、校准、可视化等不能视为已实现。eval JSON本身
不等于已在多个Agent上自动执行通过。

## 10. 许可证与条款

MIT允许复用结构和内容；若迁移具体科学方法，应保留来源并检查引用材料条款。Skills CLI是外部工具。

## 11. 优点

- 渐进披露、资源模板、脚本和gotcha共同避免单个超长提示词。
- 正/负/adversarial触发测试能约束过度触发与scope creep。
- Alpha状态和未实现路线图公开，宣传与当前仓库边界基本一致。

## 12. 缺点与风险

- 缺少统一机器可解析的依赖、版本、能力检测和失败回退字段。
- eval多为期望描述，宿主间实际行为和自动评分仍需验证。
- 通用建模Skill不能替代CFD求解器适配、QoI和论文证据契约。

## 13. 迁移判定

**reimplement**。把CFD-Paper-Agent的专用能力组织为同类Skill包：精确触发、禁用边界、输入/输出、
渐进references、assets/scripts、gotcha和正反/对抗eval；另补机器可解析依赖、能力探测、回退和
真实项目测试。不要直接复制与当前产品无关的OMF方法全文。

## 14. Internal regression relevance

`authorized internal positive regression` 适合转为 gotchas、templates 和回归 eval，而不是继续堆在
全局规则中；`authorized internal negative scientific-gate regression` 适合成为 adversarial eval，
验证 Skill 在证据不足、工况不可比、工具缺失时能停止或降级，而非声称完成。

## 15. 未验证项

未通过各支持宿主逐一运行全部eval，未执行路线图中未实现能力，也未验证Skills CLI安装。结论只把
其作为Skill工程规范参照，不把Alpha内容当作成熟科学实现。
