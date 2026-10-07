---
name: cfd-paper-workflow
description: Connect existing CFD materials, calculated analysis and an editable manuscript using CFD-Paper-Agent. Use when an author supplies ordinary files and a research question, or asks to continue or revise a current manuscript without rebuilding its evidence mappings.
---

# Connected CFD writing

Act as the host scientist and writer. Use the CLI for supported calculations,
source-bound values and document assembly. A successful export is not scientific
validation. Ask the author only for missing facts that change the interpretation.

## Enter at the current step

- Ordinary exports, method notes or defining scripts: follow
  [evidence intake](../cfd-evidence-intake/SKILL.md). Read scripts as source text;
  do not run a solver to discover their meaning.
- A question and available evidence: follow
  [QoI and physics](../cfd-qoi-physics/SKILL.md) to choose useful calculations.
- A calculated comparison needs a visual: follow
  [figure production](../cfd-figure-production/SKILL.md). A compact table or prose
  may be better than a sparse plot. Do not invent fields to produce a mechanism figure.
- A section or manuscript is ready to write: follow
  [evidence writing](../cfd-evidence-writing/SKILL.md).
- An assembled manuscript already exists: start with its `CONTINUE.md` and
  portable `drafts.json`, not the oldest proposal or an earlier chat.

## First manuscript from ordinary materials

When no current manuscript exists, use the accepted research scope to build a
provisional PaperSpine before drafting. Do not ask the author to supply the spine
or restart topic selection when the question is already confirmed. Inspect the
selected methods, source tables and actual figures first; a file inventory alone
cannot determine the paper's central claim.

If optional scientific context is supplied, read the package-root
`scientific-context.md` and `scientific-context/context.json` before the first
Methods/Results draft; copied source records are under `scientific-context/sources/`. Follow
the located facts linking each comparison's cases, solution stages, report operators
and applicable credibility checks; verify the relevant small records instead of
reconstructing those relations from filenames. Reuse this context in current section
tasks and continuation, and refresh it when its source facts change. Keep unresolved
facts or conflicts attached to the affected comparison while independent work proceeds.
Without a supplied context, use existing source files and notes; do not invent one
from solver defaults or ask the author to fill a second full-project questionnaire.

Before selecting numeric anchors, read the complete available column/key lists and
the case, region, layer and model categories relevant to the question. Then open the
definitions and source records that could distinguish the plausible explanations.
A preview or a convenient summary table may omit the decisive comparison. For
example, a changing total may need its regional contributions, while an unchanged
ranking may hide a model-dependent effect magnitude. Do not compute every available
metric or assume a suggestive field name supplies its physical definition.

Use the existing proposal, section `duties` and `evidence_notes` for a short working
outline: subquestion; explanation to test; distinguishing observation and located
source; reason for selecting it; receiving section or figure/table. Include a
relevant unused source only when reading it could change the argument. Prefer
evidence that resolves a live alternative over another expression of the same
contrast. Classify model/mesh controls and repeated observations with the QoI skill.
For each Results section, say what it resolves that the preceding one does not.
No new registry is needed; keep the central claim provisional until the selected
records and images have actually been read.

Draft Methods and Results from those inputs first. Write Discussion from their
combined answer and located literature; then align the Introduction's gap and
contribution with that answer, and write Abstract, Conclusions, title and keywords
last. This is a useful dependency order, not a demand to rewrite existing sections.
Refresh the current section context as described in the writing skill when a
dependent draft becomes available. Record an unresolved interpretation in notes
and continue sections that do not depend on it; an undefined quantity still blocks
the comparison that uses it.

Before calling the candidate complete, read the question and answer together:
do the Results answer the stated problem, do Methods define their actual
comparisons, and does each main figure carry evidence used in that answer?
Required but unavailable scientific content stays an explicit gap, not placeholder
prose. Preserve the first complete candidate before review or local revision;
chapter count and successful assembly do not establish scientific completeness.

Use the writing skill's Methods reference to trace each main comparison back to its
actual geometry, settings and diagnostic records, and its literature reference to
locate the closest relevant findings when the supplied sources cannot establish the
contribution. Resolve omissions from available records before asking the author.
Write key procedural choices compactly, put case-specific parameters in a useful
table and move noncentral detail to supplementary methods. In Results, preserve
total/local/normalized scope and judge a small effect only against applicable controls.
In Discussion, compare the nearest study's actual response, ordering or mechanism,
not merely its different conditions. These are host writing duties; the CLI carries
declared context, calculates supported operators and assembles documents, not proof
of a physical explanation or an automatic literature comparison.
Keep a necessary qualification beside the first claim it changes, and use the space
saved from repeated limitations to explain the positive answer from the selected evidence.

## Reuse analysis output instead of remapping values

After the analysis selection command, `selected/section-input/writing/input.json`
already contains the section identity, evidence IDs, calculations, source copies
and result bindings. Point the manuscript manifest's section entry to that file.
Do not type the computed values into another evidence list or reconstruct its
`result_ref` objects. Preserve the surrounding directory so relative sources resolve.

For example, if that input declares section `pressure` and evidence `total_0`:

```json
{"section_id": "pressure", "input": "selected/section-input/writing/input.json"}
```

Its spine contract uses `required_claim_ids: ["total_0"]`, and its draft uses
`{{value:total_0}}`. These are exact **local** IDs, not `pressure.total_0`.
For evidence borrowed by another section, use that section's `evidence_bindings`
mapping, for example `{"pressure_change": "pressure/total_0"}`, then use the
local alias `pressure_change` in its claims and draft. Never silently rename IDs.
The central claim and paragraph purposes still require scientific judgment:
select them for the argument, not by taking the first metric in a file.

## Write the science, not a calculation log

Assign each section a distinct purpose. Explain what the observations mean,
which comparison supports that interpretation, and what remains unresolved.
Distinguish displayed fields from inferred mechanisms and prescribed conditions
from experimentally demonstrated performance. Do not repeat every table value
and limitation in each section. Consult supplied literature for its actual role;
do not substitute plausible citations for verified support.

Use existing structured `inline_math` with `{{math:ID}}` for mathematical
variables or fractions; use `{{equation:ID}}` for numbered equations. Plain
underscore notation is not automatically converted into native Word mathematics.
Keep source variable/zone names in definitions where needed, but give readers
physical names in the prose. Preserve symbols, units and definitions throughout.

Export the existing `near-reference` DOCX layout. Check the rendered pages,
including native equations, table alignment and figure readability. Body defaults
are a two-character first-line indent and zero before/after spacing; an author or
journal template may override them. Do not apply body formatting to captions.

## Continue and revise locally

Preserve the current candidate and any author-edited Word file. Use a working
copy of the current manuscript workspace, modify only the requested section
draft or source, and assemble to a fresh output directory. Numeric bindings are
recomputed from that workspace's source snapshot, not a separately edited original.
Re-read dependent claims when numbers change: computation cannot update the
physical interpretation for you. Re-export DOCX explicitly; an older DOCX does
not update itself. If the author edited Word directly, reconcile those edits
before replacing its text from JSON.

The repository tutorial `examples/material-analysis/prepare_manuscript.py`
demonstrates the bridge with public synthetic data and recorded Methods/Results
prose. It tests connected inputs and editable output, not autonomous research.
