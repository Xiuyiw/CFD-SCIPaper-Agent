# Two figures to an editable scientific subsection

Install with `python -m pip install -e ".[docs]"` from the repository root.
The following commands create fresh directories relative to your current directory:

```text
python examples/section-writing/prepare_example.py demo-source
cfdpaper write demo-source --artifact results-section --section-input demo-source/input.json --output demo-package
```

Give `demo-package/TASK.md` and its entire folder to your host AI, with the installed
`cfd-evidence-writing` skill. It reads the supplied images and evidence, answers the
scientific question, and writes a JSON draft. For a reproducible tutorial instead,
the next command uses the provided, explicitly authored `sample-draft.json`:

```text
cfdpaper write demo-source --artifact results-section --package demo-package --draft demo-source/sample-draft.json --output demo-section
cfdpaper write demo-source --artifact results-section --package demo-section --docx --output demo-section.docx
```

The source is an analytical laminar pipe reference, **not CFD validation data**.
It compares pressure drop with fully developed Nusselt number under fixed properties
and uniform wall heat flux. The script supplies CSV, runnable source, SVG/PDF and
PNG/TIFF. Existing files are not overwritten; choose a new output for each revision.

## Your own results

Use the example `input.json` as the format reference. Supply a question, one or more
PNG/JPEG/TIFF figures, evidence with exact source locations, and subsection duties.
Evidence can be observations, metrics, interpretations, or verified literature.
Multiple figure and evidence records can come from different analyses. Define the
comparison, normalization, sampling and control volume before inferring mechanisms.
The adapter does not read arbitrary solver data or establish the physical meaning of
declared source files. Explicit `source_files` under relative `sources/` paths travel
with the writing and review packages.

### Compute exported tables before writing

Optional `table_calculations` in `input.json` runs small deterministic calculations
on CSV exports. The host selects columns from the actual files and records the
domain/units; the author need not fill a separate analysis questionnaire. For example:

```json
{
  "table_calculations": [
    {
      "id": "outlet-spread",
      "source": "sources/outlets.csv",
      "operation": "population",
      "columns": {"value": "mass_flow"},
      "units": {"value": "kg/s"},
      "group_by": "case",
      "domain": "Net mass flow per outlet, all outlets, equal outlet weights"
    },
    {
      "id": "surface-heat",
      "source": "sources/regions.csv",
      "operation": "partition",
      "columns": {"area": "area", "rate": "heat"},
      "units": {"area": "m^2", "rate": "W"},
      "group_by": "case",
      "domain": "Disjoint wall regions; integrated heat into the fluid"
    }
  ]
}
```

Preparation writes `table-results.json`; assembly recomputes it from the copied
CSV and includes it in the external review packet. Calculation sources are copied
automatically. Each group retains its CSV record numbers (header is record 1).
`population` returns count, sum, mean and population CV (standard deviation divided
by absolute mean, equal record weights). `partition` returns summed area/rate,
regional and total mean flux, and rate shares. Flux units are rate units divided
by area units; shares and CV are dimensionless. Signed rates are retained, and
zero total rate or zero mean leaves shares or CV undefined rather than inventing zero.

There is no unit conversion. Blank values make only the affected group unavailable;
invalid numbers or missing columns require correction. A sum of supplied regions
does not establish that they cover the entire physical surface. Nor does a CV or
heat partition prove a causal mechanism. To quote a computed result, use metric
evidence with `result_ref` instead of a manually entered `value` or `unit`:

```json
{
  "id": "spread-A",
  "kind": "metric",
  "text": "Outlet-flow variation for case A",
  "source": "sources/outlets.csv",
  "result_ref": {
    "calculation_id": "outlet-spread", "group": "A", "field": "cv",
    "places": 1, "percentage": true
  }
}
```

`{{value:spread-A}}` then reads the current CSV calculation during assembly.
Regional `shares` and `regional_flux` also require `source_record` (header is
record 1). Other allowed fields are count/sum/mean, area/rate/mean_flux; the
operation determines which fields apply. Missing values do not fall back to old
numbers. `section.json` retains the unrounded value, units and supporting records.
Groups match exactly; a regional share retains all group records supporting its denominator.

In the host draft, `{{value:ID}}` inserts either the declared metric value or the
current `result_ref` calculation, with its unit; `{{figure:ID}}` resolves a figure reference;
`{{cite:ID}}` numbers supplied
literature in first-use order. Unknown tokens or missing declared coverage are
rejected. Free prose still needs scientific reading: structural checks do not
prove a mechanism or verify a manually typed number. No literature is invented.

## Page layout, tables and equations

```text
cfdpaper write demo-source --artifact results-section --package demo-section --docx --layout near-reference --pdf-preview --output demo-section/preview.docx
```

The default `after-text` layout starts each figure/caption pair on a new page;
`near-reference` places each figure once after its first referring paragraph.
Optional PDF preview uses an installed LibreOffice on an isolated copy; without
it, export the retained DOCX to PDF in Word. No office software is installed by the tool.

Optional input `style` sets page dimensions/margins in mm, font sizes in pt,
spacing and preferred figure width. The defaults are A4, 25 mm margins,
11 pt Times New Roman text and 10 pt captions. Figure `sizing` can supply
`source_width_mm`, `target_width_mm` and `minimum_source_font_pt`. Use the
actual exported width, not a canvas width before cropping. Each DOCX has a
`.layout.json` companion reporting actual embedded width, effective dpi and
known minimum font size after scaling. Unknown source font size stays unknown.
Declared text below the configurable 8 pt default stops export with an adjustment
suggestion; increasing image dpi does not enlarge the printed text.

The example draft includes optional `tables` and `equations`. Tables use
`table_id`, `caption`, `columns`, rectangular `rows`, `after_section_id` and
`evidence_ids`; optional `column_widths_mm`, zero-based `numeric_columns` and
`note` control simple table presentation. Cells may contain the same value tokens.
DOCX tables are editable, with three horizontal rules and repeating headers.
`after_section_id` must equal the input `section_id`.

Equations use `equation_id`, `evidence_ids` and an `expression` of structured
nodes: text/symbol, row, sub, sup, subsup, fraction and sqrt. They become editable
Word equations (OMML), not screenshots or literal LaTeX. Use `{{table:ID}}` and
`{{equation:ID}}` for references. The packaged writing skill contains compact
examples of these finite structures; arbitrary LaTeX parsing is not supported.
For mathematical notation inside prose, declare a paragraph's `inline_math`
dictionary with the same node structure and use `{{math:local_id}}` in its text.
This produces editable inline Word math without guessing which underscores or
ordinary words should become subscripts.

## Review and editing

`demo-section/section.md` and DOCX contain prose and captions. Unresolved methodology
questions belong in `evidence-notes.md`. `review-packet/` contains the manuscript,
images, structured inputs, draft and review prompt for a separate external AI.
Declared source files and computed table results are included when supplied at preparation.

Import its response in this format:

```json
{"suggestions": [{"target": "paragraph 1", "comment": "Clarify the comparison", "recommendation": "State the fixed geometry"}]}
```

```text
cfdpaper write demo-source --artifact results-section --package demo-section --review review.json --output suggestions.json
```

Importing suggestions neither revises nor approves the manuscript. Apply useful
suggestions in a new draft and assemble a new output. Author edits to an exported
DOCX are not round-tripped automatically: keep that file as the author version.
The preview is an editable subsection, not a journal-specific typesetting template.
