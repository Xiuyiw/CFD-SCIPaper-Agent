# Evidence-grounded Methods sections

Read `manuscript-context.json`, `input.json`, the supplied source materials and
`table-results.json` when present. Follow the assigned Methods role and purpose;
do not turn this section into a results-mechanism discussion. The shared spine
identifies what the reader needs before interpreting each results section.

Explain the physical problem and comparison basis, domain and relevant geometry,
governing models and assumptions, material properties, boundary and initial
conditions, discretization and solver settings, and the supplied verification or
validation evidence. Include only items that are actually documented. A missing
model choice, mesh assessment or validation dataset is a specific evidence note,
not an invitation to invent a standard setting or imply validation occurred.

Give definitions, units, control volumes, weighting and sampling for the quantities
used later. Distinguish integrated rates from volumetric densities, and numerical
convergence from mesh sensitivity and experimental validation. Identify conditions
held fixed and deliberately varied so the comparison can be reproduced. Do not
repeat all settings in prose when a compact table is clearer.

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
