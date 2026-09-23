# From v0.10.1 to a mature author-in-the-loop CFD writing system

2026-09-23. Status: scope accepted; first implementation batch is in local development on
`workstream/linked-diagnostics`. No release is declared. This updates forward priorities,
not the historical release record.
Baseline: released v0.10.1, local main `e66654e`.

## 1. What maturity means

The target remains a solver-neutral, host-AI-assisted paper-production system starting from
mature results. A researcher supplies available results, definitions and a research intention;
the host inspects them, proposes useful comparisons, uses reproducible computations and tools,
and develops an author-reviewed argument. The researcher should not have to design every
calculation, write input JSON or supply the finished scientific explanation first.

Maturity does not mean unattended discovery or automatic acceptance by a journal. It means
reliable scientific assistance on a new supported project, useful editable figures and papers,
manageable author corrections, and predictable continuation after changes.

Retain the priority allocation: 55% science/analysis, 25% figures/writing, 10% usability and
adaptation, 10% necessary reliability. These are effort priorities, not line-count quotas.
Keep three author decisions: research direction; evidence/analysis/figure choices; final paper.

## 2. Assessment of the current product

The package is an operational research workbench, not yet a broadly demonstrated mature
scientific-writing agent. Software delivery is ahead of evidence for scientific-writing quality.

| Area | Demonstrated capability | Remaining maturity gap |
|---|---|---|
| Scientific intake | Bounded CSV previews with full sources, NPZ metadata and explicit 1D mappings | Meanings still need method-backed host interpretation; native solver extraction is not public functionality; individual portable sources over 20 MiB are skipped |
| Numerical analysis | Source selection, paired source values, declared population/partition/weighted statistics, supplied regional fractions | Comparing calculated diagnostics still needs host glue; extrema, exceedance, geometry intersections and transient analyses are not generally available |
| Scientific explanation | Located evidence, complementary-diagnostic guidance and host-written subsections | No demonstrated stable writing-depth gain in the retained v0.9/v0.10 paired trial; rules and valid evidence IDs do not establish a sound argument |
| Figures | Reproducible basic data plots, portable external figure tasks and editable returns | Complex maps/diagrams depend on host tools; effective resolution alone does not establish readable final-size typography or appropriate scientific encoding |
| Whole-paper writing | Shared spine/literature, global numbering, bound values and selective editing | Novelty, model applicability, mechanism support and cross-section conclusions still need substantial host/author reasoning |
| Documents and continuation | Native tables/math, house paragraph styles, Word export and explicit change reports | Actual pagination needs visual checking; image font metadata may be missing; Word-only author edits do not return automatically to drafts |
| Generality and revision | Public synthetic examples, known-project trials and external-review exchange | Three real heterogeneous project validations and a complete real-journal revision workflow remain incomplete |

Do not reopen fixed defects: the old 8 MiB CSV profiling exclusion, NPZ-to-CSV detour and
numerical line breaks were addressed in v0.10.1. The separate 20 MiB copying limit remains.
The released regional operation consumes fractions; it does not calculate geometric overlap.
The latest array replay did not regenerate scientific prose, so it cannot establish writing gains.

Current implementation anchors:

- `src/cfdpaper/analysis_suggestions.py`: HOST_PROMPT, source copying and proposal compilation.
- `src/cfdpaper/publication/table_evidence.py`: calculations and allowed result fields.
- `src/cfdpaper/publication/manuscript_changes.py`: explicit-dependency change suggestions.
- `src/cfdpaper/publication/figure_tasks.py` and `style.py`: figure import and final-size metadata.
- `skills/cfd-evidence-writing/references/mechanism-subsections.md`: existing diagnostic guidance.
- `V0_10_SCIENTIFIC_WRITING_PLAN.md`: retained trial findings and delivered increment.

## 3. Proposed v0.11 outcome: linked diagnostics and scientific interpretation

One coherent user outcome: move from exported fields/tables to complementary numerical
comparisons, a scientifically useful Results/Discussion argument, a matching figure or table,
and consistent manuscript summaries. Keep the whole-paper spine in view while testing the
most demanding results subsection; do not spend the release polishing one picture in isolation.

### A. Compare computed diagnostics without manually copied intermediate values

Extend the existing calculation/result-reference path for a difference and, where meaningful,
a relative change between two computed scalar results. A first example is comparing spatial
means or SD between matched cases. Reuse existing calculation objects; no arbitrary expression
language, unrestricted execution, new database or general dependency framework.

- References retain upstream source, case, physical domain, operator, weighting and unit.
- Paired quantities need compatible definitions and an explicit physical comparison; equal
  units alone do not establish comparability. Do not require identical geometry for every
  legitimate integrated comparison, or silently accept unrelated reporting domains.
- Differences of absolute temperatures have difference units. Relative absolute-temperature
  comparisons keep the existing reference rules; zero/unsupported denominators remain missing
  or actionable errors, not fabricated percentages.
- Reuse the existing result fields in prose, tables and plot inputs. Source updates recompute
  both parent values and the contrast; missing parents never reuse a stale numerical answer.
- Begin with a shallow, bounded relation between existing scalar outputs. Validate missing
  references and cycles if the chosen representation can express them.

This is an analysis capability, not proof of improved writing. Add no further statistic unless
the selected scientific question requires it and the source supports its definition.

### B. Give the host the evidence needed to explain and revise the result

Use existing host tasks, section duties and CHANGES/selected-editing outputs. Present the
question, relevant field observations, complementary calculated results, definitions and
located literature together. Give the host a clear task to explain a relationship rather than
list every available number. Reuse current guidance; do not add a mandatory paragraph formula.

For source changes, provide the old/new bound result and the affected paragraph, associated
figure and summary sections. Explicit paired-result sign/ranking changes may be identified
numerically; their scientific significance and rewritten wording remain host judgments.
This is targeted assistance, not semantic validation of every free-text claim.

The host should distinguish what the field shows, what a calculation establishes and what a
mechanism would require. Where alternative explanations remain possible, state the useful
finding and request only the discriminating missing observation. Avoid repeated defensive
qualifications and invented mixing, stability or causal claims.

### C. Improve the matching figure and manuscript presentation in parallel

Use the existing external-tool route, not a new universal plotting editor. Choose one useful
public field-comparison task/template: common-scale absolute views, an identity-matched
difference when justified, and a compact spatial or aggregate diagnostic as the question needs.
No mandatory six-panel layout, decorative complexity or full-width chart of two scalars.

Carry known source width, target width and font-size information from the returned figure into
Word sizing. Unknown fonts remain unmeasured; DPI must not stand in for readable lettering.
Preserve editable scripts/vector output and actual source dependencies. A source change may
request a new figure, not silently relabel an old image as current.

Different field meshes cannot be subtracted by array order. Require a justified mapping or
continue separate aggregate comparisons. Supplied regional fractions remain supported;
arbitrary 3D intersection, remeshing and interpolation are outside this batch.

Inspect the actual manuscript-width export, including a long table, equation and figure/caption
page break in the representative manuscript. Fix shared renderer defects only when reproduced.
Do not rerender old unchanged tutorials to accumulate evidence.

### D. Remove only demonstrated input/host friction

Record host-written conversion/glue code and actual technical recovery attempts in the selected
task. If its relevant source exceeds the current copy budget, support an explicit size policy
or deliberate portable export within the existing intake path; do not silently drop the source
or remove every resource bound. A broad solver connector is not a prerequisite.

The host, not the author, prepares machine-readable mappings from available definitions.
Ask the author only for missing scientific meaning, a consequential choice or new data.

## 4. Work sequence and division of responsibility

| Step | Owner and boundary | Deliverable and stopping condition |
|---|---|---|
| 1. Select the task | Controller; existing source maps only | One evidence-sufficient primary task and a different known-case regression; record available inputs and missing evidence once |
| 2. Implement A/B | Scientific implementer: calculation engine and focused tests; controller: proposal/result bindings and change-task integration | Upstream calculation, contrast and paragraph/table values agree; affected explanations are reachable through existing tasks |
| 3. Implement C/D | Publication implementer: figure metadata, applicable style/export code and tests; controller: material-intake limits if reached | One portable scientific visual task plus readable representative pages, without hand-editing a private PDF as a product fix |
| 4. Evaluate the outcome | Fresh host task plus controller/author or external reviewer | Preserve first draft, review scientific reasoning and presentation once, fix concrete reusable defects |
| 5. Integrate | Controller | Update skills/examples/docs, run changed-path tests and normal release CI, report actual improvement before deciding to publish |

Use the controller and two bounded implementation collaborators when implementation is approved.
Assign files before starting; shared section/CLI/contracts/version/release changes remain controller
owned. A fresh writing attempt can use a new isolated task after implementation, not an additional
permanent agent. Do not create new user-visible chats or transfer approval responsibilities without
the author's request. Maintain progress here and in the existing local recovery entry.

## 5. Evaluation that tests the product rather than a polished demonstration

Use two distinct scientific questions for first-draft comparison with installed v0.10.1 and the
candidate under matching host settings, inputs and time/tool allowances. At least one must not
repeat the already revised subsection. Preserve unassisted first outputs before feedback.
Known P04/cooling materials remain known-project evaluation even when a particular task is new.
Do not claim statistical superiority from a few attempts or require the baseline to fail.

For each task, compare concrete passages and figures, not a self-assigned maturity score:

1. Correct case/domain/unit/normalization and reproducible quantitative contrasts.
2. Diagnostics that actually address the question, including a conflicting response if present.
3. Field-to-metric explanation, useful engineering meaning and evidence-appropriate mechanism.
4. Literature used in its verified role; no unsupported novelty or validation assertion.
5. Manuscript consistency, concise natural prose and actual final-size visual readability.
6. Host glue code, technical repair attempts and author corrections. Record elapsed author time
   only if actually measured; test counts do not measure scientific quality.

Numerical/unit/case hard errors must be corrected. A reported writing improvement must point to
specific defects reduced without introducing a new unsupported explanation. If outputs are equally
good but host preparation is smaller, report the usability gain. If no useful outcome improves,
do not create another minor release merely because more code or instructions exist.

One bounded external/author review is sufficient for this increment. New simulations, unresolved
model applicability or unavailable literature cannot be closed by software or extra caveats.
Continue supported software work while identifying the exact external evidence needed.

## 6. Reuse the valuable assets, without overfitting to them

| Asset family | Transfer into the product | Evaluation boundary |
|---|---|---|
| P04 Fig.5/8/12 | Read field evolution before quantitative anchors; preserve source/transport and displayed-quantity distinctions | Known-case diagnostic examples, not new blind scientific validation |
| P04 Fig.9/10/13/14 | Complementary metrics, spatial support, normalization and multiple-evidence explanation | Use selected relevant definitions and final-author decisions, not every historical plot version |
| P04 Introduction/Methods/Conclusions and revision history | Question/design/result alignment, sufficient reproducibility, literature roles and natural non-defensive prose | Generalize the method; never copy combustion-specific claims into other domains |
| Cooling reviews and paired first drafts | Domain confusion, denominator effects, local-versus-global response and real Word defects | Keep original first attempts; distinguish manuscript repair from implemented capability |
| Recent field-comparison figure practice | Common scales, identity matching, regional profiles and threshold distributions where justified | Reuse the design method, not private data or an unverified physical interpretation |
| SG_Baffle/Gate 5 failures | Incomparable cases, weak convergence, incorrect monotonicity and false approval | Negative regression; not a successful independent generality demonstration |

Resolve private files from the existing local asset map when needed. No new archive inventory,
no original-file edits and no private data in public examples. Public analytical examples carry
known answers; future unfamiliar-project evaluation must not receive those evaluation answers.

## 7. The work after this increment

Keep the original V2 ambitions, but schedule by the next demonstrated user bottleneck rather
than promising a version number for every unfinished module.

1. **Whole-paper scientific quality and literature:** a genuinely new project's complete
   paper spine, Methods, mutually supporting Results/Discussion and consistent Abstract/Conclusions;
   closest-study comparison and source-backed citation assistance through existing tools.
2. **Practical intake and spatial/temporal breadth:** a real solver read-only export path when
   licensed access is available, plus solver-neutral support; useful regional/temporal diagnostics
   driven by real input. No running new simulations as a hidden writing step.
3. **Author editing and journal delivery:** selective Word paragraph change return, broader
   journal layouts/citation requirements and complete submission files where actually requested.
   Begin with bounded text reconciliation, not an unrestricted DOCX round-trip promise.
4. **Real revision support:** connect a real decision letter to evidence-backed actions,
   manuscript changes and responses. Reuse P04 methods without fake reviews or acceptance.
5. **Broad maturity demonstration:** real single-phase flow/pressure-drop, heat-transfer and
   transient or multiphase projects, covering at least two solvers or solver plus neutral exports.
   Existing synthetic pipe and known P04/cooling examples do not close all three requirements.

For a mature release, these supported-domain tasks must work from documented existing inputs
without bespoke hidden builders or a developer repairing every stage. Report author intervention
and remaining evidence honestly. Automatic submission, unattended appeals and universal mesh/solver
support are not necessary targets. A version label or a percentage cannot replace these outcomes.

## 8. Implementation progress and next work

The author authorized implementation with “继续下一步”. The controller integrated two bounded
workstreams without changing the released main/tag or reading private research inputs:

- A: `result_comparisons` compares two compatible computed scalars without a transcribed
  intermediate table. It preserves two upstream locators, propagates through section tables,
  prose, plot inputs and cross-section bindings, and recomputes after source changes/moves.
  It is shallow: no comparisons of comparisons, inferred units or inferred physical comparability.
- B: the existing change report now gives affected paragraph text, associated figure paths/captions
  and old/new unrounded computed values. Changed difference signs are numerical review cues,
  not automatic scientific judgments or prose rewrites.
- C: external figure deliveries carry declared source width/font and target width into the
  existing Word sizing path. Tests verify the actual DOCX image width, scaled font metadata,
  and retained body indentation/spacing. This is not automatic font recognition or rendered-page QA.

The public `examples/spatial-diagnostics/run_linked_example.py` reuses existing analytical wall
inputs to show opposing mean/SD changes. It is a recorded example, not a fresh AI quality trial.
Built-in QoI and figure Skills explain the new route without introducing another approval system.
Related publication/analysis regression and added integration tests pass; no version bump, push
or release has occurred. The shared code changes are not yet a demonstrated writing-depth gain.

Next: exercise the implemented route on two distinct scientific questions from existing relevant
materials, retain first outputs, and assess actual explanation and manuscript-width rendering.
Reuse the selected P04/cooling evidence map, not a full archive sweep. Do not relabel the old paired
first drafts as new trials. Correct only demonstrated shared-product defects. Final integration,
cross-platform CI and release follow a useful outcome; no additional simulation is required merely
to test this batch. Unknown-project validation and broader maturity work in Section 7 remain open.

### 2026-09-23: paired real-material questions and corrective implementation

Four first attempts are now preserved: released v0.10.1 versus the candidate on a cooling
spatial-support question and a P04 pollutant/input question. These are known-project examples,
not unfamiliar-project validation. Both versions produced generally sound, numerically supported
subsections. The pollutant candidate exercised computed-result comparisons, but the paired outputs
do not establish a systematic writing-depth improvement. No rewritten manuscript is counted as a
product capability. Seven initial Word/PDF pages were inspected with each version's exporter.

Actual friction drove three small corrections, instead of another rule/audit layer:

- Expose existing scalar_select and paired_change through the analysis-proposal entry; keep its
  scientific comparison qualification separate from the paired row selector. Explicit scalar
  temperature semantics survive into result comparisons without changing old ordinary payloads.
- Typeset supported scaled units and keep number/scale/unit groups together in Word. This changes
  presentation, not source values or scales. The original pollutant draft was reassembled and its
  repaired one-page PDF inspected separately from the first attempt.
- Remove the stale writer-reference statement that calculated-output differences are unsupported.

The original cooling declarations now pass directly through proposal -> compile -> build ->
unchanged draft assembly, yielding identical paragraph and table records without editing the
compiled intermediate input. This is a usability replay, not a second independent writing test.
Related regression: 698 passed, 2 skipped; targeted lint/format and Skill checks pass.

Still visible: mixed-unit long tables need an explicit host extraction/pivot; long unit/basis
labels repeat in bound prose; near-reference figure placement can leave substantial page space;
some first-draft wording still carries process language. Do not claim automatic publication-ready
layout or significant scientific-depth improvement from these results. Existing writing guidance
already covers reader-facing language, so do not add another general rule list for this trial.

Next is installation/integration validation of this implemented increment. Then address the
demonstrated intake/unit-expression/layout friction and the whole-paper/unfamiliar-project work
in Section 7. Do not keep rerunning these known questions. Local private evaluation details and
first outputs are retained under private-fixtures/v011-linked-trial; no private data enter the
public examples or tests. Released version remains v0.10.1; no release was performed here.

### 2026-09-23: installed-package integration

The local full regression completed with 1722 passed and 2 skipped; whole-tree Ruff checks and
format checks passed. A wheel built through the source distribution was installed non-editably
in a fresh Python 3.12.14 environment outside the checkout. The installed module resolves to that
environment, not the development source tree. The wheel and source archive exclude private assets.

The public linked example ran from a copied directory, moved successfully, and recomputed both
upstream-derived differences. Changing one copied synthetic temperature changed the mean difference
from -2.200 K to +1.800 K in prose and the native table while preserving the earlier output. The
unchanged explanatory draft was deliberately not rewritten: updated numbers still require an author
to reconsider their interpretation. The initial installed DOCX was rendered in Word and its single
page inspected; table alignment, the negative sign, units and body indentation remained readable.

Twenty-four additional tests run against the isolated installed wheel passed, covering the scalar/
paired proposal entry, external figure sizing into DOCX, and scaled-unit display. The linked-example
move/recompute/Word check now also sits in the existing CI package-smoke step. Its first local run
exposed an assertion that omitted the intentional word-joiner after a negative sign; the assertion
was corrected, not the product formatting.

These are local integration results, not new scientific validation or a remote CI result. The
candidate still carries the existing 0.10.1 package version for local testing only; it must not be
distributed as the published 0.10.1 artifact. No merge, push, tag or release occurred. Next use the
existing release path for version/document synchronization and supported-platform CI; do not repeat
the four scientific first attempts or the successful unchanged-input local checks. Remaining product
friction and broader scientific-quality work above stay open rather than being concealed by release.

### v0.11.0 release preparation

The candidate version, CLI notices, citation metadata, installation guidance and release notes are
synchronized to 0.11.0. Version/document checks passed (23 tests) after the earlier full integration
run. The next verification is the existing Windows/Linux Python 3.10–3.12 CI plus installed-wheel
examples, not a repeat of private first drafts. A candidate branch or PR is not a published release;
only a successful main-branch build may supply final distribution artifacts.
