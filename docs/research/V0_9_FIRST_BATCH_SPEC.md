# v0.9 first batch: real manuscript input and whole-paper review

2026-09-13. Original scope: 9A/9B; the subsequently authorized 9C task foundation is in section 7.
The author approved the version direction and preparation
of this specification and the hotspot-led scientific focus. First-batch implementation is
authorized and underway; no v0.9 release has been made.
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

Approved question: how does a cooling structure's thermal advantage depend on flow rate,
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

First-batch interface:

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
limitations. The author has confirmed the hotspot-led question. Implementation proceeds on
`workstream/v09-writing-review`: the controller owns CLI and integration, the scientific input
task owns the private trial, and the review task owns the new review module and focused tests.
There is no need to wait for new simulation. The first generated draft must remain preserved.
This document is the concise first-batch specification. Do not expand it into a multi-thousand-line
implementation script or repeat the v0.8 validation to approve it.

### First implementation checkpoint

9B now exports a whole-paper snapshot with global/local locators and retains complete raw review
reports. It reuses actual manuscript assembly for currentness and the existing section packets;
no new database, revision engine or approval workflow was added. The writing Skill includes a
whole-manuscript review reference. The root CLI and installed-wheel import/export were exercised.
89 focused CLI, manuscript, Skill and review tests passed. This is a local development result,
not a supported-platform release or proof of scientific writing quality.

9A has a prepared eight-section input built from a selected subset of the existing real cases.
The first generator has no prior cooling manuscript or evaluator text. A private builder supplies
explicit cross-row differences before standard scalar bindings; the public assembler has not
gained a general cross-row formula engine. Original scientific sources and first drafts are preserved.

The first eight-section candidate assembled successfully and was exported to a seven-page DOCX/PDF.
The first draft is retained separately from a format-only derivative using existing native math.
Actual page inspection found an internal Celsius unit spelling in bound text and tables; the shared
display formatter now renders it as °C without altering source values or units. Its regression and
related section/manuscript tests passed (85 tests). All seven final PDF pages were inspected: body
indentation, paragraph spacing, tables and equations were readable, without observed clipping.
The inherited field image still needs publication typography, a degree symbol and panel labels;
its original pixels were not silently redrawn. This is an external-review candidate, not submission
approval or an independently validated new research domain.

The complete review package now includes real Word/PDF, raw tables, definitions, literature support
and exact paragraph/object locators. Remaining scientific-writing questions include literature
coverage, numerical density, model-form and local hotspot mesh support. Await complete external
feedback before selecting 9C changes. No external-review result or v0.9 release is claimed.

## 7. Next batch: selected-review editing tasks (9C foundation)

The author requested the next step after the first candidate and review package. Implement the
thin editing-task route now on public examples; the real candidate's external review has not
returned, so do not manufacture findings or apply unreceived recommendations to that manuscript.

Interface: `cfdpaper review PROJECT --package REVIEW_RETURN --actions ACTIONS --output EDIT_TASK`.
`--report` and `--actions` are mutually exclusive. The host reads the COMPLETE returned report,
then writes the small action mapping; the author is not required to transcribe a report into JSON.
The mapping contains `package_id` and an `actions` list. Each action has a unique `id`,
`decision` (accept/reject/defer), exact nonempty `report_quote`, and nonempty `rationale`.
Accepted actions also have a nonempty `instruction` and at least one target. Paragraph targets
have `section_id`, `paragraph` (1-based integer) and exact nonempty `quote` from that paragraph;
object targets have `section_id`, `kind` (figure/table/equation/reference) and `global_number`.
If several local citation roles share one global number in that section, optional `local_id`
from the locator index disambiguates the role; do not make a legitimate target unselectable.
Optional `related_sections` maps section IDs to reasons for reconsidering connected prose.
Rejected/deferred actions may remain unmapped; they do not become editing instructions.

Check quotations against the complete readable report and reviewed paragraph, resolve object
identities through the existing locator index, and reject ambiguous/absent accepted targets.
Do not interpret a found quote as proof that the recommendation is scientifically valid.
The package identity must match; unavailable readable extraction needs host completion first.
No fuzzy retargeting, approvals, numerical edits, new database or scientific scoring is added.

Output preserves the return (including original report), the selected mapping, and a fresh
`working/` copy of the reviewed manuscript's existing inputs/drafts. Include the current builtin
writing Skill and linked references using the existing installed/source lookup so an external
host receives the same focused guidance. `TASK.md` identifies selected
targets, their exact quotations/local draft paths, and explicitly related sections. It directs
the host to alter existing authoring files only where justified, retain value/citation tokens,
leave unrelated drafts untouched, and use ordinary manuscript assembly to a NEW candidate.
Copied preview files are historical reading aids, never the revised output. For a later author
candidate, reconcile against the reviewed snapshot first; this route does not merge into it.

Controller owns CLI, integration, tutorial and the existing Skill reference. The bounded module
task owns `publication/manuscript_revision.py` and its focused tests. Reuse review copying/locators
and the existing assembler, do not modify shared contracts. Tests cover exact and stale quotes,
ambiguous targets, unknown sections, reject/defer preservation, full raw report retention, a moved
task, and editing one public-example draft followed by ordinary assembly with unrelated drafts
unchanged. Any self-authored test report is explicitly synthetic, not an external-review success.

This completes task preparation, not automatic scientific revision. Real before/after writing
evaluation and selected implementation improvements remain pending the actual complete report.

### 9C foundation result

Implemented `review --actions` with complete-return retention, paragraph/object resolution,
accepted/rejected/deferred decisions, related-section reasons, a portable ordinary authoring copy
and the current builtin writing Skill. Native equation expressions use the existing math-text
renderer in tasks. Optional local citation identity resolves multiple roles sharing one reference.
No original draft or evidence is edited by task preparation.

68 relevant revision/review/CLI/Skill tests pass; Ruff and Skill validation pass. A non-editable
wheel installed outside the repository ran export → complete synthetic report → selection →
task relocation → one local host edit → ordinary reassembly. The retained original and unrelated
drafts stayed unchanged, and the installed package supplied the complete writing Skill/reference.
This is a software integration demonstration, not an external scientific review.

The real seven-page cooling manuscript and its review ZIP remain unchanged. Receive the complete
actual feedback, assess its supported actions, then use this path for the real before/after trial.
No release, new simulation, private source edit or externally approved scientific improvement is
reported for this batch. Continue from the current workstream, not a released tag.

## 8. Real external review: selected implementation batch

The author accepted the controller's assessment and authorized the next batch after a complete
real review returned. Keep first drafts and raw evidence. The report supports scalar fidelity
but identifies complementary-metric interpretation, source-dependent paired calculations and
editable-document presentation as concrete product work. It does not establish submission readiness.

Scope: add `scalar_select` (one record, no CV) and `paired_change` to existing table calculations,
with exact pair identities within groups, signed differences and explicitly normalized relative
changes. Preserve source records and recompute at ordinary section/manuscript assembly. Absolute
temperature ratios require a declared temperature-rise reference; retain missing values and
zero-denominator cases as unavailable. Keep historical population/partition serialization stable
so old reviewed snapshots do not become falsely stale. No formula language or new database.

Update the existing writing/review references to consider response-specific rankings, complementary
metrics, normalization denominators and monitored versus reported operators. Apply these through
the existing selected-review route to an independent working copy; host-authored improvements are
not automatic scientific discovery. Use synthetic calculation/source-change tests for public code,
and keep real-case values, full review and draft comparison in the ignored private trial.

In parallel fix confirmed native-math and short-table rendering defects in the shared elements
module, preserving editable equations and long-table pagination. Render actual outputs with an
available permitted engine; structural tests alone do not establish cross-engine visual success.

Ownership: controller owns table_evidence.py, section.py, analysis_section.py, writing Skill,
tests and integration; scientific-revision task owns private selected-revision/; export task owns
elements.py and test_elements.py. No changes to contracts.py, public schemas, release/version,
original solver results or accepted field data. No new simulations or v0.9 publication this batch.

### Selected batch outcome

Both operations are implemented through the existing section and analysis-figure paths. Public
tests cover unique selection, exact pair identity, missing/duplicate members, zero denominator,
temperature-rise invariance under Celsius/Kelvin origin change, historical-input serialization,
and a raw-record change propagating its recomputed ratio to Results and bound summary chapters
without changing their authored drafts. The old reviewed snapshot also remains usable.

The real selected revision reuses the full returned report and unchanged raw records. Its principal
spread ratios and temperature differences now use the paired operation; other supplied scalar
records use explicit selection. Host-written prose explains response-specific sensitivity and
complementary field statistics. This is improved host-guided writing, not automatic mechanism
discovery or independent scientific validation.

454 publication/review-CLI tests pass; two optional Pandoc tests are skipped. Ruff and Skill
validation pass. The generic native-math and short-table corrections were used to export the
revised eight-page manuscript with Word; all pages were inspected with no observed clipping,
broken equations or orphan final table rows. Bundled LibreOffice is unavailable, so its specific
cross-engine reproduction remains unresolved. Original field-artwork labels and final effective
image resolution remain in the next batch, alongside native-field dependency completion.

No public release, new solver run, geometry/property change or scientific-readiness approval.

## 9. Portable figure dependencies: product-first follow-up

The author explicitly reiterated that this trial must improve the Agent, not become an
indefinite private-manuscript editing job. This batch addresses an existing portable figure
task defect: relocating every source into an ID-specific folder breaks relative script/helper/
field paths. New tasks retain declared input paths under `sources/`; existing imported task
paths remain readable. No new registry, solver adapter or arbitrary script runner is introduced.

The importer additionally reports raster pixel dimensions and effective ppi at the task's final
width, independent of image DPI tags. This does not measure later Word/PDF downsampling. The
builtin figure Skill covers native-array/geometry/helper dependencies, domain and unit identity,
geometry assumptions in regional statistics, panel/colorbar labels and final embedded size.

Public tests run a declared script with its sibling helper and nested source data after both
task relocation and delivery relocation, with original source directories removed. A separate
test verifies that an inflated DPI tag cannot inflate calculated effective resolution.
The private four-field trial exercises the same public task/import path, using original native
facets and isolated outputs. It is a regression example, not a new universal field-analysis
adapter, automatic mechanism discovery or a substitute for model/mesh evidence.

### Portable figure batch outcome

50 relevant figure-task, CLI, whole-review and builtin-Skill tests pass; Ruff, formatting and
Skill validation pass. The native trial used the public prepare/import functions and reran its
host-authored script after relocation. Recomputed records and preview pixels remained identical.
All four native facet files were retained, without duplicate field copies within a bundle.

The field trial reproduced supplied interface SD to floating precision; mean and regional mean
differences at export/arithmetic precision were retained, not relabeled as physical error bounds
or used to change the manuscript. Its four-format figure changes only degree/panel labels. At
160 mm width the 1980-pixel preview gives 314.325 ppi, regardless of its stored DPI tag. Original
Word/PDF embedding remains unchanged and still needs later final-output verification.

This batch changes reusable interchange behavior and the shipped figure guidance. It does not
add a universal native-field analysis engine, modify the current manuscript, or release v0.9.

## 10. Evidence gaps and linked scientific revision

2026-09-14. Continue product improvement rather than private-manuscript polishing. Accepted
scientific actions may set `trace_evidence: true` in the existing action input. Task preparation
then uses current section bindings and draft evidence IDs to locate paragraphs, tables and
equations using the targeted evidence. Paragraph and table/equation targets select their declared
evidence; reference targets use the local citation evidence ID; figure targets use the evidence
of explicitly associated paragraphs. Output includes actual draft locations and canonical owning
evidence IDs, without equating same names, numeric values or prose with a scientific binding.

This is optional rereading assistance, not semantic validation or editing permission. Normal
wording/format changes do not expand into evidence review, and rejected/deferred actions cannot
create active evidence-use lists. Free-text copies and undeclared model dependencies still need
host judgment. No new database, public contract, approval stage or automatic source modification.

Builtin writing guidance distinguishes omitted-but-available material, conflicting definitions,
and unestablished scientific evidence. It directs the host to existing case-specific records,
to preserve supported conditional results while narrowing unjustified inferences, and to suspend
only the affected claim where its definition/comparison cannot be established. Summary statements
must be reread with the revised body claim; adding caveats does not repair missing support.

### Outcome

62 revision/review/CLI/Skill tests pass; Ruff, formatting and Skill validation pass. Tests cover
result-to-summary and summary-to-owner links, object targets, old action behavior, false matches
from identical local IDs/prose, and no active tasks from deferred advice. Current private-trial
lookup identifies nine paragraphs and one table across four sections sharing the chosen hotspot
evidence. It does not edit or scientifically approve any of those passages. Three existing-review
examples illustrate the host's evidence-gap decisions; they are not autonomous classification
tests. P04's recorded diagnostic-versus-quantitative-source lessons were reused without reopening
its source assets. No new CFD, manuscript rewrite, format regression or v0.9 release this batch.

Next: assess v0.9 against its bounded software scope and consolidate the candidate. Keep the
remaining model/mesh/literature and final-preview issues explicit; do not claim their closure
from software tests, or turn a trial paper's unperformed scientific studies into endless product
development. Any eventual release description must distinguish these levels.

## 11. Candidate consolidation — 2026-09-14

The bounded v0.9 software scope is implemented. A separate read-only scope review found no
missing feature required by sections 1–10. Publication preparation, not another scientific
feature batch, is the next step.

| Scope | Current disposition |
|---|---|
| Real-material input, first draft and complete external feedback | Trial completed and retained privately; not a submission-ready or independently validated paper |
| Whole-paper export, full report return and selected editing | Implemented; public installed-CLI round trip preserves original reports and unrelated drafts |
| Paired calculations and cross-section evidence rereading | Implemented; exact source identities and explicit bindings, with host interpretation |
| Portable figure dependencies and printed-resolution reporting | Implemented; known native-field script replay completed, not a generic solver adapter |
| Word presentation repairs | Implemented and prior actual Word pages inspected; no new cross-engine visual claim |

The first full regression uncovered a real integration error: material-analysis proposals use
`comparison` for scientific qualification, while paired calculations use it for a row selector.
Remove the proposal's inheritance collision, preserve its population/partition input format,
and validate its calculation payload through the existing table model. Qualifications, units,
definitions, source membership and missing-value checks remain active. The saved proposal keeps
its scientific comparison object; the emitted table calculation does not receive that object.
One obsolete test expecting `review` to be unimplemented now checks the still-roadmap `revise`.

Verification: 57 targeted tests passed after this fix. The subsequent full run produced
1512 passed, 5 skipped and one documentation-state assertion failure introduced by the updated
README. After keeping the established capability-state vocabulary, all three public Quickstart
tests passed. No production code changed after that full run. The five skips are two optional
Pandoc checks and three Windows symlink-permission checks. Ruff lint/format and diff checks pass.

A non-editable wheel installed outside the repository ran the analytical seven-section example,
complete synthetic report return, evidence-linked task relocation, one explicit host wording edit,
reassembly and DOCX export. Four sections shared the selected evidence; originals and unrelated
drafts stayed unchanged. Word retains a table, native math and two images. The older material-analysis
example also runs from this installation. The reusable review example is now part of installed-wheel
CI; it is explicitly synthetic, not an independent AI or scientific-review result.

Remaining release work: synchronize version/CITATION/CLI/CI and release-facing documentation,
run the supported Windows/Linux Python 3.10–3.12 matrix and package job on the final candidate,
then merge/tag/publish through the normal release route. This batch does not change the version,
push, merge or publish. Private CFD sources and the trial manuscript remain unchanged.

The trial's model applicability, hotspot-QoI mesh support, literature breadth and final composite
preview remain author/research tasks. They constrain scientific claims about that trial; they
are not prerequisites for shipping the bounded review/editing software with accurate limitations.
