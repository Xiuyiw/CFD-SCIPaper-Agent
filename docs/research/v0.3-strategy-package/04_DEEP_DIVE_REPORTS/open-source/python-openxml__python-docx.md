# python-docx

## 1. 来源

- 候选ID：`python-openxml/python-docx`
- 仓库：<https://github.com/python-openxml/python-docx>
- 固定版本：`e45454602b53e8e572b179ccf1c91093ec9f4ed7`
- 访问日期：2026-09-01；许可证：MIT（`LICENSE`）。

## 2. 轨道与真实任务

覆盖`writing`与`quality-export`。python-docx读取、创建和更新WordprocessingML `.docx`，适合受控装配
段落、样式、图片、表格和分节；它不是排版引擎、引用管理器或科学写作Agent。

## 3. 实际代码或文档定位

- `src/docx/api.py::Document`：打开已有DOCX或创建默认文档，并返回document对象。
- `src/docx/document.py::Document`：`add_heading/add_paragraph/add_picture/add_section/add_table/add_comment/save`。
- `src/docx/parts/document.py::DocumentPart.save/comments`：保存package并管理comments part关系。
- `Document.iter_inner_content`和`paragraphs/tables`文档说明：修订标记中的段落可能不出现在普通集合。
- BDD示例：`features/doc-add-picture.feature`、`doc-add-table.feature`、`doc-add-section.feature`、
  `doc-add-comment.feature`；单元测试：`tests/test_document.py`。
- `docs/user/quickstart.rst`及README示例真实创建、保存并重新读取`.docx`。

## 4. 架构

高级Document/Paragraph/Table/Run对象包装底层OOXML element和package part；图片、comments等通过OPC
relationship接入文档。它允许在模板文档上进行局部操作，比直接拼XML安全，但不覆盖Word全部特性。

## 5. 输入与输出

输入为新建文档或现有DOCX、文本、样式、图片、表格数据和分节参数；输出为真实可编辑DOCX。
图片和表格是真正嵌入对象，不是Markdown链接。它不直接输出LaTeX/PDF，也不渲染页面供视觉QA。

## 6. 科学边界

库只保证OOXML操作，不检查数字、单位、case ID、引用或claim证据。表图嵌入前仍需source-data和
FigureContract。保存已有文档时，未被高级API理解的域/修订/扩展是否保真必须用OOXML diff验证。

## 7. 状态与恢复

DOCX本身是持久输出，可重新打开继续编辑；没有任务checkpoint、版本陈旧检测或作者审批状态。
不能把“文件能再次打开”当作项目恢复机制。

## 8. Skill、插件或适配器

它适合作为`DocxExporter`底层依赖：模板加载、样式映射、段落/表/图装配和低风险修改。不是Skill系统，
也没有触发、渐进披露、资源依赖或失败回退协议；这些应由CFD-Paper-Agent adapter定义。

## 9. 测试、示例与发布边界

单元和BDD tests覆盖文档、段落、图片、表格、section、style、comments等大量行为，证明真实DOCX写入。
测试不等于Microsoft Word/LibreOffice逐页排版一致，也未覆盖所有域代码、动态引文、OMML公式和修订痕迹。

## 10. 许可证与条款

MIT允许直接依赖和分发。其运行依赖轻于Quarto完整工具链，但复杂PDF输出仍需Word/LibreOffice等外部组件。

## 11. 优点

- Python原生、依赖相对轻，可直接生成含图片、表格、样式和分节的真实DOCX。
- 现有文档局部编辑和模板驱动适合Windows科研工作流。
- OOXML对象模型和测试比手工zip/XML改写更稳健。

## 12. 缺点与风险

- 不原生管理学术引用、BibTeX/CSL、Zotero动态域或LaTeX。
- 不渲染页面，无法发现裁切、分页和字体替换。
- 普通paragraph/table集合会忽略部分修订标记内容；复杂字段往返存在保真风险。

## 13. 迁移判定

**direct reuse**。作为轻量DOCX exporter和模板/局部装配后端，强制使用模板、样式白名单、嵌入图表
验证、ZIP/OOXML结构检查及LibreOffice/Word渲染QA。对已有含Zotero/修订的文档默认只读或限定操作；
复杂引用优先Quarto/BibTeX生成，不能手改编号。

## 14. P04 / Gate 5 对应关系

P04的Word版本混淆和字段保真问题说明，python-docx只能做确定性小范围装配，不能无差别重写整稿。
Gate 5则说明真实DOCX交付必须位于科学门之后，不能把文件生成当作结论批准。

## 15. 未验证项

未在固定Word/LibreOffice版本渲染样例，未验证Zotero域、OMML、Track Changes和期刊模板往返。正式集成
应以公开fixture做结构hash、媒体数量、样式、公式/域保留和逐页渲染回归。
