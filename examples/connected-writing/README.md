# Connected scientific writing: a recorded synthetic example

This small example connects Methods, Results and Discussion through one mixed-unit long table.
It replays supplied drafts; it does **not** call a language model, run CFD, validate a physical
model, or cite invented literature. No figure is needed for the two scalar responses.

The prescribed modified case has a lower wall-mean temperature (310.5 versus 315 K) and a larger
pressure drop (125 versus 100 Pa). These complementary responses support a trade-off description,
not an inferred local transport mechanism or a universal design ranking. The common domain,
heat input and volumetric flow are stipulated in the synthetic method note, not measured results.

## Run

This example requires the v0.12 development source or its candidate wheel; released v0.11 does
not provide the new context and long-table options. Use a Python environment with `cfdpaper[docs]`
installed. From the repository root, for example:

```powershell
.venv/Scripts/python.exe examples/connected-writing/run_example.py "$env:TEMP/cfdpaper-connected-example"
```

The positional output directory must not already exist. The script creates:

- `raw/metrics.csv` and `raw/method.md`: the original synthetic long table and definitions.
- `materials/`, `compiled/`, `proposal.json`: the normal material/proposal route with exact
  `row_filters` and `unit_column`, without a pivot or per-metric value copy.
- `recorded/`: clearly supplied draft JSON and partial draft mappings.
- `workspace/`: prepared three-section manuscript inputs.
- `contexts/results/` and `contexts/discussion/`: current definitions, evidence and available
  dependency paragraphs, prepared before the target draft is supplied.
- `manuscript/`: a portable assembled workspace with current sources and `drafts.json`.
- `manuscript.docx`: editable text and a native Word table.

Results use paragraph `shared_unit` to state K or Pa once in the same sentence. The native table
retains per-value units. Discussion binds directly to the Results-owned temperature and pressure
differences; it does not transcribe those values into a separate table. A repeated record ID in
the unrelated status row demonstrates that exact metric selection precedes member checks.

## Move, refresh and reassemble

Copy or move the complete `manuscript/` folder. Its `drafts.json`, section inputs and sources use
relative paths. From that folder's parent, with `portable` denoting the moved folder:

```text
cfdpaper write . --artifact manuscript --package portable --context-for discussion --draft portable/drafts.json --output refreshed-context
cfdpaper write . --artifact manuscript --package portable --draft portable/drafts.json --output recomputed
cfdpaper write . --artifact manuscript --package recomputed --docx --layout near-reference --output recomputed.docx
```

To exercise source propagation, edit only the copied
`portable/sections/results/sources/metrics.csv`: change modified temperature from `310.5` to
`308.5`, or pressure drop from `125` to `130`, preserving the other columns. Reassembly updates
Results, its native table and Discussion to temperature change −6.50 K and pressure change
30.00 Pa when both edits are made. Original CSV record positions remain 3/5 for temperature
and 4/6 for pressure. Earlier assembled output is not overwritten.

Bound numbers refresh; recorded explanations do not rewrite themselves. A change that reverses
the response or alters its scientific definition requires rereading the affected prose. This
example tests source selection, current context and propagation, not the quality of autonomous
scientific reasoning. DOCX structure tests do not replace actual Word/PDF page inspection.

## Long tables, concise values and page layout

Each calculation in the proposal uses `row_filters`, for example
`{"metric": "wall_temperature"}`, and `unit_column: "unit"`. Values match exactly, before numeric
conversion. Unit strings must match the declared value unit. This avoids mixing metrics, but it
does not infer their scientific definitions or silently convert units.

A paragraph can set `shared_unit: "K"` when its text explicitly states K and every bound numeric
token in that paragraph has that unit. The result can read “Temperatures (K) are 315.00 and 310.50”
without losing the full units in its evidence record. Other paragraphs, captions and table cells
retain their units; inline math is unchanged. Do not use this option for mixed-unit paragraphs.

For a long caption that would unnecessarily push a fixed-size figure onto the next page, the
section input's `style` may set `figure_caption_pagination: "allow-split"`. The figure stays with
the caption opening, while the remaining caption may continue. Default `"keep"` retains the
whole caption. Likewise `table_pagination: "allow-split"` releases the short-table keep chain;
default `"auto"` keeps compact tables together and lets long tables flow. Both preserve repeated
table headers, row integrity and notes. These options do not change text, font sizes or figure
data. Inspect actual Word/PDF pages before choosing them; less blank space is not always better.
