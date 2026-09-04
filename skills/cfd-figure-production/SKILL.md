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
  data, a runnable plotting script, SVG, PNG, caption, delivery metadata, and data, narrative, and
  visual QA results.

## Prerequisites

Complete `cfd-qoi-physics`. The candidate, analysis, claim ceiling, paragraph duty, and scientific
inputs must still match their recorded fingerprints.

## Workflow

1. After author acceptance of the unchanged candidate, lock and render it:

   ```text
   cfdpaper figure PROJECT_ROOT --approve-contract FIGURE_ID --author "AUTHOR_NAME"
   ```

2. Inspect the generated SVG or PNG and the three QA results.
3. Continue only when the delivery reopens successfully and every required QA dimension passes.

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
