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
