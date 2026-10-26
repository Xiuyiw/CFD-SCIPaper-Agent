# CFD-Paper-Agent

[![CI](https://github.com/Xiuyiw/CFD-SCIPaper-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Xiuyiw/CFD-SCIPaper-Agent/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Xiuyiw/CFD-SCIPaper-Agent)](https://github.com/Xiuyiw/CFD-SCIPaper-Agent/releases/latest)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

CFD-Paper-Agent is an open-source, author-in-the-loop workflow for turning mature CFD evidence into
defensible paper topics, figures, and manuscript prose. Its host-assisted materials-to-manuscript
workflow connects exported tables, method notes and definition scripts with supported calculations,
source-bound writing and editable Word output. The host AI develops the argument; the software
profiles materials, computes declared quantities and keeps numerical evidence connected to the draft.
Whole-paper review, targeted host editing, mixed-unit long-table selection, direct NPZ analysis,
cross-section evidence links and shared literature remain available.
The workflow preserves the connection between the original observations, scientific interpretation,
and the numbers and graphics appearing in the manuscript.

The software does not replace scientific judgment. Authors still choose the research topic, accept
the QoI and figure claim, and approve the final artifact.

Version 0.25.0 connects saved-report calculations to complementary response figures and
host-written Methods/Results/Discussion. Multiple series share exact case identities, source
definitions and bound values; continuing a report executes the retained author-local plotting
script against current source rows. Two original-face maps can also share a scale and accompany
layer-wise positive, negative and net transfer diagnostics. Studio-guided editable mechanism
artwork uses the existing figure exchange and manuscript attachment path, not a new automatic
mechanism-discovery engine. Start with the
[bound-response report example](examples/bound-response-report/README.md) and
[version notes](docs/releases/v0.25.0.md).

The optional local MCP server shares nine task functions with CLI/Python. Existing report
bindings, explicit reference denominators, native Word formulas, portable workspaces and
[managed Word collaboration](docs/releases/v0.23.0.md) remain available. See the
[portable host guide](docs/portable-workbench.md) and
[report-writing example](examples/report-writing/README.md).

The existing [physical diagnostics workflow](examples/physical-diagnostics/README.md) connects
regional field reductions, signed transport, matched changes and control-volume budgets to
complementary figures and source-bound prose. Optional saved-Fluent extraction and neutral NPZ/CSV
inputs use the same analysis chain. Studio guidance supplies conceptual diagrams, not invented fields.

Earlier workflows remain available: the
[materials-to-manuscript example](examples/material-analysis/MANUSCRIPT.md),
[effective-methods tutorial](examples/effective-methods/README.md),
[中文工程试用指南](docs/tutorials/engineering-trial.md),
[paired-observation tutorial](examples/paired-observations/README.md),
[multi-observation tutorial](examples/multi-observation/README.md),
[transient writing tutorial](docs/tutorials/transient-writing.md) and
[scientific context guide](docs/scientific-context.md). The
[connected-writing example](examples/connected-writing/README.md) covers long-table evidence;
the [review tutorial](examples/literature-manuscript/README.md#whole-manuscript-external-review-v09)
covers whole-manuscript feedback and selected editing.

## Capability matrix

| Capability | State | Current boundary |
|---|---|---|
| Project initialization, inspection, status, and resumable state | Available | Local project state and source-change detection. |
| Author-supplied or evidence-bounded topic planning | Available | Two to four provisional topics from mature structured records; author selection is required. |
| Scientific comparison qualification | Available | Strict records, observation membership, units, locators, comparison roles, convergence, conservation, verification, and validation. |
| Discrete QoI analysis and claim ceiling | Available | Locked observed cases only; no interpolation or continuous optimization. |
| Figure production | Available | Evidence-bound profiles, reference-range and multi-series response panels; original-face maps and declared diagnostic composites. Source data, local script, SVG/PDF/PNG/TIFF, physical dimensions and captions remain with each figure. |
| Evidence writing | Available | Numeric paragraph or host-authored multi-figure subsection; CSV or explicitly mapped NPZ calculations bind to evidence tokens with units and source locations. |
| Subsection DOCX and external review package | Available | Editable prose, tables and structured math; configurable figure sizing and placement; optional LibreOffice PDF preview; separate review suggestions. |
| Guided scientific intake | Experimental | Interactive alternative to an existing `project-records.json` envelope. |
| Existing materials to subsection analysis | Available | CSV/method profiling, bounded large-CSV previews and NPZ metadata; portable host-AI proposals; author-selected calculations and source-linked writing. v0.13 adds `.py` intake as source text, never execution. |
| Materials-to-manuscript guidance | Available | Thin workflow entry coordinates four specialist skills; portable analysis packages include all five skills. `--outline` gathers selected inputs, dependencies and optional drafts without rebuilding numeric bindings. Missing prose remains pending. |
| Spatially weighted evidence | Available | Weighted mean, population SD and measure sum from declared positive area/volume weights, optionally restricted by supplied overlap fractions; source-linked prose and native Word tables. Domain coverage remains an author/host judgment. |
| Connected surface research | Available | Two to four declared NPZ face fields with physical areas and polygon geometry; weighted diagnostics, exact area-exceedance distributions, shared-scale field maps and four-section Word output. Comparability remains explicit. |
| Physical diagnostics and mechanism evidence | Available | Region-weighted quantities, density/element-total/vector-flux integrals, opposing signed contributions, matched original geometry and defined budgets; complementary figures and source-bound writing. Planar polygon clipping is optional; curved walls need suitable native reports or supplied fractions. |
| Saved Fluent surface extraction | Experimental | Optional PyFluent reference reader for saved CASE/DATA, boundary temperature/heat flux, original polygons and native surface/coordinate-clip reports. Tested on Windows with Fluent 2023 R1/PyFluent 0.20; not arbitrary solver or field support. |
| Research refresh and author-asset preservation | Available | Source/definition changes update affected recipes, bound values and review locations; local plotting scripts and drafts are retained. The host revisits interpretations and conceptual arrows. |
| Saved transient evidence | Available | Exact sampled windows, nonuniform trapezoidal integrals/means, saved extrema and threshold samples; cumulative increments without double integration. No interpolation or native-event reconstruction. |
| Reference-range evidence | Available | Model/reference deviations and signed distances from supplied bounds, with original range meaning and units; no combined model-validation score. |
| Paired observation contrasts | Available | Model and reference changes from two explicit members, conservative endpoint subtraction and original records; contrast agreement does not erase absolute bias. |
| Source-bound method parameters | Available | Finite JSON numbers at exact pointers refresh prose, native tables/equations and cross-section links; active configurations and units are declared by the host. |
| Located method definitions | Available | Static Python class/function indexes and exact qualified-name reads preserve original lines and truncation; no execution or automatic active-model inference. |
| Same-record history differences | Available | Comparison-minus-reference from two original columns, saved-window statistics and profiles; temperature differences in K, original readings and locations retained. |
| Complementary numerical panels | Available | Saved profiles, model/reference ranges and discrete multi-series responses with exact-case x/y bindings, multi-column layout, source CSV and standalone editable exports. Straight guides are optional; no fit or smoothing is inferred. |
| Linked computed comparisons | Available | Compare two compatible calculated scalars while retaining both sources; update bound prose, tables and cross-section values. Chained comparisons and inferred comparability are not supported. |
| Multi-section manuscript workspace | Available | Shared paper spine, terms and section duties; ordered paragraph/figure/table/equation blocks, global numbering and DOCX/Markdown/LaTeX views. |
| Formal manuscript profiles | Available | Research, report and conference presentation over the same scientific content; native Word equations and tables. Explicit templates take precedence; style/last-section Word import is not arbitrary journal-template compliance. |
| Managed Word author return | Available | Baseline/author/current reconciliation for prose, captions, supported formatting, local Figure/Fig. aliases, within-section moves and anchored comments. Numerical, formula, field, image-content and overlapping edits remain localized conflicts, not silent source changes. |
| Shared literature workspace | Available | Local CSL JSON, DOI deduplication and aliases; claim-specific excerpts, locators, roles and author/host support decisions travel with the manuscript. Optional Pandoc imports BibLaTeX. |
| Cross-section evidence updates | Available | Explicit owner-evidence bindings refresh numerical tokens; declared dependencies produce section and paragraph review suggestions without rewriting prose or figures. |
| Numeric journal bibliography | Available | Optional local Pandoc citeproc and a standalone CSL file; bracket-number citations in first-citation order, with bold/italic reference text in Word. |
| Portable continued editing | Available | Local drafts, sources and task context travel with the candidate. Managed Word edits return through `cfdpaper author`; other detached Word files require host reconciliation. Original returns and unresolved comments are retained. |
| Portable workbench and host tools | Available | Selective workspace/baseline/author export, inspection and relocation recovery; nine shared CLI/Python task functions through optional local stdio MCP. This is not whole-project SQLite migration or an AI runtime. |
| Saved JSON reports to bound writing | Available | Exact JSON pointers, named setup/reference sources, unit conversions, differences/ratios/relative changes, explicit denominators and support domains; the same results feed response figures, host-written sections, native tables/formulas and current-source continuation. |
| Heterogeneous real-task evaluation | Experimental | Known-project single-phase flow/pressure and conjugate-heat-transfer paths have been exercised. Suitable mature real transient/multiphase CFD materials remain unavailable; battery control-model tests do not fill that gap. |
| External drawing tasks and mechanism attachment | Available | Studio-guided conceptual/hybrid tasks, editable-source import and manuscript attachment. Explicit `raster_concept` is schematic-only and reports no editable source; it cannot replace computed fields. Import does not approve figures. |
| Whole-paper review and selected editing | Available | Complete reports, exact targets and optional shared-evidence locations travel with editable drafts; the host evaluates and implements changes. |
| Broader native solver ingestion | Roadmap | The Fluent surface reference path above is available; STAR-CCM+ and other unsupported native quantities still require structured neutral exports. |

Autonomous full-paper reasoning and journal revision are not provided: the host and author develop
the argument, assess literature support and respond to real reviewer comments.

## Installation

CFD-Paper-Agent supports CPython 3.10–3.12. Use the v0.25.0 checkout or source archive
from [GitHub Releases](https://github.com/Xiuyiw/CFD-SCIPaper-Agent/releases), then install
with Word support from its root:

```text
python -m pip install ".[docs]"
cfdpaper --help
```

Alternatively, download the matching release wheel and install it with Word support:

```text
python -m pip install "./cfd_paper_agent-0.25.0-py3-none-any.whl[docs]"
```

The examples live in the source checkout/archive, not the wheel. For the managed Word workflow,
run the source-checkout command below, or copy `examples/author-collaboration` anywhere writable
and use the absolute path to that standalone script against the installed package:

```text
python examples/author-collaboration/run_example.py output/author-demo
```

Open `output/author-demo/recovered/manuscript.docx`. The replay preserves a clearly labelled
automation wording edit and comment while applying current CSV values; it is not human approval.
For your own manuscript, prepare and return the author copy with:

```text
cfdpaper author --package CANDIDATE --output AUTHOR_WORKSPACE
cfdpaper author --package CURRENT_CANDIDATE --return-docx AUTHOR_RETURN.docx --output NEW_RETURN
cfdpaper author --package NEW_RETURN/candidate --format tex --profile conference --output paper.tex
cfdpaper research --workspace RESEARCH_WORKSPACE --baseline PREVIOUS_BUILD --author-candidate NEW_RETURN/candidate --output UPDATED_RESEARCH
```

Keep the complete author workspace and save the edited Word under a new name. Read the returned
`CONTINUE.md` for conflicts and interpretation work. See the
[author tutorial](examples/author-collaboration/README.md) for supported edits and profile exports.

For report-bound response figures and Word, run
`python examples/bound-response-report/run_example.py output/response-demo` and open
`output/response-demo/candidate/manuscript.docx`. The example supplies illustrative author prose
and synthetic values, not an automatically discovered physical explanation.
For saved JSON report writing and native math, run
`python examples/report-writing/run_example.py output/report-demo`.
For another MCP-capable host, install the matching wheel with `[docs,mcp]` and launch
`python -m cfdpaper.mcp_server` as its local stdio server. Terminal hosts need no MCP dependency.
The [portable workbench tutorial](examples/portable-workbench/README.md) demonstrates a moved
analytical author workspace; the [host guide](docs/portable-workbench.md) describes real-task entry.

Run the connected synthetic surface example from the source root, choosing a new output directory:

```text
python examples/surface-research/run_example.py output/surface-demo
```

Open `output/surface-demo/candidate/manuscript.docx`. Add `--prepare-only` for an empty
host-writing workspace instead of replaying the supplied example prose. See the
[surface tutorial](examples/surface-research/README.md) for source/threshold refresh and relocation.

The [seven-section literature tutorial](examples/literature-manuscript/README.md) shows how
to prepare shared tasks, assemble the supplied analytical drafts, export Word and continue from
a moved workspace. The smaller [manuscript workspace tutorial](examples/manuscript-workspace/README.md)
remains available. For region clipping and signed-transfer figures, install `.[docs,geometry]`
and run `python examples/physical-diagnostics/run_example.py output/physical-demo`.
See the [v0.23.0 notes](docs/releases/v0.23.0.md) for author collaboration and the
[v0.22.0 notes](docs/releases/v0.22.0.md) for physical diagnostics, with
[v0.21.0 notes](docs/releases/v0.21.0.md) for the preceding baseline.

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

### Existing materials to analysis and a manuscript

The material-analysis route accepts a folder of exported CSV tables, method notes,
Python definition scripts and existing raster figures, without a prewritten scientific-records
envelope. Python scripts are read as line-numbered text; intake does not execute them:

```text
cfdpaper inspect STUDY --materials --output profile
cfdpaper plan STUDY --artifact analysis --output analysis-materials
```

If a definition is beyond the initial preview, search its actual source text:

```text
cfdpaper inspect STUDY --materials --find "wall temperature" --find "area average" --output matches
cfdpaper plan STUDY --artifact analysis --material-path exports/comparison.csv --material-path methods.md --output focused-materials
```

Search results contain file/line locations and nearby text. Repeat `--material-path` to select
known files for profiling, search or analysis preparation; this avoids copying a new study
directory when default discovery omits a relevant export. Selection replaces discovery, so include
the required definition files as well as the tables. Check skipped/truncated entries: no match
does not establish that a setting or result is absent. Source scripts remain text, never executed.

Give `analysis-materials/host-task.md` to your local AI. The portable package includes
`cfd-paper-workflow` and the four specialist skills for evidence intake, QoI/physics,
figure production and evidence writing, with their references. The host starts with the
workflow entry and loads the relevant guidance as needed. It reads the definitions, proposes
useful comparisons and writes the proposal; the author selects a direction and resolves
essential ambiguities. Definition gaps that prevent the selected calculation belong in
`missing_questions`; missing evidence that only limits a stronger interpretation belongs in
`interpretation_limits`.
Selection recomputes the declared quantities and prepares a portable writing task, including
the writing skill and its mechanism guidance. No API key or manually written JSON is required
from the author when using a capable local host.

Follow the [material-analysis tutorial](examples/material-analysis/README.md) for selection,
writing and DOCX export. To connect calculated Results with Methods, run this recorded
synthetic example from the checkout root, using a new output directory:

```text
python examples/material-analysis/prepare_manuscript.py my-material-manuscript
```

It produces `my-material-manuscript/manuscript.docx` and a portable manuscript candidate.
The [bridge tutorial](examples/material-analysis/MANUSCRIPT.md) explains how it reuses the six
existing result bindings and adds native editable math, using the established manuscript and
Word APIs. For your own work, point the manuscript section entry at the generated
`selected/section-input/writing/input.json` and preserve its surrounding source directories.
Use exact local evidence IDs in `required_claim_ids`; use `evidence_bindings` aliases for
cross-section evidence. Resume an existing candidate from `CONTINUE.md` and `drafts.json`.

A compact table or prose can replace an unnecessary plot; custom
figure requests remain pending until their actual artwork is supplied. Body formatting defaults
to two-character first-line indentation and zero paragraph spacing, with explicit template overrides.
This route supports declared population, partition and `weighted_population` calculations, not
arbitrary solver extraction or automatic causal inference. The existing evidence-first workflow
remains available.

For unequal spatial elements, explicitly declare the value column, positive area/volume weight
column and measure units. `weighted_population` produces `weighted_mean`, `weighted_std` and
`weight_sum`; it does not infer weights from column names. Absolute-temperature means retain their
scale (for example, °C), while their spatial SD is reported in K, not as uncertainty in the mean.
The bundled host skills connect field location and extent with mean, spread and extrema without
turning one scalar ranking into an unsupported performance or causal ranking.

The [spatial example](examples/spatial-diagnostics/README.md) combines unequal-area analytical
wall facets, a separate volume-weighted check, a reproducible map and a native Word table whose
numeric headers align with the values. It replays a recorded guided host draft; it neither calls
a model automatically nor supplies CFD validation. Use its `--prepare-only` option for a new host
attempt without the recorded answers.

### Supplied evidence and figures

For existing figures and deeper host-AI writing, follow the
[two-figure subsection tutorial](examples/section-writing/README.md). It includes
Word export, raw-table bindings, editable tables/equations and an external-review packet.
See [v0.5.0](docs/releases/v0.5.0.md) for scope and the downloadable example.
Install the `docs` extra for DOCX (`python -m pip install -e ".[docs]"`).

The workflow entry and four specialist skills are available under `skills/` in a checkout and
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
export and subsection review-suggestion import are available through `write`. Root `review`
supports complete manuscript packages, lossless report return and
selected editing-task preparation (`--actions`). The host edits a separate ordinary manuscript
workspace and reassembles it; managed Word author returns also use the generated baseline and
current candidate. Neither route makes scientific revision automatic or supports arbitrary
lossless Word reconstruction.
Root `revise` and `export` remain unavailable. External drawing-task exchange does not add
automatic complex mechanism graphics or establish broad heterogeneous CFD validation.

## Public documentation

- [Documentation index](docs/README.md)
- [Architecture overview](docs/architecture/overview.md)
- [Roadmap](docs/ROADMAP.md)
- [v0.25.0 version notes](docs/releases/v0.25.0.md)
- [Bound response figures and report example](examples/bound-response-report/README.md)
- [v0.24.0 version notes](docs/releases/v0.24.0.md)
- [Portable host guide](docs/portable-workbench.md)
- [Saved-report writing example](examples/report-writing/README.md)
- [v0.23.0 release notes](docs/releases/v0.23.0.md)
- [Managed Word author collaboration](examples/author-collaboration/README.md)
- [v0.22.0 release notes](docs/releases/v0.22.0.md)
- [v0.21.0 release notes](docs/releases/v0.21.0.md)
- [Surface research commands](docs/research-workspace.md)
- [v0.20.0 release notes](docs/releases/v0.20.0.md)
- [v0.15.0 development notes](docs/releases/v0.15.0.md)
- [v0.13.0 development notes](docs/releases/v0.13.0.md)
- [v0.12.0 notes](docs/releases/v0.12.0.md)
- [v0.11.0 notes](docs/releases/v0.11.0.md)
- [v0.10.0 notes](docs/releases/v0.10.0.md)
- [v0.9.0 notes](docs/releases/v0.9.0.md)
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
