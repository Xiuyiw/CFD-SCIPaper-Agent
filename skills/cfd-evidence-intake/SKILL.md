---
name: cfd-evidence-intake
description: Inspect an initialized CFD paper project, qualify a declared comparison, and prepare an author-reviewable QoI contract from located observations.
---

# CFD evidence intake

## Trigger

Use when an initialized project has solver-exported observations plus declared case, boundary,
model, convergence, conservation, verification, validation, and source records.

## Do not trigger

Do not use to infer missing values, redesign a simulation, run a solver, select a manuscript topic
without the author, or draft publication claims.

## Inputs

- `PROJECT_ROOT` and a stable `PROJECT_ID` for initialized project state.
- `PROJECT_RECORDS`, a complete `project-records.json` envelope, or an interactive guided intake.
- `OBSERVATIONS`, a CSV with units and source locators.
- `QUESTION_JSON`, a focused QoI proposal; `TOPIC_CANDIDATES`, an author-facing topic file; and the
  author-selected topic and QoI contract identifiers.

## Outputs

- Qualification report and candidate QoI contract under `.cfdpaper/outputs/qualify/`.
- A locked QoI contract and checkpoint 1 only after the author supplies the matching approval.
- A concise minimum-correction request when the evidence is insufficient.

## Prerequisites

Start from a writable project directory containing the declared records and observations. Topic
approval is requested only after the scientific records have been qualified.

## Workflow

1. Initialize project state, then refresh its inventory without modifying source results:

   ```text
   cfdpaper init PROJECT_ROOT --project-id PROJECT_ID
   cfdpaper inspect PROJECT_ROOT
   ```

2. Qualify the declared comparison and create a candidate QoI contract:

   ```text
   cfdpaper qualify PROJECT_ROOT --records PROJECT_RECORDS --observations OBSERVATIONS --question QUESTION_JSON
   ```

   If no records envelope exists, use the mutually exclusive guided form:

   ```text
   cfdpaper qualify PROJECT_ROOT --observations OBSERVATIONS --guided --question QUESTION_JSON
   ```

3. Read the qualification report. Correct any stated evidence gap rather than weakening the
   comparison definition. Then present the topic candidate to the author and record the selected
   manuscript topic:

   ```text
   cfdpaper plan PROJECT_ROOT --candidates TOPIC_CANDIDATES --approve-topic TOPIC_ID --author "AUTHOR_NAME"
   ```

4. After the author accepts the unchanged QoI candidate, record checkpoint 1:

   ```text
   cfdpaper qualify PROJECT_ROOT --approve-qoi-contract QOI_ID --author "AUTHOR_NAME"
   ```

## Stop conditions

- Stop when expected cases, units, locators, or comparison roles are incomplete or contradictory.
- Stop on exit code 3; do not proceed to analysis without a locked QoI contract.
- Stop on exit code 4 and run the earliest rerun command printed by the CLI.

## Fallback

Use guided intake when the strict records envelope is unavailable. If required evidence does not
exist, report the minimum missing input to the author; do not synthesize it.

## Public fixture reference

Use `examples/steady_laminar_pipe/README.md` and `oracle.json` for the positive path. Use files in
`negative/` for missing-member, duplicate-coordinate, unit, locator, aggregation, and
unresolved-nuisance stops. Adversarial requests for inferred area integrals, smoothing, continuous optima, or
approval override must stop without a stronger artifact.

## Success criteria

The comparison is supported by located inputs, the candidate preserves the declared case sequence,
and checkpoint 1 exists only for the exact author-accepted QoI contract. Running this Skill alone is
not scientific or author approval.
