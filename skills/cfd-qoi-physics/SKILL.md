---
name: cfd-qoi-physics
description: Help an author select method-backed analysis of existing CFD materials, compile it through deterministic table calculations, or evaluate an existing locked QoI.
---

# CFD QoI physics

## Trigger

Use when the author is choosing a method-backed analysis proposal from existing materials, or
after checkpoint 1 on the existing locked-QoI route.

## Host-assisted analysis route

Read the package produced by `cfd-evidence-intake`, including the actual definitions and tables.
The host may propose a new QoI or analysis direction; it must not fabricate its missing physical
definition. Distinguish observed features, relationships supported by declared quantities, and
interpretations still needing evidence. Do not treat an algebraic identity as causal proof.

For the author-selected proposal, check the mapped quantity and operator, units, spatial/statistical
domain, member and group identities, boundary/comparison basis, applicable cases and interpretation
limits. Ask only about consequential unresolved definitions. Preserve known not-comparable status;
the existence of a method path does not independently verify semantics.

Compile the selected proposal:

```text
cfdpaper plan PROJECT_ROOT --artifact analysis --package PACKAGE_DIR --proposal PROPOSAL_JSON --select CANDIDATE_ID --output OUTPUT_DIR
```

The numeric operations reuse the existing table engine: `population` uses equal records to
return count/sum/mean and population CV (`ddof=0`); `partition` sums declared area and
already-integrated rate and derives flux/shares. `weighted_population` returns weighted_mean,
weighted_std and weight_sum from explicit value/weight columns. Declare weight_kind area or volume,
map positive measure weights with matching squared/cubed units, and establish their physical
coverage from the method. Point counts and unequal cells are not interchangeable spatial weights.
For absolute temperature declare quantity_kind absolute-temperature: means retain °C/K and SD
uses K. For a temperature difference use temperature-difference with K. No CV is inferred for
the weighted operator; SD describes supplied element variation, not numerical uncertainty.
These operations do not infer a flux integral, convert units, reconstruct within-element variation,
establish physical partition coverage, or exclude inconvenient records. Missing units,
domains, definition locations, duplicate declared identities, missing declared members or
unsupported comparison status must be resolved for the selected calculation. Independent
supported candidates remain available.

Prefer a few purposeful result-bound metrics. If automatic scalar anchors are provided, they are
a selection pool, not a request to narrate every value. Inspect `table-results.json`; no hand-copied
numeric claims should replace `result_ref`. Keep zero-mean CV undefined rather than reporting zero.
Changing copied source values requires recalculation and fresh downstream figure/writing output.

Distinguish numeric anchors for prose from the evidence needed in a figure. Before selecting
figure_plan.metric_ids, identify which relationship is central and whether the selected metrics
actually display it. For example, increased regional integrated transfer and decreased mean flux
require consideration of allocation, area and flux together, not automatic selection of just two
share values. Use complete relevant partitions when the claim concerns redistribution. Do not
inflate the number of plots or indicators; a sentence or table is appropriate for a simple contrast.
Consult cfd-figure-production for this decision. If its design exceeds the implemented renderer,
record the concrete gap rather than silently accepting the renderer's default as the final design.

In the host proposal, set presentation to plot, prose, table or custom and explain the choice in
presentation_reason. Only plot invokes the current automatic comparison renderer; table/prose
continue to host writing with the same computed evidence, while custom records unfinished figure
work without substituting a default chart. This does not automatically generate a custom figure.

Use the existing figure-production and evidence-writing skills for actual plots and the subsection.
Explain why the relationship matters and what alternatives remain, without claiming that a larger
metric always means better performance or that discrete cases define a continuous operating window.
Compilation is deterministic numerical evaluation, not automatic physical validation or author
approval. No new approval registry is introduced.

## Existing locked-QoI route

The remaining requirements apply to the original locked-contract path and remain unchanged.

## Do not trigger

Do not use to invent missing QoI definitions, interpolate an unobserved state, smooth discrete cases, infer an
undeclared spatial aggregate, or claim an optimum or operating boundary.

## Inputs

- `PROJECT_ROOT` with checkpoint 1.
- The current locked QoI contract, qualification report, observations, and scientific input
  fingerprint already stored by the evidence-intake command.

## Outputs

- QoI results, claim ceiling, candidate figure contract, and paragraph duty under
  `.cfdpaper/outputs/qualify/`.
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
