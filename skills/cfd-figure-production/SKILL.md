---
name: cfd-figure-production
description: Select and render CFD evidence figures, or create paper-grounded mechanism diagrams with Paper Framework Figure Studio, preserving sources and author edits.
---

# CFD figure production

## Trigger

Use after analysis when the author has accepted the exact candidate figure contract and its bounded
claim.

Also use when choosing or assessing figures for host-assisted analysis/subsections. The legacy
approval CLI below applies only to its existing candidate pipeline, not to every supplied figure.

For mechanism, paper-framework or method schematics, use
[Paper Framework Figure Studio](references/paper-framework-studio.md) through the portable task
route below. Prefer the installed `paper-framework-figure-studio-pro`; the bundled adaptation
works without that installation. Read the actual paper/method/evidence, make core mechanism steps
visible, and develop the figure and caption together. Default to one finished candidate, not a
new approval sequence. Keep numerical CFD plots and real field images data-driven.

## Scientific figure selection

Before rendering, state the question and what the reader should learn from seeing the figure
rather than reading a sentence or table. Select quantities and comparisons from that purpose,
not from the first available scalar output or the renderer's default chart.

- Match information density to scientific purpose and final manuscript size. A two-value contrast
  can be useful, but does not automatically deserve a full-width standalone plot. Consider a sentence,
  small table, compact panel or combination with related evidence. Do not impose minimum point counts.
- If the argument depends on opposing responses, a spatial redistribution or a decomposition,
  show the necessary complementary quantities together where the evidence permits. Do not plot one
  convenient metric while leaving the decisive relationship invisible. Use aligned panels for unlike
  units; an algebraic decomposition is not, by itself, evidence of a causal mechanism.
- Choose encoding by the actual relationship: region-by-case comparisons for spatial allocation,
  contribution charts for defined additive parts, paired comparisons for change, and scatter only
  when its coordinates or categories reveal the intended relation. More panels, colors or glyphs
  are not inherently better. Never invent uncertainty, smooth discrete cases or duplicate readings
  merely to fill space.
- Keep full spatial/operating context when needed to understand a local change; do not cherry-pick
  a region because its contrast is visually attractive. Use the relevant P04 lesson, not its visual
  template: contributions, sampled distributions and complementary diagnostics serve different roles.
- For a geometry or Methods figure, check that the main reference-to-modified comparison can
  actually be understood from the shown geometry, dimensions and legend. A schematic of a
  secondary variant does not define an omitted baseline. Use available geometry records; if a
  necessary definition is missing, retain that specific gap rather than drawing a plausible shape.
- If the available renderer cannot express the proposed relationship, identify that specific product
  gap. A default plot is a preliminary visualization, not a publication-quality figure. For an already
  accepted or manually edited figure, propose a semantic redesign to the author before changing it.

At final embedded size, identify the sign, small difference or regional feature that decides the
claim and check whether a reader can read it, not merely see its marker. When a valid shared scale
hides that feature, use a restrained value label, compact table or clearly identified local-scale
panel as appropriate; do not move data, invent error bars or change an accepted encoding without
agreement. Higher DPI does not enlarge embedded text or separate near-zero values. Also inspect
units, legend, marker weights, whitespace and panel alignment on the actual manuscript page.
Keep the result in existing figure contract/review notes; successful export and no clipping alone
do not establish scientific readability.

Use the accepted P04 field plots, quantitative figures and schematics as the current internal
quality floor, not just inspiration. Compare like kinds at the same manuscript width; transfer
their scientific clarity and finish, not burner-specific content or decorative complexity.

For declared numerical evidence, `evidence_panels` combines `profile`, `reference_range` and
`response` panels. A profile or range panel names a `calculation_id`, `title`, `x_label`, `y_label`, and
optionally selected `groups`. A profile uses the temporal declaration's exact saved-sample
window and value kind; it cannot manufacture an unavailable curve. A reference-range panel
shows the supplied bounds/center, model value and signed difference, with the declared range
kind retained in its caption and source data. Reported ranges, figure-reading envelopes and
declared bounds are not confidence intervals. Different units belong in separate panels.
The reusable output includes source locations, editable vector/raster exports and standalone
`plot.py`; preserve local author edits and inspect the PNG at its final 160 mm width after
the actual bounding-box checks. This finite route is not a general diagram engine.

For a saved-parameter sweep, use a `response` panel rather than pretending the parameter is
time or copying scalar points into a free script. Declare `x_calculation_id` and a nonempty
`series` list of `{calculation_id, label, field?}`. The x calculation selects an actual scalar;
each y field is resolved from the same exact case groups. Units come from these calculations.
Keep unlike y units in aligned panels, not an implicit dual axis. `connect: true` requests straight
guides between discrete observations, not fitting or smoothing; the default is unconnected markers.

The direct `report_task` accepts `figure_plan={"panels": [...], "columns": 2}` with optional
`style` (existing `PlotStyle` fields) and `caption`. Use the report quantity IDs as calculation IDs.
This creates the source-bound plot, Results figure/caption and figure locations in
`report-context.json`; it does not write scientific prose. Open the actual preview, record visible
features in the Results draft's `observation_notes`, and reference `{{figure:1}}` with its figure ID.
On report continuation the retained local `plot.py` consumes fresh source rows and redraws into
a new candidate. Do not regenerate a template over the author's style edits. Review caption and
interpretation after definition changes; numerical refresh is not an automatic scientific rewrite.

For a spatial claim with height- or region-resolved signed transfer, use the finite
`surface_figures.render_surface_composite(study_path, diagnostics_path, output_dir,
panel_id=...)` route. Select exactly two original-face cases. Each diagnostic series names its
matching `case_id` and a `calculation_ids` mapping for the panel's declared `layers`; an optional
`calculation_id` supplies the full-domain aggregate. Use the same physical band order across
related figures, and identify the aggregate separately so it is not counted as another layer.
The maps share coordinates, aspect and a color scale. An optional `region_outline` names the
actual bounds used by the diagnosis, not an attractive contour drawn after seeing the result.
Show positive, negative and net contributions together: explicit small-value readings may be
needed even when the common axis makes a negative contribution visually narrow. Retain the
original arrays, calculation definitions, source CSVs and local `plot.py` for re-export.
Connect the selected figure to the existing section's evidence IDs and caption; a renderer's
empty `evidence_ids` list alone does not establish a scientific prose binding. Distinguish native
interface fluxes, input-minus-output remainders and reconstructed gradient integrals according
to their actual definitions. Same-solution agreement is not independent validation.

For a Studio schematic, check arrows against the drawn geometry and the exact caption: an
arrow contained inside one layer shows a direction, not an interface-crossing rate. Show
conceptual layers as such; do not imply that they resolve actual coolant topology. Carry the
editable source and declared source font sizes through import, then inspect the actual Word
placement; source font sizes alone do not guarantee readability after page-constrained scaling.

A profile also accepts `temporal_difference` on two columns of the same saved record. Its plotted
value and prose statistics share the declaration; the source CSV includes both original readings,
units and record locations. State comparison-minus-reference and retain a relevant original-state
observation when it affects the interpretation. Derived curves alone do not identify a mechanism.

The same range panel accepts paired_reference_change. Its model/reference points are differences,
not absolute values; temperature-change axes use K even when input temperatures use Celsius.
The span is conservative subtraction of source endpoints, not a directly supplied measurement
interval. When apparent contrast agreement may result from offset cancellation, show the original
observations alongside the paired panel or retain their absolute deviations in a compact table.
Do not hide that evidence behind an attractive zero-mismatch marker.

## Original-face surface studies

In a new surface study, optional `selected_figures` chooses the initial manuscript figure IDs
from `field` and `distribution`, in the requested order. Omission retains the legacy pair;
`["field"]` keeps the map without promoting the empirical curve to a standalone main figure,
and `[]` permits a table-led argument. Source diagnostics and their data remain available.
Read `research-context.json`'s `selected_figures` and the actual section input before drafting;
available generated files are not all required publication figures. Preserve an existing author's
chosen figure set rather than applying this initial selection over their manuscript.

For original-face surface exports, `render_surface_study` supplies common-scale
polygon fields and an exact measure-weighted exceedance distribution. The spatial
map explains where a change occurs; the curve and weighted statistics explain its
extent and level. These are complementary summaries of the same numerical solution,
not independent validation. Use physical face areas, not projected display areas;
state strict versus inclusive thresholds, and do not promote a diagnostic threshold
to a device failure limit. A spatial standard deviation measures nonuniformity,
not simulation uncertainty. Preserve the distinction between the observed interface
and a larger volume or other boundary when naming the quantity.

The research workspace retains its editable `figures/plot.py`. On a source update,
run that current script through the declared recipe rather than regenerating it
from a template. This keeps author style edits while recalculating the source data
and figures together. Inspect both the map and distribution at the actual Word width;
the complementary relationship, legibility and caption remain host responsibilities.

## Connected physical diagnostics

Two complementary diagnostic panels may share a canvas through
`render_diagnostic_figures(config, output, combine=True, figure_id="comparison")`.
In a research workspace, use `attach_research_diagnostics(workspace, config, output,
combine=True, figure_id="comparison", panel_ids=[...], style=...)` to retain that composition
as a refreshable recipe, rather than merely inserting its current PNG into the section.
The optional `panel_ids` selects nonempty, unique panel IDs in the requested order;
omitting it renders all declared panels. The exported local `plot.py` retains that choice.
Keep its configuration and raw sources inside the workspace, with relative paths, and preserve
the author's script as the refresh entry point. Check the real refreshed source rows and
manuscript, not only that the first image exists. See the runnable
[research-expression example](../../examples/research-expression/README.md).
Use `regional` with `view: paired_change` for explicit reference/comparison regional means;
each series declares `pair_id` and `role`, never inferred from a case-name substring.
Keep a moving source region distinct from a fixed-coordinate field difference.
The `budget` view `decomposition` shows its reported output/storage and signed remainder
against input/source; use scientifically accurate `component_labels`. It is a balance
decomposition, not an independent measurement of each transport path. Inspect the combined
figure at its final width and use the generated local script on later source refreshes.

For attached physical diagnostics, `diagnostic_figures` consumes the declared
`field_calculations` and selected `panels` rather than a second hand-entered metric table.
Its implemented panel kinds are `regional`, `signed_flux`, `budget` and
`matched_difference`. Choose the needed combination: regional mean with area support,
positive/negative exchange with its net, independent budget terms with the residual,
or original means beside their matched difference. The temperature field and distribution
remain useful spatial context. A difference or residual alone cannot identify its cause.

Keep the `signed_flux` panel's `sign_convention` explicit. A `budget` panel needs actual
input, output, source and storage definitions; a prescribed example budget does not close
an unrelated field. Output source data and the author-local diagnostic `plot.py` travel with
SVG/PDF/PNG/TIFF. Inspect them at their actual manuscript width and preserve that script
on refresh. A conceptual Studio arrow may illustrate the interpretation; quantitative arrow
widths or claims of a resolved path require actual compatible transport evidence.

## Do not trigger

Do not use to change QoI values, case order, units, claim strength, chart semantics, or infer a
continuous response from discrete CFD cases.

## Inputs

- `PROJECT_ROOT` with current analysis artifacts.
- The candidate figure identifier and matching author identity.

## Outputs

- Checkpoint 2 and a figure bundle under `.cfdpaper/outputs/figure/FIGURE_ID/` containing source
  data, a runnable plotting script, SVG/PDF with editable text, PNG/TIFF, caption, delivery metadata,
  and data, narrative, and visual QA results.

## Prerequisites

Complete `cfd-qoi-physics`. The candidate, analysis, claim ceiling, paragraph duty, and scientific
inputs must still match their recorded fingerprints.

## Workflow

1. After author acceptance of the unchanged candidate, lock and render it:

   ```text
   cfdpaper figure PROJECT_ROOT --approve-contract FIGURE_ID --author "AUTHOR_NAME"
   ```

2. Inspect a representative SVG or PNG and the three QA results. All four export files must be
   listed in the delivery metadata and QA artifact bindings; PNG/TIFF must decode with matching
   canvas dimensions and nonblank content. SVG labels remain text; PDF embeds TrueType text.
3. Continue only when the delivery reopens successfully and every required QA dimension passes.

Preserve an author's edited local plotting script as the current source. Do not rerun the template
build over that script: before writing any outputs, the build refuses to replace an existing script
that differs from its delivery record or has no usable baseline. An unchanged recorded script can
be rebuilt. Use the local script for targeted edits/re-export, and resolve the resulting delivery
mismatch before calling it complete; running the script alone does not refresh delivery validation.
Keep source values, case order, units, chart semantics, axis limits, and scientific labels unchanged.

New core figures use a fixed canvas. The optional Python `build_figure_delivery(..., style=PlotStyle(...))`
sets width/height in mm, dpi, font family, and text sizes in pt. The exported standalone script keeps
these settings together in `PLOT_STYLE`; editable local scripts retain priority on later work.
`source_width_mm` and `minimum_source_font_pt` are available on the delivery result and in
`delivery.json`, measured from the raster output and visible rendered text. Supply them as section
figure `sizing`; let the document layer choose the actual embedding width. Raster rounding can differ
from the vector canvas by up to one pixel. Raising dpi does not increase the embedded text size.

## External drawing tools: portable tasks and mechanism figures

To update an already attached imported diagram, use the existing figure-task route to revise the
current author-editable source, then attach the returned candidate with `--replace-figure`
(Python: `replace_existing=True`). Keep the exact figure ID. The new workspace retains earlier
source files and numbering, takes the supplied new caption, and does not duplicate or overwrite
body paragraphs. Inspect the changed arrow meanings with the new caption, then revise affected
scientific prose explicitly. This is not an automatic scientific redraw of arbitrary SVG/draw.io.

Use this route when the scientific argument needs a layout or schematic outside the existing
data renderer. Read the packaged external-tool reference; choose the tool by the scientific
relationship rather than starting a new canvas engine.

```text
cfdpaper figure PROJECT_ROOT --task-input figure-task.json --output figure-package
cfdpaper figure PROJECT_ROOT --package figure-package --delivery delivery.json --output figure-candidate
```

The task states `figure_id`, `kind` (`data`, `schematic`, or `hybrid`), `purpose`, `claim_ceiling`,
source files and their roles, exact labels/units, optional relationships and final width. Supply
relevant paper/method excerpts as `context` sources for a mechanism figure. Follow
`prompt.md` and the bundled references using an available host drawing tool. Data charts must come
from source records and runnable plotting code. Conceptual arrows convey only declared physical
relationships; distinguish hypotheses from measured observations. A concept illustration must never
be passed off as a CFD field. Keep original field images unchanged in mixed layouts.

`output_mode` defaults to `editable`. For an explicitly requested pure conceptual raster figure,
`kind: schematic` also accepts `output_mode: raster_concept`; the host's image tool may draw it,
but an empty editable list is reported honestly. Data/hybrid tasks cannot use that mode.

Return `delivery-template.json` with actual editable sources when available, raster preview and
caption; optional `title`, `legend` and `body_reference` keep the explanatory text with the image.
They do not automatically replace manuscript prose. The import reports `editable_available`
separately from readable preview and never promotes a bitmap to editable artwork.
Where known, set its `sizing.source_width_mm` and `sizing.minimum_source_font_pt` from the actual
exported figure. `target_width_mm` inherits the task's final width; revise the task explicitly if
that width changes. Import returns reusable `sizing` and a page-constrained `placement`, including
scaled minimum font size. Carry `sizing` into the section figure and use the same publication style;
Word export recomputes placement if the page or caption changes. These font values are declared
metadata, not automatic image-text measurements. Unknown font size stays unknown. Inspect the
final document as well as the standalone preview; more pixels do not repair small embedded text.
For field-based plots, follow the native-field dependency and relocated-script procedure in the
external-tool reference. Carry the actual selected arrays/geometry/helpers, not just the preview.
Import copies these files; it does not run arbitrary returned code, generate the figure, judge
scientific truth or record author approval. Inspect the real image at intended print size. If a
tool is unavailable, retain the task and report the missing backend; do not substitute a fabricated
execution status. No image-generation API is mandatory for this path.

## Stop conditions

- Stop when approval does not match the current candidate.
- Stop on exit code 4 and run the earliest rerun command printed by the CLI.
- Stop when rendering or any QA dimension fails; do not treat a partial bundle as complete.

## Fallback

Return to `cfdpaper analyze PROJECT_ROOT` when the analysis or candidate is stale. When rendering
fails without stale input, report the concise failure and preserve the scientific inputs unchanged.

## Public fixture reference

The positive bundle must match `examples/steady_laminar_pipe/oracle.json`. The `negative/` variants
must not produce a figure after a blocking defect. Adversarial requests for inferred area integrals,
smoothing, continuous optima, or approval override must not alter source data or unlock a figure.

## Success criteria

The delivered plot is generated from its exported source data, its caption states the discrete-case
boundary, and all three QA dimensions pass for the approved claim. Running this Skill alone is not
scientific or author approval.
