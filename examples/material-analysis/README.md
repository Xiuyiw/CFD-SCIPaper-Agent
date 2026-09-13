# Existing materials to an analysis and a results subsection

This example starts with a CSV and a short method note, not a prebuilt
scientific-records envelope. The numbers are synthetic. The offline replay contains
recorded host responses; it is a reproducible software example, not a test of autonomous reasoning.

## Try the host-assisted route

Use version 0.6.0 or later with the `docs` extra. Replace `STUDY` with a
folder of exported CSV, readable method notes, and optional existing figures.
Use fresh output directories (preferably outside STUDY, to avoid profiling prior outputs).

```text
cfdpaper inspect STUDY --materials --output profile
cfdpaper plan STUDY --artifact analysis --question "Explain the observed thermal response" --output analysis-materials
```

Give your local host AI `analysis-materials/host-task.md`. It reads the sources and
proposes one to three useful analyses in `proposal.json`; you choose an ID and answer
only essential definition questions. You do not need to write the JSON yourself.
The example/schema describes the supported population and partition calculations.
Unknown units, statistical domains or incomparable cases must be resolved for the selected analysis.

```text
cfdpaper plan STUDY --artifact analysis --package analysis-materials --proposal proposal.json --select CHOSEN_ID --output selected
```

The selection produces recomputed results and `selected/section-input/writing/TASK.md`.
The host sets `presentation` to `plot`, `prose`, `table` or `custom`, with a reason grounded
in what the reader needs to understand. `plot` produces four formats and a local plotting
entry point. Other choices preserve the calculated evidence without forcing a plot.
`table` asks the host for a native table in its draft; `custom` leaves the proposed figure
as an unfinished production task, not a substitute default scatter plot. Give the task to your host to
write `draft.json`, then assemble and inspect the actual document:

```text
cfdpaper write STUDY --artifact results-section --package selected/section-input/writing --draft draft.json --output section
cfdpaper write STUDY --artifact results-section --package section --docx --layout near-reference --output section.docx
```

Figure labels are grouped by the same calculation, quantity and unit, not by units
alone. The generated categorical plots are an editable starting point. The host
still chooses useful evidence and writes the scientific interpretation; the software
does not infer a mechanism merely because a calculation ran.

The material package includes the current analysis and figure-selection Skills, so an external
host does not depend on this repository's chat history. A sparse contrast may be better in text
or a compact table; a mechanism comparison may need complementary quantities or custom panels.
Selecting a presentation is not evidence that its scientific or visual quality has been approved.

Use a candidate's optional `style` object to carry author/template choices into the writing
package and DOCX. Body defaults are `body_first_line_indent_chars: 2`,
`body_space_before_pt: 0`, `body_space_after_pt: 0`. Override those fields for another template.
`space_after_pt` remains the existing non-body spacing setting; `line_spacing` is independent.
No whitespace is inserted to indent paragraphs, and captions/tables/headings do not inherit it.

For new data, rebuild the analysis and writing package in a new output directory.
The preserved plotting entry point can be edited locally; rerunning only that script
updates figures, **not** an already assembled manuscript or its copied source snapshot.

## Reproduce the synthetic document offline

```text
python examples/material-analysis/run_example.py demo-output --pdf
```

Omit `--pdf` if LibreOffice is unavailable; the editable DOCX remains usable.
The default recorded choice is `presentation: "table"`: one native, editable Word
table reports wetted area, integrated heat rate and mean heat flux for both configurations.
The six values are calculated from the source CSV and bound with `{{value:ID}}` tokens
in both the table and prose. Table 1 shows the complementary quantities together:
Reference is 5 m², 50 W and 10 W m⁻²; Modified is 10 m², 70 W and 7 W m⁻².
The larger integral therefore coexists with lower transfer per unit area.

Default outputs include original source copies, calculation results, the recorded
proposal/draft, the writing package, assembled Markdown/JSON, and an actual DOCX
with no placeholder figures. Body paragraphs use the editable two-character first-line
indent and zero before/after spacing described above; the table and caption retain
their own formatting.

To exercise the existing discrete plotting path instead, use a separate output directory:

```text
python examples/material-analysis/run_example.py demo-plots --presentation plot --pdf
```

This optional mode exports three separate quantity comparisons (area, heat rate and
mean flux), each as SVG/PDF/PNG/TIFF with source data and a local plotting entry point.
It demonstrates the available renderer; the compact table is the default for this
six-value comparison. Read the argument and inspect the actual document before reuse.
