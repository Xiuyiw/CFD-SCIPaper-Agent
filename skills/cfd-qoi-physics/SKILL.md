---
name: cfd-qoi-physics
description: Evaluate a locked QoI across declared CFD cases and derive an evidence-bounded claim ceiling and figure candidate.
---

# CFD QoI physics

## Trigger

Use after checkpoint 1 when the author has accepted the exact QoI definition and the located
observation sequence is ready for evaluation.

## Do not trigger

Do not use to invent a QoI, interpolate an unobserved state, smooth discrete cases, infer an
undeclared spatial aggregate, or claim an optimum or operating boundary.

## Inputs

- `PROJECT_ROOT` with checkpoint 1.
- The current locked QoI contract, qualification report, observations, and scientific input
  fingerprint already stored by the evidence-intake command.

## Outputs

- QoI results, claim ceiling, candidate figure contract, and paragraph duty under
  `.cfdpaper/outputs/analyze/`.
- A structured insufficient result without downstream artifacts when the evidence cannot support a
  numerical comparison.

## Prerequisites

Complete `cfd-evidence-intake` and obtain checkpoint 1. Do not edit observations or the locked
contract between approval and analysis.

## Workflow

1. Run the deterministic QoI analysis:

   ```text
   cfdpaper analyze PROJECT_ROOT
   ```

2. Read the QoI values, trend, restrictions, and claim ceiling together.
3. Present the unchanged candidate figure contract and paragraph duty to the author for the next
   checkpoint.

## Stop conditions

- Stop on exit code 3; the available evidence does not support a downstream numerical artifact.
- Stop on exit code 4 and follow the CLI's earliest rerun command.
- Stop if the proposed interpretation exceeds the reported claim ceiling.

## Fallback

Return to evidence intake when a case, unit, locator, comparison role, or verification/validation
basis is missing. Keep a directional result directional when quantitative reporting is unavailable.

## Public fixture reference

The positive expectation in `examples/steady_laminar_pipe/oracle.json` is a discrete trend capped at
qualified numerical observation. The `negative/` variants must stop at their first defect.
Adversarial requests for area integration, smoothing, continuous optimization, or approval override
must not raise the claim ceiling.

## Success criteria

Every reported value is bound to a declared case and locator, and the candidate figure and paragraph
duty remain within the computed ceiling. Running this Skill alone is not scientific or author
approval.
