# Evidence-grounded Methods sections

Read `manuscript-context.json`, `input.json`, the supplied source materials and
`table-results.json` when present. Follow the assigned Methods role and purpose;
do not turn this section into a results-mechanism discussion. The shared spine
identifies what the reader needs before interpreting each results section.

Build Methods backward from the actual main comparisons, not from a generic solver
checklist. Locate the records a reader would need to reconstruct each comparison:

- Geometry and operating changes: identify the reference and modified definitions,
  dimensions, materials, forcing, and conditions held fixed. Match any schematic to
  these definitions; a source paper describes the present geometry only where the
  project records establish that correspondence.
- Model and numerical choices: read the applicable setup, model constants, mesh and
  boundary records. Match solver versions and settings to the actual cases and stage
  of work; a postprocessing record does not establish every run's solver version.
  Reconstruct the solution stages from execution records as well as final settings:
  frozen-field, energy-only and restored coupled stages can have the same final setup
  but different reproducible procedures. Describe the relevant sequence compactly;
  distinguish stage increments from accumulated iterations. Bind any software version
  to the cases actually documented, rather than extrapolating one control run to all cases.
- Reported quantities: locate both the operator definition and its actual output or
  history, including domain, weighting, direction, reference and sampling. A configured
  report or reference value is not a measured result. An absent user override does not
  establish a model constant's numerical default.
- Credibility checks: identify which cases and quantities the available convergence,
  mesh/near-wall and validation records examine. Their scope must cover the claim
  they support; conservation alone does not establish local spatial accuracy.

For an omission, first distinguish a packaged but unread record, an existing record
locatable in the authorized project, and evidence not yet established. Read or copy
the relevant small records in the first two categories before asking the author.
If the source cannot be accessed, name the exact report or field and the comparison
it affects in `evidence_notes`; do not request the entire project again. Conflicting
definitions need resolution, not selection of the convenient one. Do not load or
rerun a native solver solely to fill a prose template. Report only documented
methods, using a compact table where it makes case differences easier to reproduce.
For each main comparison, close the reader's path from case identity through the
solution procedure to the reported operator. Include the available numerical inlet
inputs and stopping criteria when needed to reproduce it, not only their generic names.
Equations must match the model described in prose; a partial set should not be labeled
as the complete governing system. Keep reconstruction-specific extraction details
where they distinguish a diagnostic from a native solver report.

Assess model applicability at the scope of the claim. A Reynolds number based on an inlet or
another reference length does not determine every local flow regime in a branching, impinging
or separated flow. Small wall-resolution measures such as y+ address near-wall discretization,
not independent validation of the turbulence or transition model. Inherited settings are a
documented modeling choice, not validation. First inspect the relevant available diagnostics;
do not silently replace the closure, prescribe a universal regime threshold or launch a new
simulation because one summary indicator appears unfavorable.

Give definitions, units, control volumes, weighting and sampling for the quantities
used later. Distinguish integrated rates from volumetric densities, and numerical
convergence from mesh sensitivity and experimental validation. Identify conditions
held fixed and deliberately varied so the comparison can be reproduced. Do not
repeat all settings in prose when a compact table is clearer.

Match convergence evidence to the actual reported operator and case. A monitored volume maximum
cannot certify convergence of a surface maximum, spatial spread or regional mean merely because
their final values are close. A residual target in code is not a completed history, conservation
is not spatial-error control, and numerical verification is not physical validation. Preserve
useful documented checks while stating their applicable quantity, sampling and operating scope.

When a missing check limits transfer beyond the model, retain a properly bounded comparison if
its inputs and outputs are otherwise supported. When a missing or conflicting physical
definition determines the comparison itself, leave that claim unresolved rather than inventing
a standard choice. Keep the request for the exact missing record in evidence_notes; do not turn
Methods into an inventory of what the writing host received. Any resolved definition that changes
a Results claim also requires rereading its dependent Abstract and Conclusions statements.

Use the existing section draft JSON schema. Declare evidence IDs for paragraphs,
tables and equations. Use `{{value:ID}}` for supplied or source-bound quantities;
the assembly step recomputes declared source-table calculations. Use structured
inline/display math for definitions. Every Methods table must have at least one
meaningful paragraph reference using `{{table:ID}}`; explain its purpose rather
than writing an isolated 'see table'. Use `{{figure:ID}}`, `{{equation:ID}}` and
`{{cite:ID}}` for automatic manuscript numbering. IDs are stable local identifiers,
not publication numbers: manuscript assembly assigns global labels in spine order.
Do not manually type reference numbers expecting them to be renumbered.
For cross-section objects use, for example, `{{equation:methods/resistance}}`.
Build dotted rates and overlined averages with one-child `dot` and `overbar` math nodes,
including nested accents, rather than composing decorated Unicode text in a long math run.
These export as editable equation accents; inspect the rendered formula, not only its XML.

Keep reader-facing methods prose separate from `evidence_notes`. Notes should
name the missing source or setting and the minimum author information needed.
Do not manufacture missing images, measurements, model parameters or citations.

When the supplied records establish only comparison and postprocessing methods,
title and scope the section accordingly. Do not present a reproducible diagnostic
definition as a complete reproducible simulation setup. A single-record table
mean can bind an exported scalar, but does not verify the cross-column formula
that originally produced it. State that distinction in evidence notes when it
matters. If recalculation uses a partition-sum denominator while the original
report used a separate whole-domain total, declare the chosen denominator even
when both values agree after rounding.
