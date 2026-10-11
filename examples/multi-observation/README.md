# Connected multi observation tutorial

This public example uses invented records and recorded prose. It demonstrates the
software chain, not an independent AI performance test, simulation or experimental
validation. Timing agrees with supplied illustrative ranges while one temperature
observation exceeds its declared bound. The three finite panels show the saved
temperature profile, timing and temperature comparisons on separate unit axes.

From the repository or an installed product environment:

```powershell
python examples/multi-observation/run_example.py output-multi-observation
```

Use a fresh output directory. The script executes `prepare_analysis`,
`compile_analysis`, `build_analysis_section`, `prepare_manuscript_seed`,
`assemble_manuscript` and `export_section_docx`. Its recorded proposal and four
drafts are copied to the output. Methods defines the window and operators; Results
uses source-bound numbers; Discussion and Conclusions bind back to Results rather
than copying numeric values. No literature was supplied and no citation is invented.

`inputs/method.md` documents the provenance and observation supports. The exact
0–5 s profile excludes the saved 9 s samples. Event times are independent records,
not interpolated threshold crossings. The default plot prefers Times New Roman
with an explicit serif fallback; the exported local `analysis/figures/plot.py`
contains centralized `PLOT_STYLE` parameters and needs only matplotlib and Pillow,
not this package. It reproduces SVG/PDF/PNG/TIFF from the exported source CSV,
retains source locations and runs actual layout/raster checks. Preserve local edits.
This tutorial demonstrates an explicit local height adjustment to 135 mm for the
three panels, retaining the 160 mm width, declared axis units and original font
sizes; its refreshed layout checks and plot style travel with the exports.

For a separate bundled document runtime, first use `--no-docx` and then call
`export_section_docx` on the returned manuscript directory in that runtime. The
DOCX preserves editable paragraphs and a native inline equation, two-character
body indentation and zero before/after body spacing. Check the actual rendered
pages before using it. Font fallback and export success alone do not certify
publication layout.

Copy the entire `workspace` (or assembled `manuscript`) directory for continuation.
Use its own portable `drafts.json` to reassemble into a fresh directory; do not use
the historical outline paths. The source tables are never modified.
