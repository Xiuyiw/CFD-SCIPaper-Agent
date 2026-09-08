# Figure-grounded mechanism subsections

Read this reference when drafting a results-section, after identifying its scientific question and
paragraph duties. Use the actual supplied evidence, not a fixed sentence template. A single figure
may support a complete argument; multiple figures should answer one question through complementary
evidence rather than repeat their captions.

## Establish what is known

Open each figure and distinguish visible features from author-provided descriptions. Record
`viewed` only after actual viewing; use `author-provided` or `not-viewed` otherwise. A contour can
show localization or redistribution without establishing a source-resolved budget or causation.
Read legends, normalization, axes and case definitions before comparing apparent color intensity.
If scales differ, colors alone do not establish a quantitative difference.

For each paragraph, choose its duty and evidence/figure IDs. Distinguish direct observations,
supplied metrics, interpretations and literature. Exact source locators identify declared evidence;
they do not certify that a source was independently checked. Do not invent missing quantities,
case comparisons, citations or boundary conditions.

## Build the argument from the physical question

For a single figure, identify the dominant spatial or parametric change, quantify it only where
supplied measurements permit, then connect it to a defensible balance or transport process. State
what the figure adds beyond its caption. Avoid describing every panel in plotting order.

For multiple figures, give each a distinct role: for example, a field identifies a spatial change,
a profile tests its location or extent, and a derived metric tests its magnitude. Explain agreement
or tension between them. Do not treat several correlated diagnostics of the same field as
independent verification. If a metric and the spatial field disagree, inspect their definitions
and sampling support before selecting the more convenient result.

Reason from the relevant mass, momentum, energy or species balance. Check the control volume,
boundary conditions, imposed forcing and comparison basis. Distinguish storage, transport and
source terms, and assess whether geometry, residence time or redistribution offers an alternative
explanation. Use causal wording only when the evidence separates the proposed mechanism from
credible alternatives; otherwise describe consistency or association. A larger indicator is not
automatically a better engineering outcome.

## Keep quantitative statements well defined

- A sum of cell-integrated rates differs from a sum of per-volume source densities; the latter
  requires cell-volume weighting to become an integrated rate. An area flux integral similarly
  needs the relevant area and normal direction.
- A sampled peak is not necessarily a continuous-field maximum. A local value is not a global
  balance. Missing data are not zero. Threshold sensitivity is not measurement uncertainty.
- Use consistent dimensions, reference scales and control-volume scope. Check mesh/time-step
  dependence, convergence and available validation before implying resolved accuracy.
- Preserve supplied values through `{{value:evidence_id}}`; use `{{figure:figure_id}}` and
  `{{cite:evidence_id}}` for figure and supplied literature references. Cite tokens require
  literature evidence. Declare each paragraph's referenced IDs, as described in `TASK.md`.
  Raw free prose is not numerically or semantically certified by successful assembly.

## Write for the reader, keep review work separate

Lead with the evidence-supported finding, develop its physical interpretation, and finish with the
implication relevant to the section question. Vary paragraph structure with the evidence rather
than forcing observation, mechanism and implication into identical three-sentence blocks. Prefer
specific physical relationships to generic claims such as improved mixing or enhanced performance.

Put source-access gaps, requests for additional analysis and reviewer questions in `evidence_notes`.
Keep qualifications necessary to interpret a scientific claim in the manuscript itself; separate
notes are not a license for overstatement. Captions define variables, conditions and visual encoding
without duplicating the discussion. Before assembly, check every duty, comparison, quantitative
statement and image-observation status. Human review remains responsible for the argument.
