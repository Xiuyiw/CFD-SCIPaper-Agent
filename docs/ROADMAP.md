# CFD-Paper-Agent public roadmap

## Release principle

The repository is published early and improved in visible, evidence-backed increments. A public
version contains only capabilities that run and are tested at that tag. Longer-term targets remain
recorded here instead of being represented as already complete.

## Versioned delivery

| Version | Public deliverable | Release condition |
|---|---|---|
| `v0.1.0` | Initial Public Preview: installable CLI, local project state, resumable inspection, author-supplied topic ranking, architecture and tests | Fresh-clone Quickstart, public example, CI, privacy scan and honest capability matrix pass |
| `v0.2.0` | Automatic generation of 2–4 evidence-bounded topic candidates | Generic private-regression checks pass; author review and approval remain external |
| `v0.3.0` | Scientific analysis and reproducible figure-contract vertical slice | Units, comparability, QoI, trends, source data, scripts and figure QA close one public example |
| `v0.4.0` | Evidence-linked paper spine and section writing | Claim-evidence and literature-role mapping produce a bounded manuscript section and external-review package |
| `v0.5.0+` | Review, export, adapters and broader project support | Each capability passes its public contract and private regression without overclaiming support |
| `v1.0.0` | Stable evidence-to-paper workflow | Three heterogeneous real projects, at least two data/solver routes and zero hard scientific/cross-document errors |

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
gates. A failed validation becomes a regression fixture and returns the affected subsystem to
implementation.
