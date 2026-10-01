# Material analysis to a two section manuscript

This offline tutorial reuses `run_example.py`, its public synthetic CSV and method
note, and its existing compile/analyze section input. No private fixtures, model
call, solver run or new scientific validation is involved. Both section drafts
are recorded tutorial text. A native table is enough; no figure is manufactured.

Run with the package installed with its `docs` extra, from the repository root:

```text
python examples/material-analysis/prepare_manuscript.py NEW_OUTPUT
```

`NEW_OUTPUT` must not exist. The script preserves the original analysis replay
under `analysis/`, reads its generated Results input without rebuilding metric
bindings, adds a Methods input, and calls these APIs:

1. `publication.manuscript_seed.prepare_manuscript_seed(outline, workspace)`
2. `publication.manuscript.assemble_manuscript(workspace, drafts, candidate)`
3. `publication.section.export_section_docx(candidate, docx, layout="near-reference")`

The result is `NEW_OUTPUT/manuscript.docx`. Its Methods paragraph includes native
editable inline math for mean flux (overbar and fraction), not underscore text or
an equation image. Results retain all six `result_ref` bindings emitted by the
existing public example. The bindings refer to computed area, rate and mean flux
for Reference and Modified; their values are not copied into the bridge script.
`manuscript/` retains the continuation inputs, drafts, copied sources and resolved
numeric provenance. `workspace/` is the prepared input snapshot.

## Reuse selected inputs without moving them by hand

The `--outline` entry accepts the existing manuscript input format
with an optional `draft` path on each section. Section input and draft paths may
be absolute or relative to the outline, so separate analysis outputs need not be
manually collected under a shared directory first:

```text
cfdpaper write STUDY --artifact manuscript --outline outline.json --output workspace
```

The host still chooses the scientific question, section roles, dependencies and
evidence. This entry copies the selected inputs and their declared source,
figure and literature dependencies, preserving result identifiers and supplied
drafts. It does not generate claims or manuscript prose. Omit a section's `draft`
when it has not yet been written; the workspace task lists it as pending.
`workspace/drafts.json` contains only supplied drafts, while
`workspace/drafts-template.json` lists all target paths. Add completed drafts to
the map before assembly. The existing `--manuscript-input` entry remains available
for an already collected input tree. `--outline` requires v0.14.0 or later.

For a source update, preserve the original candidate. Edit a working copy's
Results CSV and reassemble it to a fresh directory with `workspace/drafts.json`.
Re-read dependent prose: recomputation updates numeric bindings, not scientific
interpretations. The original DOCX is not changed and must be separately exported
from the updated candidate when needed.

```text
python -m pytest tests/test_material_manuscript_example.py -q
```

The focused tests check computed-binding provenance, native Word math, body
indentation/spacing and heading style, source-change propagation, refusal of an
existing output path, and byte preservation of the original candidate and DOCX.
These are software contracts, not prose matching or manuscript-quality scoring.
Inspect rendered pages before reusing the document as a publication draft.
