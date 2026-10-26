# Constructed reports → complementary response panels → Word

This portable example uses **synthetic, illustrative readings**, not private cooling results or
P04 data. It requires no solver, API key or model service. It exercises the installed `report_task`
entry point with three cases, two temperature statistics and two pressure differences.

```text
python -m pip install "PATH_TO_MATCHING_WHEEL[docs]"
python /path/to/bound-response-report/run_example.py /path/to/new-output
```

The output directory must be new. Copy this example directory anywhere writable; no checkout path
or repository data is needed. `DejaVu Serif`, bundled with Matplotlib, makes the default typography
portable. Actual journal figures can set an available journal font in `figure_plan.style`.

Open `candidate/manuscript.docx` and inspect the figure at
`candidate/workspace/sections/results/sources/report-figure/evidence-panels.png`.
The same directory contains the source-data CSV, locally runnable `plot.py`, editable SVG/PDF and
high-resolution TIFF. The two panels deliberately separate interface-temperature response from
the inlet–outlet pressure response rather than overlay unlike units. Shape and color distinguish
the two series within each panel. Lines connect discrete cases; there is no fit or smoothing.

The script first prepares a normal report workspace, then supplies example author prose in the
Methods, Results and Discussion drafts and calls the same product entry point to export Word.
Bound values, the native table, figure and caption consume the same calculations. The facet maximum
is not renamed a junction temperature; pressure differences retain their area-weighted section
supports and do not automatically become pumping power. `raw/method.md` gives the definitions.

For a real task, omit `_example_drafts`: the host/author reads `prepared/workspace/TASK.md`, inspects
the generated preview, fills the normal drafts and records actual image observations. The product
does not infer a mechanism from two scalar curves. Its source binding reduces transcription work;
scientific interpretation and final page inspection remain part of the author's workflow.

To continue after editing retained source reports or an author-local plotting script, call
`report_task(output=FRESH_DIRECTORY, workspace=CURRENT_REPORT_DIRECTORY,
drafts=CURRENT_REPORT_DIRECTORY/workspace/drafts.json)`. The current report directory is
`candidate/` here. Keep the original candidate; a source change can require interpretation changes
as well as bound-number updates. The separate `report-writing` example demonstrates a retained-source
refresh with an explicit reference denominator and native equation.
