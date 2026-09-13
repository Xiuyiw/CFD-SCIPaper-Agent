# CFD-Paper-Agent

[![CI](https://github.com/Xiuyiw/CFD-SCIPaper-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Xiuyiw/CFD-SCIPaper-Agent/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Xiuyiw/CFD-SCIPaper-Agent)](https://github.com/Xiuyiw/CFD-SCIPaper-Agent/releases/latest)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

CFD-Paper-Agent is an open-source, author-in-the-loop workflow for turning mature CFD evidence into
defensible paper topics, figures, and manuscript prose. Version 0.8.0 connects the multi-section
workspace to shared literature, source-bound summaries, targeted change reports and optional
numeric CSL bibliography formatting. Dedicated writing guidance covers Introduction, Discussion,
Abstract and Conclusions alongside the existing Methods and Results workflow.
The workflow preserves the connection between the original observations, scientific interpretation,
and the numbers and graphics appearing in the manuscript.

The software does not replace scientific judgment. Authors still choose the research topic, accept
the QoI and figure claim, and approve the final artifact.

## Capability matrix

| Capability | State | Current boundary |
|---|---|---|
| Project initialization, inspection, status, and resumable state | Available | Local project state and source-change detection. |
| Author-supplied or evidence-bounded topic planning | Available | Two to four provisional topics from mature structured records; author selection is required. |
| Scientific comparison qualification | Available | Strict records, observation membership, units, locators, comparison roles, convergence, conservation, verification, and validation. |
| Discrete QoI analysis and claim ceiling | Available | Locked observed cases only; no interpolation or continuous optimization. |
| Figure production | Available | One evidence-bound panel with source data, runnable script, SVG/PDF/PNG/TIFF, physical dimensions, caption, and QA results. |
| Evidence writing | Available | Numeric paragraph or host-authored multi-figure subsection; current CSV calculations bind to evidence tokens with units and source records. |
| Subsection DOCX and external review package | Available | Editable prose, tables and structured math; configurable figure sizing and placement; optional LibreOffice PDF preview; separate review suggestions. |
| Guided scientific intake | Experimental | Interactive alternative to an existing `project-records.json` envelope. |
| Existing materials to subsection analysis | Available | CSV and method profiling; portable host-AI proposals; author-selected population/partition calculations, expression choices and source-linked writing. |
| Multi-section manuscript workspace | Available | Shared paper spine, terms and section duties; role-specific host guidance, keywords, global figure/table/equation numbering and editable DOCX. |
| Shared literature workspace | Available | Local CSL JSON, DOI deduplication and aliases; claim-specific excerpts, locators, roles and author/host support decisions travel with the manuscript. Optional Pandoc imports BibLaTeX. |
| Cross-section evidence updates | Available | Explicit owner-evidence bindings refresh numerical tokens; declared dependencies produce section and paragraph review suggestions without rewriting prose or figures. |
| Numeric journal bibliography | Available | Optional local Pandoc citeproc and a standalone CSL file; bracket-number citations in first-citation order, with bold/italic reference text in Word. |
| Portable continued editing | Available | Local drafts, sources and task context travel with the candidate; reassembly preserves unedited drafts. Word-only edits must be reconciled into the draft. |
| External drawing tasks | Available | Host-facing data, conceptual and hybrid tasks; import Python, SVG or uncompressed draw.io editing sources with previews and listed supporting files. Import does not run scripts or approve figures. |
| Native Fluent, STAR-CCM+, and other solver ingestion | Roadmap | Export structured neutral inputs for this release. |

Autonomous full-paper reasoning and journal revision are not provided: the host and author develop
the argument, assess literature support and respond to real reviewer comments.

## Installation

CFD-Paper-Agent supports CPython 3.10–3.12. For the literature-linked workspace, use a v0.8 checkout
or a wheel built from the same version; the v0.7.0 wheel does not contain these additions.
From the checkout root, install with Word support:

```text
python -m pip install ".[docs]"
cfdpaper --help
```

Start with the [seven-section literature tutorial](examples/literature-manuscript/README.md)
to prepare shared tasks, assemble the supplied analytical drafts, export Word and continue from
a moved workspace. The smaller [manuscript workspace tutorial](examples/manuscript-workspace/README.md)
remains available. See the [v0.8.0 notes](docs/releases/v0.8.0.md) for the version scope.

The default bibliography needs no additional tool. For BibLaTeX import or journal-style references,
install [Pandoc](https://pandoc.org/installing.html) separately and put `pandoc` on PATH.
PDF preview uses an existing LibreOffice installation.

## Reproducible evidence Quickstart

Copy `examples/steady_laminar_pipe` to a writable directory and change into the copied directory.
The example uses synthetic, non-sensitive data for fully developed laminar pipe flow.

Run the evidence workflow in this order:

```text
cfdpaper init . --project-id steady-laminar-pipe
cfdpaper inspect .
cfdpaper qualify . --records project-records.json --observations observations.csv --question question.json
cfdpaper plan . --candidates topic-candidates.json --approve-topic steady-pipe-pressure-drop --author "Fixture Author"
cfdpaper qualify . --approve-qoi-contract QOI_ID --author "Fixture Author"
cfdpaper analyze .
cfdpaper figure . --approve-contract FIGURE_ID --author "Fixture Author"
cfdpaper write . --artifact results-paragraph
cfdpaper write . --artifact results-paragraph --approve-final --author "Fixture Author"
```

Replace `QOI_ID` with the identifier printed by the first `qualify` command and `FIGURE_ID` with the
identifier printed by `analyze`. The fixture should reach a qualified numerical observation, not a
supported physical interpretation, because it supplies an analytic numerical-verification reference
but no external validation dataset. See the [fixture walkthrough](examples/steady_laminar_pipe/README.md)
and its machine-readable [oracle](examples/steady_laminar_pipe/oracle.json).

Negative fixture variants demonstrate that missing members, duplicate observations, unknown units,
or failed convergence stop before unsupported analysis, figure, or paragraph artifacts are created.

## Inputs

### Literature-linked manuscripts

The [seven-section example](examples/literature-manuscript/README.md) covers Abstract, Introduction,
Methods, two Results sections, Discussion and Conclusions. It uses supplied analytical data and
authored sample drafts, with one local explanatory source shared across chapters:

```text
python examples/literature-manuscript/prepare_example.py my-source
cfdpaper write my-source --artifact manuscript --manuscript-input my-source/manuscript-input.json --output my-package
cfdpaper write my-source --artifact manuscript --package my-package --draft my-source/drafts.json --output my-manuscript
cfdpaper write my-source --artifact manuscript --package my-manuscript --docx --layout near-reference --output my-manuscript.docx
```

Run these commands from the checkout root after installation; every output path must be new.
For your own study, give the prepared `TASK.md` and section tasks to the host AI instead of using
the sample drafts.

The manuscript's `literature` field points to a relative JSON file containing a `bibliography`
path and `supports` records. Bibliographic identity is separate from each section's `claim`,
`role`, source `excerpt`, `locator` and support `status`. Only `supported` records become citation
evidence; withdrawing support prevents stale references from assembling. Exact excerpt matching
checks where the passage occurs, while the host and author decide what it supports. Original
source text, metadata and aliases stay with the workspace; relevant excerpts, source texts and
reference metadata are also included in detached section review packets.

Use a section's `evidence_bindings`, such as `{"dp": "results/dp"}`, to consume an owning section's
evidence through a local `{{value:dp}}` token. `depends_on` declares which other sections the host
should read when reconsidering the argument. On continuation, `CHANGES.md` identifies affected
sections and paragraph positions after source, definition, literature, terminology or draft changes.
Bound calculations refresh from the owner's current source; interpretations and plots remain
host/author work. The manifest's `keywords` list appears after the Abstract in Markdown and Word.

To apply journal bibliography formatting, add `"citation_style": "my-journal.csl"` to the manifest
and provide that standalone local CSL file. Pandoc formats the shared metadata in current citation
order; the style travels with the candidate. This route supports bracketed numeric citations, not
author–date or superscript styles, and does not create Zotero fields. Omit `citation_style` to use
neutral metadata labels. See the tutorial for exact inputs and a source-change continuation exercise.

### Existing exports to an analysis subsection

The material-analysis route accepts a folder of exported CSV tables, method notes and
existing raster figures, without a prewritten scientific-records envelope:

```text
cfdpaper inspect STUDY --materials --output profile
cfdpaper plan STUDY --artifact analysis --output analysis-materials
```

Give `analysis-materials/host-task.md` to your local AI. The package includes the analysis
and figure-selection skills. The host reads the definitions, proposes useful comparisons,
and writes the proposal; the author selects a direction and resolves essential ambiguities.
Selection recomputes the declared quantities and prepares a portable writing task, including
the writing skill and its mechanism guidance. No API key or manually written JSON is required
from the author when using a capable local host.

Follow the [material-analysis tutorial](examples/material-analysis/README.md) for selection,
writing and DOCX export. A compact table or prose can replace an unnecessary plot; custom
figure requests remain pending until their actual artwork is supplied. Body formatting defaults
to two-character first-line indentation and zero paragraph spacing, with explicit template overrides.
This route supports declared population and partition calculations, not arbitrary
solver extraction or automatic causal inference. The existing evidence-first workflow remains available.

### Supplied evidence and figures

For existing figures and deeper host-AI writing, follow the
[two-figure subsection tutorial](examples/section-writing/README.md). It includes
Word export, raw-table bindings, editable tables/equations and an external-review packet.
See [v0.5.0](docs/releases/v0.5.0.md) for scope and the downloadable example.
Install the `docs` extra for DOCX (`python -m pip install -e ".[docs]"`).

The four bundled skills are available under `skills/` in a checkout and
`importlib.resources.files("cfdpaper").joinpath("skills")` in an installed wheel.
Give the writing skill and prepared package to your host AI; no API key is needed
for local assembly.

The non-interactive evidence workflow accepts:

- `project-records.json`: cases, boundaries, comparison roles, numerical checks, verification,
  validation, and source locations;
- `observations.csv`: located scalar observations with case identity, coordinate, variable, value
  role, scope, value, and unit;
- `question.json`: the proposed QoI definition, operator, operands, expected membership, units, and
  reporting policy;
- a topic-candidate JSON file accepted by `cfdpaper plan`.

These are structured scientific inputs, not arbitrary solver files. The input observations are never
rewritten.

## Outputs

Project-local outputs are written under `.cfdpaper/outputs/`:

```text
plan/topic-ranking.json
qualify/qualification-report.json
qualify/candidate-qoi-contract.json
qualify/locked-qoi-contract.json
qualify/qoi-results.json
qualify/claim-ceiling.json
qualify/candidate-figure-contract.json
qualify/paragraph-duty.json
figure/FIGURE_ID/source-data.csv
figure/FIGURE_ID/plot_FIGURE_ID.py
figure/FIGURE_ID/FIGURE_ID.svg
figure/FIGURE_ID/FIGURE_ID.pdf
figure/FIGURE_ID/FIGURE_ID.png
figure/FIGURE_ID/FIGURE_ID.tiff
figure/FIGURE_ID/caption.txt
figure/FIGURE_ID/qa-data.json
figure/FIGURE_ID/qa-narrative.json
figure/FIGURE_ID/qa-visual.json
write/results-paragraph.txt
write/numeric-backlinks.json
write/delivery.json
```

Changed scientific inputs make dependent artifacts stale. The CLI reports the earliest command that
must be rerun. Invalid input exits with a correction, insufficient evidence stops without downstream
artifacts, and render or write failures are not presented as completed work.

## Topic planning

`cfdpaper plan` can rank an author file or generate provisional candidates from mature structured
records:

```text
cfdpaper plan PROJECT_ROOT --candidates AUTHOR_CANDIDATES.json
cfdpaper plan PROJECT_ROOT --provider offline
cfdpaper plan PROJECT_ROOT --provider auto
cfdpaper plan PROJECT_ROOT --regenerate
```

The deterministic offline path requires no API key. Author files take precedence over generated
candidates. Generated topics remain provisional: reports retain the minimum missing-data list,
provider transport is not real author approval, and ordinary indexed files are not promoted
automatically to verified scientific evidence.

## Explicit non-capabilities

CFD-Paper-Agent does not run CFD simulations, ingest arbitrary native solver cases, infer missing
values, construct undeclared spatial integrals, smooth discrete cases into a continuous response,
identify an operating optimum, autonomously write a complete paper, independently verify scientific
support in literature, export submission packages, or submit to a journal. Multi-section and subsection DOCX
export and subsection review-suggestion import are available through `write`; the root `review`,
`revise`, and `export` commands remain unavailable. External drawing-task exchange does not add
automatic complex mechanism graphics or establish broad heterogeneous CFD validation.

## Public documentation

- [Documentation index](docs/README.md)
- [Architecture overview](docs/architecture/overview.md)
- [Roadmap](docs/ROADMAP.md)
- [v0.8.0 notes](docs/releases/v0.8.0.md)
- [v0.7.0 release notes](docs/releases/v0.7.0.md)
- [v0.5.0 release notes](docs/releases/v0.5.0.md)
- [v0.6.0 release notes](docs/releases/v0.6.0.md)
- [v0.4.0 release notes](docs/releases/v0.4.0.md)
- [v0.3.1 release notes](docs/releases/v0.3.1.md)
- [v0.3.0 release notes](docs/releases/v0.3.0.md)
- [v0.2.0 release notes](docs/releases/v0.2.0.md)
- [v0.1.0 release notes](docs/releases/v0.1.0.md)
- [Limitations](docs/limitations.md)
- [Contributing and issue-reporting guidance](CONTRIBUTING.md)
- [Citation metadata](CITATION.cff)

## Data and scientific boundary

Do not commit confidential solver cases, unpublished manuscripts, company data, credentials, or
licensed files. File presence is not validation: comparability, convergence, conservation, units,
QoI definitions, source provenance, and claim scope still require scientific review.

## License

Apache-2.0 for the source code. Public examples are synthetic and provided solely for software
demonstration.
