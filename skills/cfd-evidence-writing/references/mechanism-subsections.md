# Figure-grounded mechanism subsections

Read this reference when drafting a results-section, after identifying its scientific question and
paragraph duties. Use the actual supplied evidence, not a fixed sentence template. A single figure
may support a complete argument; multiple figures should answer one question through complementary
evidence rather than repeat their captions.

## Establish what is known

Open each figure and distinguish visible features from author-provided descriptions. Record
`viewed` only after actual viewing; use `author-provided` or `not-viewed` otherwise. A contour can
show localization or redistribution without establishing a source-resolved budget or causation.
Read legends, normalization, axes and case definitions before comparing apparent color intensity.
If scales differ, colors alone do not establish a quantitative difference.

For each paragraph, choose its duty and evidence/figure IDs. Distinguish direct observations,
supplied metrics, interpretations and literature. Exact source locators identify declared evidence;
they do not certify that a source was independently checked. Do not invent missing quantities,
case comparisons, citations or boundary conditions.

## Build the argument from the physical question

For a single figure, identify the dominant spatial or parametric change, quantify it only where
supplied measurements permit, then connect it to a defensible balance or transport process. State
what the figure adds beyond its caption. Avoid describing every panel in plotting order.

For multiple figures, give each a distinct role: for example, a field identifies a spatial change,
a profile tests its location or extent, and a derived metric tests its magnitude. Explain agreement
or tension between them. Do not treat several correlated diagnostics of the same field as
independent verification. If a metric and the spatial field disagree, inspect their definitions
and sampling support before selecting the more convenient result.

Reason from the relevant mass, momentum, energy or species balance. Check the control volume,
boundary conditions, imposed forcing and comparison basis. Distinguish storage, transport and
source terms, and assess whether geometry, residence time or redistribution offers an alternative
explanation. Use causal wording only when the evidence separates the proposed mechanism from
credible alternatives; otherwise describe consistency or association. A larger indicator is not
automatically a better engineering outcome.

Select a few quantitative anchors that explain the observed change, rather than listing every
result. For example, stronger local source intensity may coexist with weaker downstream transport;
compare the integrated source and the relevant flux before attributing the difference to mixing.
If a normalized index rises while its absolute numerator falls, inspect the changing denominator
before describing stronger physical support. Use these comparisons when the supplied data support
them, not as a required paragraph pattern.

## Keep quantitative statements well defined

- A sum of cell-integrated rates differs from a sum of per-volume source densities; the latter
  requires cell-volume weighting to become an integrated rate. An area flux integral similarly
  needs the relevant area and normal direction.
- A sampled peak is not necessarily a continuous-field maximum. A local value is not a global
  balance. Missing data are not zero. Threshold sensitivity is not measurement uncertainty.
- Use consistent dimensions, reference scales and control-volume scope. Check mesh/time-step
  dependence, convergence and available validation before implying resolved accuracy.
- Preserve supplied values through `{{value:evidence_id}}`; use `{{figure:figure_id}}` and
  `{{cite:evidence_id}}` for figure and supplied literature references. Cite tokens require
  literature evidence. Declare each paragraph's referenced IDs, as described in `TASK.md`.
  Raw free prose is not numerically or semantically certified by successful assembly.

## Write for the reader, keep review work separate

Lead with the evidence-supported finding, develop its physical interpretation, and finish with the
implication relevant to the section question. Vary paragraph structure with the evidence rather
than forcing observation, mechanism and implication into identical three-sentence blocks. Prefer
specific physical relationships to generic claims such as improved mixing or enhanced performance.

Put source-access gaps, requests for additional analysis and reviewer questions in `evidence_notes`.
Keep qualifications necessary to interpret a scientific claim in the manuscript itself; separate
notes are not a license for overstatement. Captions define variables, conditions and visual encoding
without duplicating the discussion. Before assembly, check every duty, comparison, quantitative
statement and image-observation status. Human review remains responsible for the argument.

## Exported table example

This example is included with the installed skill; it needs no repository examples directory.
Merge this fragment into a section input containing a declared figure `f1`, title and question.
Paths are relative to that input JSON. Select column roles and units from the actual export and
methods. The two metric records bind directly to the calculations, so no manual values are needed:

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
      "domain": "Net mass flow per outlet; all outlets with equal record weights"
    },
    {
      "id": "surface-heat",
      "source": "sources/regions.csv",
      "operation": "partition",
      "columns": {"area": "area", "rate": "heat"},
      "units": {"area": "m^2", "rate": "W"},
      "group_by": "case",
      "domain": "Disjoint supplied wall regions; integrated heat into the fluid"
    }
  ],
  "evidence": [
    {
      "id": "outlet-cv",
      "kind": "metric",
      "text": "Population CV of outlet mass flow for case a",
      "source": "sources/outlets.csv; case a; all outlet records",
      "result_ref": {
        "calculation_id": "outlet-spread", "group": "a", "field": "cv",
        "places": 1, "percentage": true
      }
    },
    {
      "id": "region-share",
      "kind": "metric",
      "text": "Heat share of the second supplied region for case a",
      "source": "sources/regions.csv; case a; record 3 relative to the group total",
      "result_ref": {
        "calculation_id": "surface-heat", "group": "a", "field": "shares",
        "source_record": 3, "places": 2, "percentage": true
      }
    }
  ],
  "duties": [
    {
      "purpose": "Report outlet variation and the selected regional heat contribution",
      "evidence_ids": ["outlet-cv", "region-share"],
      "figure_ids": ["f1"]
    }
  ]
}
```

For a small synthetic example, `sources/outlets.csv` contains:

```csv
case,mass_flow
a,1
a,3
```

and `sources/regions.csv` contains:

```csv
case,area,heat
a,2,8
a,3,6
```

Preparation copies the calculation sources and writes `table-results.json`; assembly recomputes
from the copied CSVs and includes the report in the review packet. Read each report's domain,
units and group before choosing a result. CSV records count parsed records, with the header as
record 1; they are not physical line numbers when quoted CSV cells contain newlines.

`population` provides `count`, `sum`, `mean` and `cv` (population standard deviation divided by
absolute mean, equal record weights). `partition` provides total `area`, total `rate`,
`mean_flux`, `regional_flux` and `shares`. Here the mean outlet flow is 2 kg/s, CV is 0.5,
total heat is 14 W and total mean flux is 2.8 W/m^2. Regional fluxes are 4 and 2 W/m^2:
the higher local intensity and the larger area belong to different regions, so read both when
explaining their integrated contributions.

The host draft uses the same evidence IDs in prose and captions. This minimal synthetic draft
demonstrates the binding; develop the physical argument from the actual figures for a real study:

```json
{
  "title": "Outlet variation and regional heat contribution",
  "paragraphs": [
    {
      "text": "For case a, the outlet-flow CV is {{value:outlet-cv}}, and the second region contributes {{value:region-share}} of the supplied regions' total heat ({{figure:f1}}).",
      "evidence_ids": ["outlet-cv", "region-share"],
      "figure_ids": ["f1"]
    }
  ],
  "captions": {"f1": "Case a: outlet-flow CV {{value:outlet-cv}}; second-region heat share {{value:region-share}}."},
  "evidence_notes": [],
  "image_observations": {"f1": "not-viewed"}
}
```

Save the draft as `draft.json` and run the Skill's assemble command. Both prose and caption resolve
to `50.0 %` and `42.86 %` for these tables. Assembly recalculates from the current package CSVs,
so updated source values propagate to both locations. Set image-observation status according to
what was actually viewed when preparing a real draft.

`result_ref` requires `kind: "metric"`; omit `value` and `unit`, which come from the calculation.
Keep `source` as the human-readable locator. The assembled `resolved_values` retains the actual
CSV path, supporting records and raw number. Group names match exactly; omitted `group_by`
produces `all`. This grouping determines which records enter the denominator.
`regional_flux` and `shares` require `source_record` starting at 2; scalar fields omit it. A regional
flux cites that record alone, whereas the share of record 3 uses both records 2 and 3 in its group
total. Selecting the region identifies the numerator, not the full support of a share.

Count, CV and shares are dimensionless. Other units follow the declared roles; flux is written
as `(rate unit)/(area unit)`, without converting or simplifying units. `"percentage": true` applies
only to CV and shares, multiplies the original ratio once, then rounds to `places` (0–12).
It returns a numeric string and a separate `%` unit; do not multiply again or append another `%`.
Blank numeric cells leave the affected group unavailable. Zero mean or zero total rate leaves
CV or shares undefined. Correct missing columns and invalid values before using that result.
Partition totals describe the supplied records; establish surface coverage from the source
definition. Successful selection does not check manually typed numbers elsewhere in the prose.

## Optional tables, equations and document sizing

Add a table when exact comparisons help answer the question, or an equation when a quantity's
definition needs to be explicit. Merge this fragment into the draft above, with the input's
`section_id` set to `heat-results`:

```json
{
  "tables": [{
    "table_id": "t1", "caption": "Case a diagnostics",
    "after_section_id": "heat-results",
    "columns": ["Quantity", "Value"],
    "rows": [["Outlet-flow CV", "{{value:outlet-cv}}"],
             ["Second-region heat share", "{{value:region-share}}"]],
    "evidence_ids": ["outlet-cv", "region-share"],
    "column_widths_mm": [95, 55], "numeric_columns": [1],
    "note": "The heat-share denominator includes all supplied regions."
  }],
  "equations": [{
    "equation_id": "eq1", "evidence_ids": [],
    "expression": {"kind": "row", "children": [
      {"kind": "symbol", "text": "s"},
      {"kind": "text", "text": " = "},
      {"kind": "fraction", "children": [
        {"kind": "sub", "children": [
          {"kind": "symbol", "text": "Q"}, {"kind": "symbol", "text": "r"}
        ]},
        {"kind": "symbol", "text": "Q"}
      ]}
    ]}
  }]
}
```

Here `s` is the regional heat share, `Q_r` the selected region's integrated heat, and `Q` the
supplied-region total. Reference these objects in a paragraph with `{{table:t1}}` and
`{{equation:eq1}}`. IDs identify objects declared in this draft. Tables reuse `ManuscriptTable`:
`after_section_id` must equal the input `section_id`, every row must match `columns`, and cell
values are strings. `evidence_ids` declares the evidence used by value tokens in cells, caption
and note; values resolve through the same calculation references as prose. Optional column widths
are in mm; `numeric_columns` uses zero-based indices for right alignment.

Math nodes use `text` or `symbol` leaves with a `text` string. Composite nodes instead use
`children`: `row` in reading order; `sub` as [base, subscript]; `sup` as [base, superscript];
`subsup` as [base, subscript, superscript]; `fraction` as [numerator, denominator]; and `sqrt`
with one radicand. Equation `evidence_ids` similarly declares any value tokens used in leaf text.
These finite structures export as editable Word equations; they are not an arbitrary LaTeX parser.

For a variable or expression inside a sentence, declare `inline_math` on that paragraph and insert
`{{math:ID}}`. For example, using the regional-share evidence above:

```json
{
  "text": "The selected-region share is {{math:share}}.",
  "evidence_ids": ["region-share"], "figure_ids": [],
  "inline_math": {"share": {"kind": "row", "children": [
    {"kind": "sub", "children": [
      {"kind": "symbol", "text": "s"}, {"kind": "symbol", "text": "r"}
    ]},
    {"kind": "text", "text": " = {{value:region-share}}"}
  ]}}
}
```

`{{math:share}}` inserts editable inline OMML from this paragraph's nodes; `{{equation:eq1}}`
inserts a numbered reference to a declared equation. Subscripts are explicit nodes, not inferred
from underscores. Value tokens in inline nodes use the paragraph's `evidence_ids` and current
table bindings, just as prose does.

Set document defaults in input `style`, and per-figure sizing in each figure's `sizing`. For
example, merge this into the section input (use your actual image path and known source dimensions):

```json
{
  "style": {"margin_mm": 25, "body_pt": 11, "caption_pt": 10, "figure_width_mm": 150},
  "figures": [{
    "id": "f1", "path": "fixture.png", "caption": "Case a diagnostics",
    "description": "Use the actual supplied figure description here.",
    "sizing": {"source_width_mm": 150, "target_width_mm": 150, "minimum_source_font_pt": 9}
  }]
}
```

These are adjustable review settings, not journal certification. Source width means the actual
exported width; leave unknown source font size unspecified. Embedded font size scales with
embedded width divided by source width. After assembly, export with figures near their references:

```text
cfdpaper write PROJECT_ROOT --artifact results-section --package section-v1 --docx --layout near-reference --pdf-preview --output section-v1.docx
```

`after-text` remains the default layout. PDF preview uses an available LibreOffice backend;
omit `--pdf-preview` to export DOCX alone. Inspect the rendered pages for readable text and captions.

## Conjugate heat transfer

Read the source tables, not just a metric JSON. State the solid/fluid interface, statistical
domain and operator for each temperature, pressure and flux. Use the existing `table_evidence`
helpers for equal-observation population CV and partition identities; missing values remain
missing. A conditional weighted-temperature mismatch requires checking report fields, face sets
and interpolation before selecting either value. Copy small tables/scripts using explicit
`source_files` under `sources/` so an external reviewer can repeat the calculation.

Use available regional area, mean flux and integrated heat together: Q = A times mean flux.
If area grows while mean flux falls, determine their product before explaining the heat budget.
Equal-area bands may carry different heat without different area growth. At fixed total heat,
the whole-interface mean flux decreases with increasing area by definition. This is not an
independent mechanism or evidence of an increased local heat-transfer coefficient.

Describe the actual shared-scale maps in `observation_notes`: localization, extrema and spatial
contrast. A narrower temperature range need not follow a lower outlet-flow CV. Distinguish net
outlet statistics from internal exchange, normal velocity from speed, and local flux from its
area integral. Local mass/enthalpy transport can test a pathway; a controlled geometry comparison
is needed to isolate topology from area. Do not treat those evidence tasks as interchangeable.

Design each figure at its intended Word width, with common scales, clear units, panel labels and
unobstructed discrete data. The DOCX exporter offers after-text (default) or near-reference layout
through `--layout`. Inspect actual rendered pages; neither image DPI nor a successful export
certifies readability. Keep renderer/font notes out of the scientific prose.
