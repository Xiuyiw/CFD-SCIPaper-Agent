# Portable transient writing example

All source values are invented. This example exercises deterministic temporal calculations,
a scientific three-panel figure, result-bound prose/table and editable Word export; it is not
a battery case, CFD validation or a comparison of model writing quality. The recorded draft is
tutorial prose, not an AI invocation.

From the repository root, with the package and `docs` extra installed:

```text
python examples/transient-writing/run_example.py OUTPUT
```

Use a fresh OUTPUT. It contains `writing/TASK.md`, `input.json`, complete `sources/`, copied
`skills/`, `table-results.json`, a draft template, assembled section and `section.docx`.
The reproducible figure bundle includes `source-data.csv`, `plot_history.py`, editable SVG/PDF,
300 dpi PNG/TIFF and measured header-spacing checks. Read the actual preview and Word pages.

For an independent host attempt, do not show the recorded draft:

```text
python examples/transient-writing/run_example.py FRESH --prepare-only
```

Give the complete `FRESH/writing` folder to a local-tool AI host, or attach its TASK/input/results,
source method/CSV, figure and writing skill references to a file-reading web chat. Ask it to return
`draft.json` following TASK. The latter can review and write from attached evidence; local execution,
image viewing and Word export depend on its actual tools. A provider name is not a capability test.

With local tools, the real CLI invocation from any existing project directory is:

```text
cfdpaper write PROJECT --artifact results-section --package FRESH/writing --draft draft.json --output section-v1
cfdpaper write PROJECT --artifact results-section --package section-v1 --docx --layout near-reference --output section-v1.docx
```

Here PROJECT is an existing directory; paths may be absolute. Keep the full writing folder when
moving to another computer. No provider SDK, account or model-specific transport is required.
Assembly recalculates copied sources, resolves tokens and validates structure. The host/author
remains responsible for scientific interpretation and truthful image-observation status.

To redraw after relocation:

```text
python writing/sources/figure/plot_history.py writing/sources/figure/source-data.csv REDRAWN
```

A and B share nonuniform saved times. Read the computed results, not arithmetic sample means,
when interpreting temporal exposure. The regression tests check original-record calculations,
numeric bindings, independent cumulative accounting, relocated redraws and native DOCX contents.
