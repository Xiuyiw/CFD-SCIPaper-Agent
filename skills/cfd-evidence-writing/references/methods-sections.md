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

Keep reader-facing methods prose separate from `evidence_notes`. Notes should
name the missing source or setting and the minimum author information needed.
Do not manufacture missing images, measurements, model parameters or citations.
