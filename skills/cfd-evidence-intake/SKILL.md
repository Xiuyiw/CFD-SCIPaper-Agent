---
name: cfd-evidence-intake
description: Read existing CFD materials and propose grounded subsection analyses, or qualify a declared comparison through the existing locked-QoI pathway.
---

# CFD evidence intake

## Trigger

Use when an author provides existing CSV exports, readable method notes and figures, even before
they have organized a full scientific question or column mapping. Also use the strict pathway
below when an initialized project already has declared scientific records and observations.

## Existing-materials analysis entry

1. Read the material summary and actual method sources; prepare a portable host package:

   ```text
   cfdpaper inspect PROJECT_ROOT --materials --output PROFILE_DIR
   cfdpaper plan PROJECT_ROOT --artifact analysis --question "AUTHOR_QUESTION" --output PACKAGE_DIR
   ```

   The question is optional. `PACKAGE_DIR/materials.json` lists raw column names, explicit units,
   missing values, category hints and source locations. Read `host-task.md` and the relevant
   `sources/` documents in full when excerpts are truncated. Open relevant figures when possible;
   otherwise state that they were not viewed. The summary does not establish physical meaning.

2. As the host, write `proposal.json` using the packaged example/schema. Present one to three
   useful analyses, or zero with minimum evidence gaps. Ground mappings in method passages via
   `definition_source` paths and line locators, and state the operator, units, domain, member IDs,
   group column and comparison scope/status. Column names alone cannot establish these facts.
   Include expected members/groups when specified by the method. A source locator is traceability,
   not proof that the interpretation is correct. Keep observed, calculable and interpretive claims
   distinct. Recommend by scientific usefulness, not by the count of available statistics.

3. Let the author choose a candidate ID, or clarify only gaps affecting that choice. The host
   constructs the JSON; the author need not hand-write it. If their question is already explicit,
   develop that analysis without forcing a new topic exercise. A supported independent candidate
   can proceed while another candidate has unknown definitions. Do not set unknown or known
   not-comparable calculations to supported merely to obtain output.

4. Hand the chosen proposal to `cfd-qoi-physics`. This is a subsection-analysis choice, not a new
   manuscript-topic approval, locked QoI contract or checkpoint. It does not bypass an existing
   comparison restriction. Do not run a solver or invent missing definitions.

## Existing strict qualification pathway

The inputs, commands and checkpoint stop conditions below apply to the existing records-based
pathway; they do not require authors to rebuild a complete records envelope to propose analyses
from already available material.

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
