# Architecture overview

CFD-Paper-Agent keeps project state local and separates file discovery from scientific evidence
qualification. The structured-record workflow connects mature CFD evidence to a bounded
research direction, an approved quantity of interest (QoI), discrete analysis and a figure.
The declared-evidence workflow also supports host-written multi-section manuscripts,
shared literature, numerical bindings and targeted change reports.

`write --artifact results-section` also accepts a portable declared evidence
package with existing figures. The host AI writes the subsection; the CLI resolves
tokens, recomputes declared CSV results, checks declared coverage, embeds figures,
tables and structured equations in DOCX, and separates review notes.
This additive route does not confer the qualification status of the structured QoI
pipeline on author-supplied evidence.

```mermaid
flowchart LR
    A[Mature CFD results or neutral exports] --> B[inspect]
    B --> C[Local source index and stale state]
    C --> D[Structured cases, observations, and checks]
    D --> E[qualify comparison and candidate QoI]
    E --> F[plan 2–4 provisional topics]
    F --> G{Author selects topic}
    G --> H{Author locks QoI}
    H --> I[analyze observed discrete cases]
    I --> J{Author accepts figure contract}
    J --> K[figure package]
    K --> L[write results paragraph]
    L --> M{Author approves final artifact}
```

`inspect` records relative source locations and detects changed inputs. It does not infer solver
semantics or treat file presence as scientific validation.

`qualify` checks the declared comparison, case membership, units, source locations, convergence,
conservation, verification, validation, and proposed QoI. The current public interface expects
structured records and scalar observations rather than arbitrary native solver files.

`plan` ranks an author candidate file or generates two to four provisional directions from mature
records. Offline generation is deterministic. Optional provider refinement may improve bounded
wording but cannot add evidence, alter numerical relations, or approve a topic.

After author selection, the QoI is locked before `analyze` reads the declared discrete sequence.
The analysis records trends and claim ceilings without interpolation, smoothing, or continuous
optimization. `figure` packages source data, a runnable plotting script, editable and preview
graphics, a caption, and focused QA results. `write` produces one results paragraph whose numbers
link back to the analyzed records.

## Local components

| Component | Responsibility | Boundary |
|---|---|---|
| Typer CLI | Coordinate the public workflow and report unavailable commands clearly | No unattended research decisions |
| Project indexer | Discover files and track changed sources | No scientific evidence qualification |
| SQLite store | Persist project state, sources, records, approvals, and checkpoints | Project-local state |
| Topic planner | Propose and rank bounded research directions | Author selects the direction |
| Scientific qualifier | Check comparability, evidence, QoI definition, and reporting limits | Missing evidence remains missing |
| QoI analyzer | Evaluate declared scalar sequences and allowable trends | Observed discrete cases only |
| Figure pipeline | Produce evidence-linked figures and finite complementary panels | No undeclared transformation or arbitrary native field interpretation |
| Table evidence | Calculate declared CSV/NPZ populations, partitions and supported spatial/temporal diagnostics; resolve current numeric tokens | No automatic choice of scientific operator or missing-value inference |
| Writing pipeline | Assemble host-authored sections and multi-section manuscripts with shared evidence and literature | No autonomous claim expansion or guarantee of submission readiness |
| Subsection export | Place figures, native tables and structured mathematics in editable DOCX | Finite elements and configurable layouts, not an arbitrary journal template engine |

## Research workspace (v0.21 development)

The new `research` route reuses those calculation, binding and manuscript functions. A
surface-study declaration locates original face values, physical areas, polygon geometry
and methods. Preparation supplies relative-path inputs, editable local figure scripts and
empty host-writing drafts. Building computes observations, refreshes declared figure recipes,
assembles the host's drafts and exports editable Word. A previous build can identify changed
dependencies while preserving author prose and scripts; interpretation remains a host task.
Large provenance-index lists in writing context use exact pointers to the retained full reports.

This concrete surface route has been exercised locally on one known real project; it is not
yet a released v0.21 capability. See the [workspace guide](../research-workspace.md).

Finite manuscript/literature/review/revision support already exists; it must not be confused
with autonomous scientific validation or complete journal compliance. Native Fluent and
STAR-CCM+ extraction, broader field diagnosis, general author-edited Word return and
cross-host heterogeneous validation remain incomplete.
See the [public roadmap](../ROADMAP.md) and [current limitations](../limitations.md).
