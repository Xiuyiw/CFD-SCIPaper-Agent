# Source-bound research-expression example

This small, fully synthetic example connects original face temperatures and separate
local energy tables to a focused two-panel figure, disclosed example-author prose,
two native Word tables and an editable Word research note. No solver, model API,
private project, network access or manuscript template is required.

From the matching source checkout, install and run:

```console
python -m pip install ".[docs]"
python examples/research-expression/run_example.py output/research-expression
```

Use a new output directory. The command creates both the first candidate and one
normal source-driven refresh:

- `materials/`: original constructed NPZ face arrays, local-budget CSVs and definitions.
- `candidate/manuscript.docx`: first editable Word note, with one composite figure
  and two native tables. Body, captions and table cells resolve source-bound values;
  shared units appear in table headers rather than every numeric cell. Explicit
  Results paragraph IDs and `block_order` place the original-mean table after the
  whole-interface comparison, then the regional/budget argument, its composite
  figure and the local-accounting table. Editable Word content controls retain
  these ordered blocks and the native tables inside them.
- `candidate/workspace/sections/results/figures/diagnostics/`: `thermal-budget`
  SVG/PDF with editable text, PNG/TIFF previews, original-value source CSV,
  paired-change CSV, checks and a runnable author-local `plot.py`.
- `author-working/`: an independent author copy. The example changes its local
  tick font to 8.5 pt and adds 1 K to both prescribed A1 face temperatures.
- `refreshed/manuscript.docx`: rebuilt values, figure and tables, retaining the
  author-local script and original draft files. `refresh.json` and `CHANGES.md`
  identify changes that need interpretation review.

For Structure A, the original whole-interface means are 317.500 and 319.750 K;
their comparison-minus-reference change is 2.250 K. The refresh changes the latter
mean to 320.750 K and its paired change to 3.250 K. These values are computed from
the current original arrays, not entered into the final manuscript or source CSV.
The first materials and first candidate remain unchanged.

## What the example expresses

Each of two reference–comparison pairs uses the same two original rectangular
faces, with areas of 0.0001 and 0.0003 m². The fixed heated footprint is exactly the
first face. Its boundary follows a face edge, so whole-face centroid assignment is
exact for this construction; it does not demonstrate polygon clipping. Physical
area weighting lets footprint cooling coexist with whole-interface warming.

The energy tables are separate prescribed local-accounting examples. Positive
input enters the volume and positive output leaves it; source and storage are
explicitly zero. The derived remainder is input minus output, not an independently
measured lateral flux or numerical convergence residual. Temperatures and budgets
are not linked by a transport solution. Their juxtaposition demonstrates research
organization, not a causal mechanism, real CFD validation or a device ranking.

The host/author supplies the question, short argument and figure choice. The product
calculates and binds evidence; it does not infer the scientific interpretation.
`study.selected_figures=[]` keeps the original field map and distribution available
in the workspace without putting every generated diagnostic in the paper. The single
published composite uses explicit `pair_id`/`role`, regional `view="paired_change"`
and budget `view="decomposition"` through `attach_research_diagnostics(...,
combine=True, figure_id="thermal-budget")`. Its `field_difference` calculations bind
both original means and their derived changes. `SectionTable.column_units` declares
the shared K/W headers.

## Continue with author edits

Start from the latest candidate's entire `workspace/`, not from the generator.
Edit the local `sections/results/figures/diagnostics/plot.py` for style. Run that file
directly to redraw the composite, or build a fresh complete candidate:

```console
cfdpaper research --workspace output/research-expression/author-working --output output/research-expression/next-candidate --baseline output/research-expression/candidate
```

Read the source definitions, actual figure preview and rendered Word pages, then
revise the prose if changed evidence alters the argument. The exported Word text
and tables are editable, but Word-only edits must be reconciled into the managed
drafts before a rebuild. The example does not automate that editorial decision.

## Original surfaces, author style and a changed interpretation

The separate linked-surface example uses two synthetic 64-face temperature fields
and one three-panel figure: two original-face maps on a shared Kelvin scale, then
fixed-region contributions to the mean change. It needs the geometry and Word extras:

```console
python -m pip install ".[geometry,docs]"
python examples/research-expression/run_linked_surface_example.py output/linked-surface
```

Use a new output directory. `candidate/manuscript.docx` is the initial host-authored
note. Its 160 by 110 mm figure links the actual polygons, a fixed quarter-area footprint
and its complement; `candidate/workspace/sections/results/figures/diagnostics/`
retains editable SVG/PDF, PNG/TIFF, both original-field and contribution CSVs and
the author-local `plot.py`. Source data are prescribed static values, not a solver
solution. The displayed pixel blocks are the original faces, not interpolated data.

The script then copies the candidate workspace to `author-working/`, changes only
the local script's tick font to 9 pt, and subtracts 1 K from the copied comparison
field. A normal baseline refresh creates `refreshed/`: the whole-surface change
reverses from +0.500 to -0.500 K, while the author script and draft wording survive.
`CHANGES.md` and `refresh.json` request review of affected current passages and
captions. `refreshed-response.json` retains the current bound readings and the
still-unrevised caption; it does not automatically endorse a new interpretation.

Finally, the example host supplies `host-revision.json` through the existing
explicit revision API. Only the affected Results paragraph and caption are
replaced; the figure ID `surface-change`, all source bindings and the unrelated
scope paragraph stay in place. `revised/manuscript.docx` is the resulting candidate,
and `revised/workspace/` is its continuation entry. The fixed-footprint and remaining-
surface contributions are now -1.250 and +0.750 K. These contributions compose a
temperature change; they are not heat flows or independently discovered mechanisms.
The script leaves figure observation status `not-viewed`: inspect the PNG and
actual Word pages before treating a particular run as visually reviewed.

The public entry uses an in-memory diagnostic object rather than a second JSON
proposal file:

```python
host_tools.research_task(
    output / "workspace",
    workspace=output / "prepared",
    diagnostics=diagnostics,
    diagnostic_figure={"surface_partition_panel": "surface-change"},
)
host_tools.research_task(
    output / "refreshed",
    workspace=output / "author-working",
    baseline=output / "candidate",
)
```

To check an installed wheel independently of the source import path, install that
wheel with `[geometry,docs]` in a fresh environment, copy only this example script
to a separate working directory, and run it there. It imports the installed
`cfdpaper` package and does not require repository fixtures or private files.
