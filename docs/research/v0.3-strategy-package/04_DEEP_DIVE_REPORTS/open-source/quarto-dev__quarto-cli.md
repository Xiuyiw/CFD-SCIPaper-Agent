# Quarto

## 1. 来源

- 候选ID：`quarto-dev/quarto-cli`
- 仓库：<https://github.com/quarto-dev/quarto-cli>
- 固定版本：`eb126f9811981e59e8165d3da9641d92c77b9e3e`
- 访问日期：2026-09-01；Quarto源码主许可证为MIT，完整分发依赖条款见`COPYING.md`。

## 2. 轨道与真实任务

覆盖`writing`、`figures`和`quality-export`。Quarto把QMD/Markdown、notebook、引用、图表和metadata
交给执行引擎与Pandoc，生成真实HTML、DOCX、LaTeX/PDF、JATS等出版文件。它是渲染后端，不是
论文科学写作者。

## 3. 实际代码或文档定位

- `src/command/render/render.ts::renderPandoc`：合并执行结果、includes和Pandoc参数，调用`runPandoc`，
  处理资源及最终输出。
- `src/format/docx/format-docx.ts::docxFormat`：注册MS Word/docx格式和格式资源。
- `src/project/types/manuscript/manuscript-render.ts::manuscriptRenderer`：编排文章、notebook、JATS/HTML
  等稿件组成部分并收集render completion。
- `src/command/render/freeze.ts`：冻结计算输出相关逻辑；`src/project/project-cites.ts`和`src/core/csl.ts`
  支持引用/CSL路径。
- 测试：`tests/smoke/render/render-docx.test.ts`、`tests/smoke/manuscript/render-manuscript.test.ts`、
  `tests/smoke/crossref/docx.test.ts`、`tests/smoke/render/render-freeze.test.ts`。
- 示例：`tests/docs/manuscript/qmd-full/index.qmd`包含metadata、bibliography、公式、图、表、交叉引用和嵌入notebook。

## 4. 架构

输入先经计算引擎得到Markdown和资源，再由format和Pandoc filters转换；manuscript project在项目层
组合主文和notebook；DOCX、TeX/PDF等由格式recipe完成。引用、图表和交叉引用属于渲染语法，
不是后期字符串替换。

## 5. 输入与输出

输入为QMD/Markdown、YAML metadata、BibTeX/CSL、图片、notebook和可选reference DOCX；输出为真实
DOCX、TeX/PDF、JATS、HTML及资源目录。示例证明图、表、公式和引用能进入文稿，而非仅生成Markdown。

## 6. 科学边界

Quarto能保证引用key、交叉引用和渲染结构，不验证数字、单位、CFD claim或文献支持强度。执行notebook
可能改变结果；CFD-Paper-Agent应默认消费锁定source data并显式选择是否执行，避免渲染时隐式重算。
reference-doc控制样式不等于复杂期刊模板完全保真。

## 7. 状态与恢复

freeze/cache可复用计算输出，项目结构支持分文件重渲染；但它不是业务阶段checkpoint。输入、环境和
扩展变化仍需外部manifest判断陈旧性，不能把`freeze`当科学批准。

## 8. Skill、插件或适配器

Quarto有extension/format/filter机制，适合作为export adapter；它不是Agent Skill系统。适配器应探测
CLI版本、Pandoc/TeX能力和reference-doc，失败时回退到python-docx或保留QMD/LaTeX源，而不是隐藏失败。

## 9. 测试、示例与发布边界

仓库有真实DOCX、crossref、manuscript、JATS、PDF和freeze smoke tests，宣传的多格式输出有实现支撑。
测试规模和工具链较大；V0.3应通过一个公开fixture验证图、表、公式、citation和DOCX/PDF，而不复制
Quarto自身测试体系。

## 10. 许可证与条款

核心MIT；二进制分发包含Pandoc、Deno、TeX相关及其它第三方组件，应按`COPYING.md`处理。推荐调用
用户安装的Quarto CLI，不复制其源码或打包整个工具链。

## 11. 优点

- 提供真正DOCX/LaTeX/PDF/JATS输出及图表、公式、引用、交叉引用。
- manuscript project和notebook嵌入适合可复现论文源。
- reference-doc和CSL使投稿样式可以配置，而不是硬编码Word XML。

## 12. 缺点与风险

- 安装体积和依赖较重，TeX/Pandoc/extension失败诊断复杂。
- 渲染器不会审查科研证据；漂亮文件仍可能包含错误claim。
- DOCX复杂域、期刊特殊版式和已有人工Word字段的往返保真需单独验证。

## 13. 迁移判定

**direct reuse**（外部可选export backend）。通过CLI adapter调用，不复制实现；先生成受控QMD、BibTeX、
图片和source-data，再渲染DOCX/LaTeX/PDF。安装缺失时给出明确最小操作，并回退到python-docx或源文件。
在科学证据冻结后才允许export。

## 14. Internal regression relevance

`authorized internal positive regression` 表明最终交付必须有真实 DOCX/PDF 和逐页 QA；Quarto 可
减少手工装配，但不能替代 Word 字段/视觉终审。`authorized internal negative scientific-gate regression`
表明 export 成功不得被当作科学门通过，最终文件必须来自已批准 claims 和图件。

## 15. 未验证项

未构建Quarto二进制、未执行DOCX smoke、未测指定Energy模板/Zotero动态域或复杂修订痕迹。迁移前须用
公开脱敏fixture验证reference-doc、公式、图表、citation和PDF/DOCX一致性。
