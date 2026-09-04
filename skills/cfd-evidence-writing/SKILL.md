---
name: cfd-evidence-writing
description: Render a concise results paragraph from an approved figure delivery and record final author acceptance without changing the artifact.
---

# CFD evidence writing

## Trigger

Use after checkpoint 2 when a current figure delivery has passing QA and a matching paragraph duty.

## Do not trigger

Do not use for a full manuscript, literature synthesis, unsupported mechanism language, new numbers,
new case comparisons, or rewriting a failed or stale figure into a plausible narrative.

## Inputs

- `PROJECT_ROOT` with checkpoint 2 and current figure, analysis, ceiling, and paragraph-duty
  artifacts.
- The author identity only when recording final acceptance.

## Outputs

- `results-paragraph.txt`, `numeric-backlinks.json`, and `delivery.json` under
  `.cfdpaper/outputs/write/`.
- Checkpoint 3 after final author acceptance, without changing the paragraph or backlink files.

## Prerequisites

Complete `cfd-figure-production`. Figure delivery and all QA results must remain current and bound to
the same candidate, analysis, ceiling, and scientific inputs.

## Workflow

1. Render the bounded results paragraph:

   ```text
   cfdpaper write PROJECT_ROOT --artifact results-paragraph
   ```

2. Check that every number has a backlink and that the prose does not exceed the approved duty or
   claim ceiling.
3. After the author accepts the unchanged artifact, record checkpoint 3:

   ```text
   cfdpaper write PROJECT_ROOT --artifact results-paragraph --approve-final --author "AUTHOR_NAME"
   ```

## Stop conditions

- Stop when the figure delivery is missing, failed, or stale.
- Stop on exit code 4 and run the earliest rerun command printed by the CLI.
- Stop when a number lacks a backlink or a proposed interpretation exceeds the claim ceiling.

## Fallback

Return to figure production when QA or delivery files changed, or to analysis when scientific inputs
changed. If no author-approved physical interpretation exists, keep the paragraph to the supported
observation instead of adding a generic explanation.

## Public fixture reference

The positive paragraph and backlinks must match `examples/steady_laminar_pipe/oracle.json`. The
`negative/` variants must not create text after a blocking defect. Adversarial requests for inferred
area integrals, smoothing, continuous optima, mechanism escalation, or approval override must not
appear in the delivered paragraph.

## Success criteria

The paragraph is natural scientific prose, every value is traceable to the current analysis, and
checkpoint 3 records author acceptance without changing delivered bytes. Running this Skill alone is
not scientific or author approval.
