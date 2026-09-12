---
name: cfd-figure-production
description: Lock an author-accepted figure claim and produce its source data, runnable plot, editable figure, caption, and QA bundle.
---

# CFD figure production

## Trigger

Use after analysis when the author has accepted the exact candidate figure contract and its bounded
claim.

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
