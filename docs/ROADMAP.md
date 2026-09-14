# CFD-Paper-Agent public roadmap

## Release principle

The repository is published early and improved in visible, evidence-backed increments. A public
version contains only capabilities that run and are tested at that tag. Longer-term targets remain
recorded here instead of being represented as already complete.

## Versioned delivery

| Version | Public deliverable | Status |
|---|---|---|
| `v0.1.0` | Installable CLI, local project state, resumable inspection, and author-supplied topic ranking | Released 2026-08-30 |
| `v0.2.0` | Automatic generation of 2–4 evidence-bounded topic candidates from mature structured records | Released 2026-08-31 |
| `v0.3.0` | Structured comparison qualification, discrete QoI analysis, one reproducible figure, and one numerically backlinked results paragraph | Released 2026-09-04 |
| `v0.3.1` | Cross-platform CI and public-documentation maintenance for the v0.3 workflow | Released |
| `v0.4.0` | Figure-grounded host writing, multi-evidence subsections, DOCX and review packets | Delivered; see release tag |
| `v0.5.0` | Raw-table-linked quantitative writing and manuscript-scale figures, tables, equations and DOCX layout | Delivered; see the v0.5.0 release tag and notes |
| `v0.6.0` | Existing exported materials to host-assisted scientific analysis selection and the subsection workflow | Released; see the v0.6.0 release tag and notes |
| `v0.7.0` | Multi-section manuscript workspace, portable continued editing and external drawing-task integration | Released; see release tag |
| `v0.8.0` | Shared literature, cross-section evidence bindings, targeted change reports and optional numeric CSL formatting | Released; see the v0.8.0 notes and release tag |
| `v0.9.0` | Real-material whole-manuscript trial, bounded review and selected-feedback editing | Delivered scope; see v0.9.0 release notes and the verified release tag |
| `v0.10.0` | Explicit area/volume-weighted evidence, spatial-reasoning guidance, portable field/Word example and aligned numeric table headers | Release preparation; see v0.10.0 notes |

The [v0.5.0 implementation plan](research/V0_5_IMPLEMENTATION_PLAN.md) combines P04 writing
lessons and the cross-domain cooling trial. It improves the existing host-assisted subsection
workflow, not an autonomous full-paper system. Completed private manuscript repairs are distinct
from product changes and new-task evaluation. Earlier release scopes and long-term goals remain.

The [v0.6 development plan](research/V0_6_DEVELOPMENT_PLAN.md) addressed the manual
input-preparation burden: inspect existing tables and definitions, propose meaningful analyses,
and connect the author's choice to the existing calculation, figure and DOCX path. This chain is
implemented, with a recorded synthetic example and a known cooling-case regression.
It does not promise arbitrary native-solver extraction or autonomous full papers; new cross-domain
validation remains separate from software release checks. The [v0.6.0 notes](releases/v0.6.0.md)
describe the delivered inputs, presentation choices and remaining limits.

## Approved post-v0.6 writing direction

The [full-writing development proposal](research/POST_V060_WRITING_PLAN.md) reviews the actual
subsection capability, historical P04 and cooling-trial lessons, and the remaining manuscript gaps.
The [figure-skill integration study](research/FIGURE_SKILL_INTEGRATION_STUDY.md) identifies reusable
editable-diagram and data-figure workflows. The v0.7 candidate includes a portable drawing-task
adapter, Methods/multi-section assembly, global references and continued editing after relocation.
These features have shipped; v0.8 adds shared literature and source-aware manuscript updates.

The approved sequence is a manuscript workspace plus figure integration, literature-supported
whole-paper writing, then real manuscript trials and bounded pre-submission review. Version targets
v0.8's software workflow is delivered, while original scientific quality on unfamiliar complete
papers remains to be demonstrated. The v0.9 proposal prioritizes a real first draft, one bounded
whole-manuscript review and targeted improvement. It reuses existing section packets and change
reports rather than introducing another governance framework. See the final section of the
[development proposal](research/POST_V060_WRITING_PLAN.md) for the stage assessment and scope.
The [first-batch specification](research/V0_9_FIRST_BATCH_SPEC.md) defines real-material input
preparation and whole-paper review delivery without expanding the solver or submission scope.
Native solver platforms and submission automation are not prerequisites for this writing route.

## Product direction

The current release-preparation increment is defined in the
[v0.10 scientific-writing plan](research/V0_10_SCIENTIFIC_WRITING_PLAN.md): explicit spatial
weighting connected to diagnostic selection, substantive host writing, complementary figures
and actual Word presentation. Weighted mean, population SD and measure sum now bind to prose and
Word tables, including the distinction between absolute-temperature and temperature-difference
units. Host skills connect field extent and location with summary diagnostics; numeric table
headers now follow their columns' alignment.

The [public spatial example](../examples/spatial-diagnostics/README.md) carries analytical source
facets, editable four-format artwork and a recorded guided host draft through relocation and Word
export. Local transfer and rendered-page checks are complete; final regression, supported-platform
CI and release integration remain release-preparation work. Recorded replay is not a new model
invocation, an unfamiliar-project writing benchmark or physical validation. See the
[v0.10.0 notes](releases/v0.10.0.md) for the bounded release scope.

Development follows the path from mature CFD results to an author-approved scientific paper:

1. solver-neutral and solver-assisted result intake;
2. scientific comparison, QoI, trend, uncertainty, and field analysis;
3. publication figures and linked scientific writing;
4. full paper structure and document export;
5. pre-submission review and event-driven revision after real reviewer comments;
6. heterogeneous validation across flow, heat-transfer, and multiphase projects.

Further releases will narrow this list to one primary user bottleneck before implementation. This
keeps each public increment useful and testable without presenting the long-term system as already
complete.

## Long-term maturity gates

| Gate | Deliverable | Promotion rule |
|---|---|---|
| 0 | Product contract, isolated repository, legacy boundary | Public interfaces frozen and no private assets tracked |
| 1 | Installable CLI and resumable project | New project initializes and resumes offline |
| 2 | SQLite/FTS hybrid retrieval and context packets | Fresh evidence is retrieved; stale evidence is excluded |
| 3 | Scientific core and reference adapters | Known private-regression scientific failures are blocked |
| 4 | Analysis, figures, writing and export | Claims remain evidence-linked and artifacts are real |
| 5 | Pre-submission review and event-driven revision | No planned or synthetic change is reported as complete |
| 6 | Three heterogeneous real-project validations | Zero hard scientific and cross-document errors |
| 7 | Stable public package | CI, docs, examples, license and release checks pass |

These maturity gates describe the route to a broadly reusable product. They do not imply that the
current release already supports arbitrary solver files, complete manuscripts, or unattended
research decisions.
