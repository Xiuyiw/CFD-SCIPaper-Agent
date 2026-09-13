# Literature-linked analytical manuscript example

This example requires the v0.8 development implementation (or a later release containing it),
not the released v0.7.0 wheel. Install this checkout with the `docs` extra and run from its root:

```text
python -m pip install -e ".[docs]"
python examples/literature-manuscript/prepare_example.py my-source
cfdpaper write my-source --artifact manuscript --manuscript-input my-source/manuscript-input.json --output my-package
cfdpaper write my-source --artifact manuscript --package my-package --draft my-source/drafts.json --output my-manuscript
cfdpaper write my-source --artifact manuscript --package my-manuscript --docx --layout near-reference --output my-manuscript.docx
```

Every output path must be new. The preparation script calls the existing manuscript-workspace
tutorial, retaining its analytical source values, two simple reference plots, Methods table and
equation. It adds Abstract, Introduction, Discussion and Conclusions for seven sections in total.
It does not add complex graphics to suggest a more mature scientific study. Add `--pdf-preview`
to DOCX export only if a supported LibreOffice installation is available. No paid service, external
download or Pandoc is required to generate the example after installing the project dependencies.

## What the example demonstrates

The two existing Results sections compare analytical pressure drop and a prescribed fully developed
Nusselt number. The additional static, authored sample drafts demonstrate section roles, shared
literature identity, global citations and cross-section numerical evidence bindings. They are not
a fresh AI scientific-writing experiment, a literature novelty claim, a solved CFD study or a
publication-ready full manuscript.

`literature/analytical-note.md` is a readable note generated with this software example. Its CSL JSON
record deliberately has no DOI or invented publication metadata. Three claim-specific uses in
Introduction and Discussion share that same source identity. Their `supported` status is supplied
for the authored example; excerpt matching verifies location, not semantic truth or validation.
Read the note and each `claim`, `role`, `locator` and `excerpt` in `literature/literature.json` together.

The new summary sections have no copied raw CSV or separately entered metric values. Their input
`evidence` arrays start empty; manuscript preparation resolves these `evidence_bindings`:

| Local evidence ID | Direct owner evidence | Meaning |
|---|---|---|
| `dp-first` | `hydraulics/dp-A` | Case A pressure, recalculated from the owner's CSV |
| `dp-last` | `hydraulics/dp-C` | Case C pressure, recalculated from the owner's CSV |
| `nu-reference` | `thermal/nu-A` | Existing declared analytical value, not a new table calculation |
| `model-scope` | `methods/model` | Existing analytical assumptions and interpretation scope |

Abstract, Discussion and Conclusions use `{{value:dp-first}}`, `{{value:dp-last}}` and
`{{value:nu-reference}}`, with the local IDs also listed in paragraph evidence and duties.
`depends_on` declares the scientific reading dependencies; it is not a request to automatically
rewrite the dependent prose. Abstract appears first in reading order but depends on Results/Discussion.

## Check propagation from an owner source

Keep `my-manuscript` unchanged and copy that whole assembled directory to `working-copy`.
Read `working-copy/CONTINUE.md`, its manuscript and local-ID drafts. In the working copy only,
open `sections/hydraulics/input.json` and follow the `case-pressure` calculation's relative source
path to its CSV. Change one `pressure_drop_Pa` value, retaining the case ID and other fields.
This is a software propagation perturbation, not a newly derived analytical or physical result.
Do not edit copies belonging to another owner section or manually replace summary values.

```text
cfdpaper write . --artifact manuscript --package working-copy --draft working-copy/drafts.json --output changed-manuscript
cfdpaper write . --artifact manuscript --package changed-manuscript --docx --layout near-reference --output changed-manuscript.docx
```

Check that the changed owner pressure is identical in the Hydraulic response, Abstract, Discussion
and Conclusions, including their units and formatting. Nu should be unchanged. The retained plots
are not automatically redrawn after this perturbation: do not treat the changed output as a
scientifically consistent candidate until the host updates the relevant figure and interpretations.
Read the generated dependency/context-change report and the affected section tasks. A context
report identifies dependencies to reconsider; it does not automatically rewrite scientific claims,
prove a new trend, or infer author acceptance. Restore the reference value in a fresh working copy
when you want the original analytical demonstration again.

For actual host-written prose, use the package TASK and section tasks rather than claiming the
supplied drafts were generated by the CLI. Preserve local draft IDs and use the assembled candidate's
`drafts.json` for continuation. Reconcile Word-only edits with the authoring drafts before export.
The default body uses a two-character first-line indent and zero paragraph spacing; inspect the
actual rendered pages, references and scientific meaning rather than relying on file generation.
