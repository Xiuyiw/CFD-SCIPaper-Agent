# CFD-Paper-Agent public roadmap

## Release principle

The repository is published early and improved in visible, evidence-backed increments. A public
version contains only capabilities that run and are tested at that tag. Longer-term targets remain
recorded here instead of being represented as already complete.

## Versioned delivery

| Version | Public deliverable | Release condition |
|---|---|---|
| `v0.1.0` | Initial Public Preview: installable CLI, local project state, resumable inspection, and author-supplied topic ranking | Released 2026-08-30 |
| `v0.2.0` | Automatic generation of 2–4 evidence-bounded topic candidates from mature structured records | Public positive example, fail-closed private challenge replays, CI, package, and release smoke pass |
| `v0.3.0` | Paused; no active specification, branch, or implementation | Development resumes only after explicit author authorization |

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
| 7 | Stable public package | CI, docs, examples, license and release audit pass |

The versioned roadmap changes when functionality becomes public; it does not weaken the maturity
gates. Development pauses after v0.2.0. Longer-term gates remain architectural context rather than
an active backlog, and no v0.3.0 work begins without explicit author authorization.
