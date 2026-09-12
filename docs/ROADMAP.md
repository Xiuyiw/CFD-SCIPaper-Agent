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
| `v0.5.0` | Raw-table-linked quantitative writing and manuscript-scale figures, tables, equations and DOCX layout | Implemented locally with rendered examples and private trials; release preparation ongoing, not released |

The [v0.5.0 implementation plan](research/V0_5_IMPLEMENTATION_PLAN.md) combines P04 writing
lessons and the cross-domain cooling trial. It improves the existing host-assisted subsection
workflow, not an autonomous full-paper system. Completed private manuscript repairs are distinct
from product changes and new-task evaluation. Earlier release scopes and long-term goals remain.

## Product direction

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
