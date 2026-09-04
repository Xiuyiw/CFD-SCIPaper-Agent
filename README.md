# CFD-Paper-Agent

CFD-Paper-Agent is an open-source, author-in-the-loop workflow for turning mature CFD evidence into
defensible paper topics, figures, and results prose. Version 0.3.0 adds a complete evidence pathway:
qualify a declared comparison, lock a quantity of interest (QoI), analyze discrete cases, render an
evidence-bound figure, and write one numerically backlinked results paragraph.

The software does not replace scientific judgment. Authors still choose the research topic, accept
the QoI and figure claim, and approve the final artifact.

## Capability matrix

| Capability | State | Current boundary |
|---|---|---|
| Project initialization, inspection, status, and resumable state | Available | Local project state and source-change detection. |
| Author-supplied or evidence-bounded topic planning | Available | Two to four provisional topics from mature structured records; author selection is required. |
| Scientific comparison qualification | Available | Strict records, observation membership, units, locators, comparison roles, convergence, conservation, verification, and validation. |
| Discrete QoI analysis and claim ceiling | Available | Locked observed cases only; no interpolation or continuous optimization. |
| Figure production | Available | One evidence-bound panel with source data, runnable script, SVG, PNG, caption, and three QA results. |
| Evidence writing | Available | One results paragraph with numeric backlinks and an author-approved reporting ceiling. |
| Guided scientific intake | Experimental | Interactive alternative to an existing `project-records.json` envelope. |
| Native Fluent, STAR-CCM+, and other solver ingestion | Roadmap | Export structured neutral inputs for this release. |
| Full-manuscript writing, literature management, review, revision, and document export | Roadmap | Not delivered by the v0.3.0 CLI. |

## Installation

CFD-Paper-Agent supports CPython 3.10–3.12. From a public checkout:

```text
python -m pip install -e .
cfdpaper --help
```

## Reproducible v0.3.0 Quickstart

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
figure/FIGURE_ID/FIGURE_ID.png
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
candidates. Ordinary indexed files are not promoted automatically to verified scientific evidence.

## Explicit non-capabilities

Version 0.3.0 does not run CFD simulations, ingest arbitrary native solver cases, infer missing
values, construct undeclared spatial integrals, smooth discrete cases into a continuous response,
identify an operating optimum, write a complete manuscript, manage references, export submission
documents, or submit to a journal. The `review`, `revise`, and `export` commands remain unavailable.

## Public documentation

- [Documentation index](docs/README.md)
- [Architecture overview](docs/architecture/overview.md)
- [Roadmap](docs/ROADMAP.md)
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
