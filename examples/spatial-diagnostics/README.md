# Spatial diagnostics and scientific explanation

This v0.10 example uses prescribed analytical fields, **not CFD results**.
It exercises area/volume-weighted statistics, a portable field figure, bound prose
and a native Word table. It does not demonstrate a cooling mechanism or validate a solver.

The six wall facets have unequal areas. Modified has a lower area-weighted mean
temperature but a larger spatial standard deviation and a hotter terminal facet.
The map preserves physical facet widths and shares one color scale between fields;
the small table supplies the aggregate readings without an extra two-point chart.
The separate volume dataset checks volume weighting and is not wall-mechanism evidence.

## Run

Use the v0.10 checkout or its matching wheel with the `docs` extra installed.
The published v0.9.0 wheel does not include the weighted operator used here. From the checkout root:

```powershell
python -m pip install ".[docs]"
python examples/spatial-diagnostics/run_example.py output/spatial-demo
cfdpaper write . --artifact results-section --package output/spatial-demo/section --docx --layout near-reference --output output/spatial-demo/spatial-diagnostics.docx
```

The example requires a new output directory and DOCX export requires a new file path.
Add `--pdf-preview` to the `cfdpaper write` command if LibreOffice is installed for PDF preview.
For an installed wheel and a separately copied example directory, run `run_example.py` from that
directory and use the same `cfdpaper write` command. DOCX export uses `write`, not root `export`.

Outputs include source tables, both calculation results, the portable writing
package, Markdown/section JSON and a figure delivery with SVG/PDF/PNG/TIFF plus
its local runnable script and unchanged CSV. Move the entire output directory to
continue elsewhere. Reassemble from `section-input/writing` and
`recorded-host-draft.json`; `section/` is the assembled output, not the input package.
Rerun the exported local `plot_wall.py` with its `source-data.csv` after local edits.

The figure is 160 mm wide with 9 pt labels at that width. Times New Roman falls back
to DejaVu Serif when unavailable. The DOCX uses the normal manuscript renderer:
two-character first-line body indentation, zero before/after body spacing and
independent caption/table styles. Inspect actual rendered pages before delivery;
software assertions do not prove visual or scientific quality.
Numeric column headers use the same alignment as their values. Source-bound absolute-temperature
means display °C and spatial temperature SD displays K; measure sums retain mm² or mm³.

## Fresh host attempt versus recorded replay

Default execution replays the supplied recorded proposal and guided host draft.
It does **not** invoke a model or independently rediscover the finding on each run.
For a new host attempt:

```powershell
python examples/spatial-diagnostics/run_example.py output/fresh-spatial --prepare-only
```

Give only `output/fresh-spatial/materials/host-task.md` and its linked inputs/skills
to the host, without this README or `recorded/`. Retain its proposal and first draft
before supplying feedback. `--writing-only --proposal <proposal.json>` prepares a
new writing package with the example map; `--draft <draft.json>` supports replay of
a returned draft. This helper expects the example's two candidate IDs; it is not a
general proposal CLI replacement.

The stored proposal came from an isolated initial attempt. The stored prose is a
guided continuation after a controller supplied the map and improved reusable skill
guidance. Only obsolete pending-figure metadata was adjusted for this public replay;
the numerical bindings and manuscript prose were retained. Original drafts remain
separate in local development records. This is one guided example, not a blind
cross-project quality benchmark.

## Known answers and limits

| Field | Wall mean (°C) | Wall spatial SD (K) | Volume mean | Volume spatial SD |
|---|---:|---:|---:|---:|
| Reference | 45.6 | 2.9393876913 | 0.4 | 0.2121320344 |
| Modified | 43.4 | 5.3516352641 | 0.4 | 0.0707106781 |

Both wall measures are 10 mm²; both volume measures are 4 mm³. Domain coverage,
facet constancy and the physical interpretation are explicitly supplied, not
inferred from column names. Spatial SD is not uncertainty in a mean. The current
operator supplies mean, SD and measure sum; extrema, threshold fractions and
composition of calculated outputs are not added by this example. The terminal
hot-region explanation uses the CSV and actual field map, not a new extremum binding.
