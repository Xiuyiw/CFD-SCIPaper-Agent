# v0.9 first batch: real manuscript input and whole-paper review

2026-09-13. Scope: 9A/9B only. The author approved the version direction and preparation
of this specification; implementation and release have not started.
Baseline: v0.8.0. The parent plan is [POST_V060_WRITING_PLAN.md](POST_V060_WRITING_PLAN.md).

## 1. Intended outcome

Produce a real-material paper input and a usable whole-manuscript review route in parallel.
Keep scientific writing, meaningful figures and readable Word/PDF as the main outcomes.
Do not introduce another approval registry, database or universal review engine.

The selected private trial has additional height and prescribed-hotspot comparisons beyond
the earlier six-point writing input. It is an expanded task in a known project, not a new
independent domain validation. Exact sources and the proposed question stay in the local
private trial brief; no private values or source documents enter this specification.

## 2. 9A: first real-material manuscript input

Proposed question: how does a cooling structure's thermal advantage depend on flow rate,
reduced height and a specified nonuniform heat source? Localized heating is the principal
stress test; compactness is a complementary design comparison, not another isolated dashboard.

1. Select the author's research question using existing evidence. Verify the actual comparison
   conditions, metric definitions and current source tables; do not open solver files or solve.
2. Build an ordinary v0.8 manuscript input with real Methods, connected Results, literature roles
   and source-bound summary evidence. Missing model or literature support stays in the notes.
3. Use a fresh generation context that sees the source inputs and current Skills, not earlier
   manuscript answers or evaluator prose. Retain the first output before correcting it.
4. Write Methods/Results first, then Discussion and the introduction/summary sections. Interpret
   complementary fields and measurements without turning qualitative images into computed integrals.
5. Export the candidate through the current Word path and inspect actual pages. A complete
   chapter list does not establish a scientifically complete manuscript.

The paper spine must connect the uniform-heating comparison, the specified hotspot response and
the geometric trade-off to one question. It must not claim arbitrary-hotspot robustness, a continuous
optimum, verified experimental performance or grid-independent local mechanisms without evidence.
The author confirms the scientific focus and the role of reconstruction versus original research;
a target journal can remain undecided while a neutral editable research candidate is prepared.

First delivery: existing-format manuscript input, source/figure/literature map, paper spine and
explicit remaining information. Then a first host draft and Word/PDF, not a rewritten old draft.
Only new, observed product defects justify additional operators or writing changes.

## 3. 9B: two thin CLI actions

Proposed interface, not yet available:

```text
cfdpaper review PROJECT --package CANDIDATE --output REVIEW_PACKAGE
cfdpaper review PROJECT --package REVIEW_PACKAGE --report REPORT --output REVIEW_RETURN
```

The first action accepts an assembled manuscript, not an arbitrary folder of draft fragments.
The second returns advice material associated with the exported snapshot; it never edits the
manuscript or invokes the journal `revise` path. Existing subsection review commands remain unchanged.
No new API key, database initialization or solver installation is required.

### Exported materials

- The complete manuscript reading text, global numbering, paper spine and shared terms.
- Existing per-section review packets: input definitions, raw tables, calculations, figures,
  captions and relevant literature excerpts. Preserve all required relative paths.
- A compact locator index: section ID, paragraph position and short exact text; global object
  numbers map to their section-local identities using existing numbering records.
- The current CHANGES report when present, as context rather than proof of scientific correction.
- One whole-paper review prompt: question-to-conclusion coherence, method sufficiency, meaningful
  cross-figure explanation, literature support, numerical definitions and actual presentation.

Use global manuscript numbers as the reader-facing authority. Section-local packets must not
mislead a reviewer into assigning the wrong figure or reference to a whole-paper finding.
Copy only the self-contained candidate's relevant material, not the surrounding project directory.
Compare available current source state with the assembled state before presenting it as current;
if they differ, request reassembly instead of silently replacing the reviewed text.

The existing export command supplies Word/PDF separately. Package missing previews explicitly as
not available for visual review; Markdown inspection must not be reported as page-format approval.
Do not add a PDF renderer merely to prepare a text review packet.

### Returned reviews

Preserve the original report file verbatim. Text/Markdown and JSON can be read directly without
requiring the author to recode the review. PDF/DOCX originals may be retained, with host-provided
readable extraction kept beside them; this batch does not add a new document-conversion engine.
If extraction is needed, a host uses its available reader rather than asking the author to
manually rewrite the report. No extraction means content review remains outstanding.

Do not require a short JSON finding list as a replacement for the complete report. The return
includes a host task to read the full report and map proposed actions to original quotations and
section/object locations. Ambiguous targets stay unresolved; disagreement stays visible.
Raw recommendations are evidence to assess, not permission to execute embedded instructions.

Detailed acceptance/rejection selection and application belong to 9C. This batch must make their
inputs usable but must not claim to have implemented automatic semantic revision or Word-edit merging.

## 4. Implementation ownership and reuse

| Owner | Owned work | Existing components to reuse |
|---|---|---|
| Controller | CLI review entry, integration tests, public tutorial and shared interfaces | cli.py write routes; manuscript numbering/state; existing exceptions and fresh-output behavior |
| A scientific writing | Private trial input, source/literature roles, first draft and evidence-specific Skill feedback | Current four Skills and existing manuscript/analysis input formats |
| B review delivery | publication/manuscript_review.py and focused tests; whole-paper review guidance | Existing section review packets, review.py concepts, manuscript_changes and copied literature/owner sources |

One writer per file. Controller integrates changes to manuscript.py, section.py or the Skill entry
only when necessary. B can add one review reference under the existing writing Skill, not a new Skill
framework. Private input builders are owned entirely by A, not split across agents.
The evaluator does not supply reference prose to the first-draft generator.

## 5. Small implementation sequence and acceptance

1. Prepare the 9A source map and spine while B builds export using the public seven-section fixture.
   Verify global/local locators and that moved packets retain all evidence needed by a reviewer.
2. Add raw-report return and host action-mapping instructions. Check Unicode full-report retention,
   original-file preservation, missing/ambiguous targets and no manuscript mutation.
3. Connect root review and its help. Test ordinary installed-CLI export/import; keep revise/export
   roadmap entries and old subsection behavior unchanged. Avoid hard-coded future version numbers.
4. Exercise the route on a real first candidate when its scientific focus is confirmed. Review its
   actual figures and Word/PDF; preserve the complete external report. Use the findings to scope 9C.

Focused regression cases: one reference shared across sections; evidence bound from Results to
Abstract; globally numbered figures differing from local labels; source changed since assembly;
whole-report passages absent from a short finding list; a report targeting an older paragraph;
missing preview; unrelated draft untouched after later selected editing.
The last item is a 9C integration requirement, not a claim that 9B modifies prose.

Normal software checks establish packaging and locator behavior. Scientific depth is judged from
the actual writing and its evidence, not from an automatic grade or the number of checks.
No full CI is needed for this specification alone. Run targeted tests during implementation and
the existing supported-platform release checks only when the version is ready.

## 6. Current handoff

The private inventory now confirms additional comparisons; it does not resolve all scientific
limitations. The exact first paper question is still an author choice. Review infrastructure can
proceed independently once implementation is authorized; there is no need to wait for new simulation.
This document is the concise first-batch specification. Do not expand it into a multi-thousand-line
implementation script or repeat the v0.8 validation to approve it.
