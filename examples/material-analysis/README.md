# Existing materials to an analysis and a results subsection

This example starts with a CSV and a short method note, not a prebuilt
scientific-records envelope. The numbers are synthetic. The offline replay contains
recorded host responses; it is a reproducible software example, not a test of autonomous reasoning.

## Try the host-assisted route

Use version 0.6.0 or later with the `docs` extra. Replace `STUDY` with a
folder of exported CSV, readable method notes, and optional existing figures.
Use fresh output directories (preferably outside STUDY, to avoid profiling prior outputs).

Python and MCP callers can pass a host-selected proposal object directly to
`run_analysis_task(package, proposal, candidate_id, output)`. It uses the same
proposal schema and calculation checks as the JSON-file route, without writing a
temporary proposal file. The returned writing package already contains computed
bindings; the host should not transcribe the numbers. Existing CLI file inputs remain supported.
Material inspection and literal search also read `.c`/`.h` method and UDF sources
with line locations. Source presence does not establish that a function was loaded,
hooked or executed in a saved solver case.

```text
cfdpaper inspect STUDY --materials --output profile
cfdpaper plan STUDY --artifact analysis --question "Explain the observed thermal response" --output analysis-materials
```

Give your local host AI `analysis-materials/host-task.md`. It reads the sources and
proposes one to three useful analyses in `proposal.json`; you choose an ID and answer
only essential definition questions. You do not need to write the JSON yourself.
The example/schema describes the supported population and partition calculations.
Version 0.10.0 and later also support explicit spatial weighting, described below.
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

The material package includes a connected-workflow entry and its intake, analysis,
figure and writing Skills with their references. Start with `skills/cfd-paper-workflow/SKILL.md`
and load only the relevant specialist instructions, rather than reading the whole bundle.
An external host does not need this repository's chat history. A sparse contrast may be better in text
or a compact table; a mechanism comparison may need complementary quantities or custom panels.
Selecting a presentation is not evidence that its scientific or visual quality has been approved.

## Derive on each face before averaging

Use `activated_response_mean` when the study defines a dimensionless, thermally activated
response on individual faces. For concentration `C`, reference `C_ref` and absolute
temperature `T`, the supported form is `[a (C/C_ref)^p exp(-B/T)]^q`.
The output is the area-weighted mean of those face responses, **not** the response
evaluated at the mean concentration and temperature. For example, two equal-area faces
with concentration ratios 1 and 3, a square law, unit prefactor, no temperature dependence
and unit outer exponent give a mean response of 5, not 4.

Supply aligned case and face identities, concentrations on the same declared basis as the
reference, temperatures in kelvin and retained areas in square metres. A face with zero
concentration is still part of the physical support. The calculation does not infer constants,
repair missing faces or establish that the selected law is scientifically appropriate.
For previously exported scalar fields that need no per-face transformation, use the existing
weighted calculation below.

## Spatially weighted records (v0.10.0 and later)

Use `weighted_population` when exported element values have corresponding positive
areas or volumes. For example, a calculation on absolute wall temperatures can declare:

```json
{
  "id": "wall-temperature",
  "source": "sources/facets.csv",
  "operation": "weighted_population",
  "columns": {"value": "T [degC]", "weight": "area [m2]"},
  "units": {"value": "degC", "weight": "m2"},
  "weight_kind": "area",
  "quantity_kind": "absolute-temperature",
  "domain": "Supplied non-overlapping wall facets",
  "group_by": "case"
}
```

This is the calculation portion of a proposal; the host must also provide its
actual `definition_source`, comparison scope and element identity, as in the existing
proposal schema. Use `weight_kind: "volume"` and a cubic measure unit for cell volumes.
Supported measure units are m, cm or mm squared/cubed, including `m2`, `m^2`, `m²`
and their cubic equivalents. Units are not converted. Point counts are not spatial weights.

The available result fields are `weighted_mean`, `weighted_std` and `weight_sum`.
Mean = sum(w*x)/sum(w); spatial population SD = sqrt(sum(w*(x-mean)^2)/sum(w)).
For values 1 and 3 with weights 1 and 3, these are 2.5, sqrt(0.75) and 4.
Mean temperature retains the supplied Celsius or Kelvin scale; its SD is reported in K.
For K, specify `absolute-temperature` or `temperature-difference`; non-temperature
quantities use `ordinary`. No temperature reference is needed for these statistics.

Use the result fields in existing `result_ref` bindings for both prose and native
tables. A blank value leaves its group unavailable; invalid or non-positive weights
must be corrected rather than dropped. The SD describes variation of the supplied
element values, not solver uncertainty or unresolved variation within each element.
The physical coverage of those elements remains part of the method definition.

Choose the statistics that answer the question: a lower mean can coexist with a larger
spread or a higher maximum. Report their relationship rather than interpreting every
lower statistic as better overall performance. This operation does not calculate maxima,
flux integrals or CV; use separately sourced evidence where those quantities are needed.

Use a candidate's optional `style` object to carry author/template choices into the writing
package and DOCX. Body defaults are `body_first_line_indent_chars: 2`,
`body_space_before_pt: 0`, `body_space_after_pt: 0`. Override those fields for another template.
`space_after_pt` remains the existing non-body spacing setting; `line_spacing` is independent.
No whitespace is inserted to indent paragraphs, and captions/tables/headings do not inherit it.

For a fresh analysis, build the analysis and writing package in a new directory. Running a
plot script by itself **does not** update an assembled manuscript. When the figure already
has an author's layout, use the linked section workflow below to update the data,
artwork and author-written text together.

## Refresh an author's figure, caption and section

For a runnable, synthetic before/after, run
`python examples/material-analysis/run_linked_refresh.py demo-refresh`. Its source table
contains regions with different areas. Changing one regional heat rate changes the
integrated rate, its plot, its bound caption and its paragraph. The area comparison is
not redrawn. A locally refined plot colour and wording in the other paragraph survive.

For an existing study:

1. Start from the existing `section-input/input.json`, its declared `sources/`, and the
   **current** author-local `draft.json`. Captions and paragraphs use the existing
   `{{value:...}}` bindings. Do not copy old computed numbers into the prose. Add the
   actual plot script, named input table and required helpers. Set each figure's
   relative preview path in `input.json` to its real recipe output and preserve its sizing.
2. Use the existing `figure-recipes.json` format, with one `section_id` and `figure_id`
   per owned figure. Add `result_tables` to the recipe, e.g.
   `[{"path":"rate/display.csv","row_key":"case","columns":{"reading":{"unit":"W","by_row":{"Reference":"rate-Reference","Modified":"rate-Modified"}}}}]`.
   The table is a declared recipe **input**, distinct from the raw sources. Each bound
   column must cover its actual row keys; a genuinely fixed cell (e.g. a reference
   change relative to itself) can be declared as `"fixed":{"Reference":0}` alongside
   `by_row`. Only named cells are filled; row order, unbound columns and author code
   are retained. Scientific definitions, the percent denominator and raw numerical
   precision come from the calculation, not the author's tick labels. Any display
   processing done by a script is not a new scientific observation.
3. Build a fresh candidate:

       cfdpaper refresh-section author-workspace --output before --docx
       cfdpaper refresh-section current-author-workspace --baseline before --output after --docx

   For the second call, continue from a copy of `before/workspace` with the current
   sources/author edits. The program executes only **explicitly trusted local scripts**;
   it does not import or discover scripts in manuscripts or archives. Provide their
   table, assets and dependencies. The build is published only after its figure and
   text assembly succeeds. The `section.docx` is a new section candidate, not an
   in-place edit of an arbitrary Word document.

The host/Python/MCP entry is `refresh_section_task`. Read `refresh.json` for changed
results, changed images and the specific readers to revisit. Unchanged calculation
inputs and figure dependencies need no recalculation or redraw on a prose-only return.
Figures without a linked recipe are listed separately as unlinked; retaining an image or
an unbound data column does not verify it against a changed source.
An image change invalidates its previous visual reading, not the wording in other
paragraphs. The tool never infers a new mechanism. Where wording depends on an
ordering, declare it in the optional `reading-relations.json`, e.g.
`[{"kind":"paragraph","id":"rate","left":"rate-Modified","op":">","right":"rate-Reference"}]`.
A reversal stops this build and names the exact object and its new values. Edit just
that interpretation in the author's current draft. Only declared conditions are checked;
free prose still needs a reader.

### When the physical definition changes

Use the same baseline. Keep the author's latest prose in the current workspace, update
the physical declaration (for example, filter the actual rows to a named region), then:

    cfdpaper refresh-section current --baseline before --inspect-change --output inspection
    cfdpaper refresh-section current --baseline before --reconcile edited.json --output revised --docx

Inspection runs the scientific calculations but no plot scripts. Copy
`inspection/reconcile.json` to `edited.json`. For each affected reader supply the
actual `after` text, or explicitly retain its present text. Review the figure's
labels, units and accepted local script; fill in `reading` with what that figure now
represents. For an affected native table or equation, supply the corresponding
retained or revised object. Keep `basis` and `before` as returned: an intervening
edit to a targeted object or its data requires reading the current version, not replacing it.
The second command stages revisions in a fresh copy, executes the affected recipe even
if the numbers happen to agree, and reassembles bound text. A relabelled domain alone
does not change which data were sampled; define the actual selection and weighting.

For a section that compares competing explanations, use `input.json`'s optional
`mechanism_questions`, e.g. `[{"question":"Does the total change hold in the selected
region?","diagnostics":["total","region","opposite-region"],"interpretation":"Compare
matched domains and the opposite-region response."}]`. IDs refer to actual calculations
or bound evidence. The context returns their values, scopes, units, sources and declared
evidence roles, including unchanged counterexamples; the host writes the interpretation.
An identity and a second diagnostic of the same numerical solution are not new measurements.

Panel source roles are optional declarations in `display-evidence.json`: each row
locates a figure, panel and actual source. A raster cache, smoothed representation or
compressed difference can illustrate a trend, not supply a raw quantitative validation.
Where comparable field panels use a common color scale, describe its physical knots,
color positions and clipping; compare a fresh visual reading at the real target width.
These checks cover the declared evidence, not arbitrary author code or an image's scientific truth.

## Continue into a manuscript

The [two-section manuscript tutorial](MANUSCRIPT.md) reuses this example's
generated section input and all six result bindings, adds Methods with native
Word mathematics, and exports an editable manuscript. It also demonstrates source
updates without replacing the original candidate. For host-led work, start with
the [connected workflow skill](../../skills/cfd-paper-workflow/SKILL.md).

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
