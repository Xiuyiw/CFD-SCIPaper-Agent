---
name: cfd-figure-production
description: Select evidence and visual encoding for a CFD argument, assess scientific information density, and produce an author-accepted reproducible figure bundle.
---

# CFD figure production

## Trigger

Use after analysis when the author has accepted the exact candidate figure contract and its bounded
claim.

Also use when choosing or assessing figures for host-assisted analysis/subsections. The legacy
approval CLI below applies only to its existing candidate pipeline, not to every supplied figure.

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
- If the available renderer cannot express the proposed relationship, identify that specific product
  gap. A default plot is a preliminary visualization, not a publication-quality figure. For an already
  accepted or manually edited figure, propose a semantic redesign to the author before changing it.

At final embedded size inspect both scientific readability and typography: can the reader see the
main relationship without relying on the prose; are labels/units/legend readable, marker weights
consistent, whitespace proportionate, and neighboring panels aligned? Successful export and absence
of clipping are necessary checks, not sufficient evidence of figure quality. Keep this assessment
in the existing figure contract/review notes; do not create another approval registry.

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

## External drawing tools: portable tasks and editable returns

Use this route when the scientific argument needs a layout or schematic outside the existing
data renderer. Read the packaged external-tool reference; choose the tool by the scientific
relationship rather than starting a new canvas engine.

```text
cfdpaper figure PROJECT_ROOT --task-input figure-task.json --output figure-package
cfdpaper figure PROJECT_ROOT --package figure-package --delivery delivery.json --output figure-candidate
```

The task states `figure_id`, `kind` (`data`, `schematic`, or `hybrid`), `purpose`, `claim_ceiling`,
source files and their roles, exact labels/units, optional relationships and final width. Follow
`prompt.md` and the bundled references using an available host drawing tool. Data charts must come
from source records and runnable plotting code. Conceptual arrows convey only declared physical
relationships; distinguish hypotheses from measured observations. A concept illustration must never
be passed off as a CFD field. Keep original field images unchanged in mixed layouts.

Return `delivery-template.json` with the actual editable source files, raster preview and caption.
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
