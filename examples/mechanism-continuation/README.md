# Same-evidence mechanism and manuscript continuation

This fully constructed example continues `research-expression` through the public
research-question and figure-task APIs. It adds one editable observation-support
schematic to the existing quantitative composite, then carries a controlled source
change through a same-ID diagram update, caption and explicit example-author prose.
It does not discover a mechanism, call an image model, solve CFD or validate a device.

With the matching checkout and `.[docs,geometry]` installed, use two commands and new output
directories:

```console
python examples/research-expression/run_example.py output/research-expression
python examples/mechanism-continuation/run_example.py output/research-expression output/mechanism-continuation
```

The second command reads the first command's original `candidate/workspace/`, not
its already shifted `refreshed/` output. It does not recreate the input study or
copy the earlier calculation/plot implementation. It adds a finite partition-change
recipe to an isolated continuing workspace: original face areas determine regional
weights, and the resulting temperature contributions enter both the existing plot
and prose through normal bindings. If that output already exists,
run only the second command with a fresh continuation output path.

## Read the actual comparison

`research_question_context()` recalculates selected original means, regional means
and the same-face difference, retaining definitions, support and the related prose.
Structure A initially has whole-interface means 317.500 and 319.750 K, hence a
comparison-minus-reference change of +2.250 K. Its footprint contribution is
−0.750 K and its remaining-region contribution is +3.000 K. These area-weighted
temperature changes are not heat fractions or independent causal evidence. The two
original faces have areas 100 and 300 mm². The new schematic uses their real vertices and connectivity,
preserves that 1:3 area ratio, and labels original face temperatures. Its SVG has
native editable text and polygons; its PNG uses the same drawing primitives.
The arrow denotes paired comparison, not heat flow.

In a separate author workspace the example subtracts 4 K from both A1 face values.
No geometry, face areas, observation definitions, B fields, budget inputs or
author-local plotting script changes during this source perturbation. The mean
difference becomes −1.750 K: the footprint contributes −1.750 K while the remaining
region contributes zero. This controlled
software perturbation is not another simulated operating condition.

The local energy budgets remain separate prescribed accounting. They are not
independent measurements of the temperature response and are not drawn as causal
heat-flow paths. The source-supported explanation here is the contribution of
fixed-area regional observations to an overall mean, not a demonstrated conduction
or mixing mechanism. Real geometry/transport interpretation needs real linked evidence.

## Inspect each continuation stage

- `analysis-input/` and `source-analysis/`: the added contribution recipe uses the
  existing synthetic case files. The three-panel composite retains original regional
  changes, adds their weighted composition and keeps the separately prescribed
  budgets. Its isolated author script receives only the extra print height needed
  by the added panel; the predecessor remains unchanged.
- `initial-revision-proposal.json`: example-author Methods/Results wording and the
  updated composite caption are applied through `apply_research_revision()`, not a
  direct draft-JSON rewrite.
- `context-before.json` and `context-after.json`: current, explicitly selected
  evidence obtained through the read-only question API; the script does not insert
  hand-entered means into resolved manuscript values.
- `artwork-before/` and `artwork-after/`: prepare/import task packages, original
  constructed source copies, author-created SVG/PNG, captions and delivery metadata.
- `first-candidate/manuscript.docx`: four-section note with existing Figure 1,
  new Figure 2 and the two existing native tables.
- `author-working/`: isolated editable copy with an author SVG comment/notes and
  the uniform A1 shift. Input materials and the predecessor candidate stay unchanged.
- `numerical-refresh/manuscript/CHANGES.md`: recomputed evidence and the explicit
  `difference_mean` direction-change context. This intermediate draft deliberately
  retains its old interpretation: it is the review input, not the final note.
- `artwork-updated-workspace/`: `attach_imported_figure(..., replace_existing=True)`
  uses the same figure identity and numbering, updates its caption and stores new
  artwork under `observation-support-update-1`. The original author source/notes
  remain under `observation-support`. Paragraph text is not automatically replaced.
- `host-revised-workspace/`: disclosed example-author revisions in
  `host-revision-proposal.json` change the affected Results/Discussion/Conclusions
  and explain the constructed shift in Methods. The revision API locates current
  paragraph IDs, checks previous wording and attaches explicit evidence references.
  Scientific interpretation is not inferred by the software.
- `interpretation-updated/manuscript.docx`: rebuilt final editable note; the same
  two figure identities/order and tables remain, without duplicate introduction
  paragraphs. `continuation.json` points to the main artifacts.

Open the actual PNG and Word pages when assessing communication quality. Import
checks and tests establish the software behavior, not journal quality or scientific
validation. For a real study, the host author must review the evidence and revise
the interpretation; the example's fixed prose is not a general writing engine.
