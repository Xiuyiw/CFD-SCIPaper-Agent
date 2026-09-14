# v0.10: Scientific analysis that improves manuscript reasoning

2026-09-14. The author approved the post-v0.9 direction: improve scientific understanding,
writing depth, figures and actual document presentation before adding more workflow machinery.
This document defines the next bounded increment, not a claim of completed implementation.
The public baseline is v0.9.0. Version metadata remains unchanged during development.

## 1. Intended user outcome

Starting with existing exported CFD records, definitions and figures, a capable host should:

1. distinguish record statistics from spatially weighted quantities;
2. select complementary diagnostics that answer the author's physical question;
3. compute the declared quantities reproducibly;
4. explain agreement or tension between the field, mean, spread and extrema;
5. deliver a readable subsection and its manuscript-level consequences in Word.

The improvement must appear in the supplied analysis and prose, not just in more instructions,
reports or identifiers. Author/host scientific judgment is intentional; preparation burden and
unreliable outputs are the problems to reduce. Preserve the 55/25/10/10 priority allocation.

## 2. First implementation slice: explicit spatial weighting

At the v0.9 baseline, code inspection confirmed that `calculate_table` supported population,
partition, scalar_select and paired_change. Population treats records equally. Partition handles
supplied area/rate identities, not general area- or volume-weighted field variability. The v0.9
proposal entry accepts population/partition only. The execution state below records the new work.

Add one `weighted_population` operation for explicitly declared value and positive area/volume
weight columns. Preserve grouping, source records, definitions and missing-value behavior.

- Weighted mean: sum(w*x)/sum(w).
- Weighted population SD: sqrt(sum(w*(x-mean)^2)/sum(w)); use stable summation.
- Outputs: weighted_mean, weighted_std and weight_sum, with their source records and units.
- No automatic CV, flux integral, normal-vector projection, quantiles or uncertainty estimate.
- Weights must be finite and strictly positive. A missing selected value makes the affected
  result unavailable; do not silently discard rows. Invalid definitions/weights require correction.
- Weight units must describe the declared area or volume measure. Do not silently mix units.
- Absolute temperature means retain their scale; their SD is a temperature difference in K.
  Celsius/Kelvin translation must leave SD unchanged. Reuse existing temperature semantics where
  appropriate without changing the established paired-change behavior.
- The result represents supplied element values with supplied measure weights. Statistics of
  cell/face averages are not a claim to reconstruct unresolved within-element fluctuations.
- Whole-domain coverage, overlap and the physical meaning of the field are host/author judgments.
  Signed mass flux and point-count weighting are outside this initial operation.

Reuse `publication/table_evidence.py`, `publication/section.py` result_ref and calculation models,
and `analysis_suggestions.py` proposal-to-writing path. Preserve the distinct scientific comparison
object in proposals; do not reintroduce the v0.9 inheritance/name collision. `materials.py` need
not infer weighting automatically from column names. No new command or project database.

## 3. Four delivery batches

| Batch | Work | Observable completion |
|---|---|---|
| A: calculated evidence | Implement the operation and existing analysis/section bindings; test the source-change and relocation paths | Unequal spatial weights produce correct means/SD, and the same values appear in prose and native tables |
| B: diagnostic-to-writing skill | Improve only the guidance gaps demonstrated by a fresh host attempt using the shipped package; select mean/spread/extrema/field evidence according to the question | A paragraph explains an actual relationship beyond its caption; a scalar ranking is not inflated into an overall performance or causal ranking |
| C: coordinated figure and Word output | Use existing figure-task integration for complementary maps/profiles/data comparisons; use the current DOCX renderer | Source data and editable figures accompany the text; actual manuscript-width pages are readable and visually coherent |
| D: transfer and release assessment | Run a relocated installed-package example and one focused content review; fix actionable failures, then assess the version scope | Separate software results, host-written improvements and remaining research evidence; release only after the current CI and example checks |

B and C advance together after A exposes a stable interface. Do not postpone manuscript progress
to polish a single figure indefinitely. A tiny comparison may belong in a table or prose;
no mandatory panel count, fixed paragraph template or invented diagram detail.

## 4. Scientific and writing examples

Public examples use clearly labeled analytical/synthetic records with known answers. Include
area-weighted and volume-weighted cases to avoid coding heat-sink-specific assumptions.
At least one example should show that mean, spread and extremum need not give the same ranking.
This is a teaching/testing example, not empirical proof of a mechanism or cross-domain validation.

Private asset use remains targeted and read-only:

| Asset | Purpose |
|---|---|
| P04 multi-evidence writing and Fig.9/10/12/13/14 development | Reuse field-versus-metric reading, source-versus-transport reasoning, normalization and complementary evidence; do not reuse only Fig.5 |
| P04 Introduction/Methods/Conclusions and literature roles | Judge question-to-design-to-result alignment and whether a local result is summarized at the right scope |
| Cooling full external review and existing native-field replay | Test whether weighted definitions are carried into interpretation and whether missing-but-available inputs are distinguished from missing research evidence |
| SG_Baffle failure lessons | Keep unequal definitions, incomparable cases and false monotonic claims from being treated as persuasive findings |

Reuse existing private source maps rather than recataloging projects. Resolve the particular
source/definition needed before a replay; conflicting wall-temperature definitions remain
unresolved unless actual evidence settles them. Do not change solver results or submitted P04 files.
Known-case replay is not an unfamiliar-project blind test. A generated draft must be preserved
before feedback; generation receives evidence and current skills, not the evaluator's final prose.

## 5. Minimum effective verification

Calculation tests:

1. Values [1,3] with weights [1,3] give mean 2.5 and SD sqrt(0.75).
2. Equal weights match population mean/SD; a single element has zero SD.
3. Multiplying every weight by a positive constant leaves mean/SD unchanged.
4. Splitting an element into same-value elements with conserved total measure leaves results unchanged.
5. Missing/nonfinite inputs and invalid weights do not produce silently filtered statistics.
6. Groups, units, membership and result_ref supporting rows remain correct.
7. Celsius/Kelvin shifts preserve SD, and reported mean/SD units are distinct where required.
8. A moved analysis package recomputes after source updates and propagates bound values to the
   subsection, table and consuming manuscript section without silently rewriting interpretation.

Content evaluation asks whether the host chose useful diagnostics, explained their relation,
used literature in its actual role, and limited only unsupported inferences. Record concrete
passages and corrections; do not use self-assigned scores or test counts as writing-quality proof.

Presentation evaluation uses actual DOCX/PDF pages: two-character first-line paragraph indentation,
zero before/after paragraph spacing unless explicitly overridden; independent heading/caption/table
styles; consistent final-size labels, markers, legends, colorbars and units; sensible figure/table
placement and whitespace. Inspect scientific values and actual previews, not only file existence.

Do not repeat unchanged old tests at every step. Run focused tests while implementing, integration
tests once the chain changes, and the established full supported-platform checks before release.

## 6. Work ownership and continuation

- Controller owns the shared section/result bindings, integration entry points, public example,
  overall plan, versioning and release. Maintain one active feature branch.
- Analysis implementer owns the weighted calculation and focused numerical tests once interfaces
  are agreed in the existing models; no independent schema or general field engine.
- Writing/presentation collaborator owns assigned skill guidance and focused example evaluation;
  it does not edit the same example/renderer file concurrently with the controller.
- Use short isolated subtasks with exact file ownership when useful. Keep outcomes here rather
  than creating a new approval/registry system. The author need not approve every coding step.

New scientific choices, unavailable source material or a necessary new simulation require a
specific author question. Continue independent work while those points await an answer.

## 7. Deferred work, not forgotten

Native Fluent/STAR intake, general temporal/3D analysis, automatic literature search, broader
journal styling, Word-only edit reconciliation, event-driven journal revision and final submission
bundles remain on the public roadmap. They are not all prerequisites for this bounded increment.
The three heterogeneous real-project validations remain necessary before claiming broad maturity.
Do not rename v0.10 as a complete v1.0 merely because this increment passes its tests.

## Current execution state

Batch A implemented on `workstream/v010-scientific-writing` (2026-09-14). The numerical
implementation and its tests were delegated with exclusive file ownership; the controller
implemented proposal/section integration, source-change propagation, Word-table tests and usage
documentation. Version metadata remains 0.9.0; this is unreleased v0.10 development.

- `weighted_population` now exposes the three specified results through existing calculations,
  analysis proposals and result_ref. Temperature semantics survive package serialization.
- Existing equal-record proposals cannot silently discard supplied spatial weighting or
  temperature semantics and proceed as a different calculation.
- Source relocation, changed-source reassembly and downstream manuscript bindings are tested;
  interpretation-only text remains unchanged. Native Word tables receive the bound values,
  Celsius means/K standard deviations and squared/cubed measure labels.
- Numerical tests cover known answers, equal weights, splitting/scaling, missing/invalid input,
  unit/domain declarations, Celsius/K shifts and stable large-offset computations.
- Publication, analysis-suggestion and built-in-skill regression run: 586 passed, 2 optional
  Pandoc skips. A subsequent proposal-validation fix passed its complete affected test files
  (42 tests, including two new regression cases). Ruff check, changed-file format check and
  diff check passed. These are local Python 3.14 results, not supported-platform release CI.

No private source cases, manuscripts or figures changed. Existing P04 asset mapping and cooling
review dispositions informed the scope; this batch did not conduct a new private writing replay.
Batch B/C and local transfer work are recorded below. Do not treat calculation
or temporary DOCX test success as writing quality, scientific validation or visual acceptance.
This direction is author-authorized; do not reopen v0.9 or demand repeated plan approvals.

### B/C: diagnostic selection, reusable guidance and actual pages

Completed locally on 2026-09-14, following Batch A commit `321da21`. The controller retained
the fresh host proposal/draft before providing the field image and revised guidance; a separate
collaborator rendered the figure. Original P04/cooling materials were not edited or recomputed.

Targeted reuse included the existing P04 multi-evidence subsection and asset map, and the cooling
external-review dispositions. They informed field-versus-summary reasoning, source-versus-
transport distinctions and avoiding unsupported overall performance rankings. This did not
repeat the Fig.5 experiment or claim to reread the complete private archive.

The first host independently selected area-weighted mean and SD with spatial evidence and kept
the independent volume example separate. It correctly explained the lower mean/hot terminal
region relationship, but repeated method definitions and irrelevant limitations. The guided
continuation actually viewed the field image and explained why broad cooling lowers the mean
while a narrow hot region increases spread. This is a local descriptive explanation of prescribed
fields, not a discovered heat-transfer mechanism. The original and guided attempts are retained
separately under the ignored `private-fixtures/v010-host-trial/`.

Reusable changes prompted by that attempt:

- The shipped QoI skill now documents the weighted operation and area/volume/temperature roles.
- The writing reference connects spatial extent with summary moments, concentrates definitions
  in one appropriate location and avoids repeating irrelevant cautions in manuscript paragraphs.
- Section/manuscript Markdown tables now display their numbers once, matching prose/Word.
  Legacy standalone exports retain their existing unnumbered caption behavior.
- Section preparation no longer automatically says custom artwork is pending when an actual
  supplied figure exists. Free-text historical proposal notes are not silently rewritten; the
  public example updates its obsolete presentation notes explicitly and retains the original
  host attempt separately.

`examples/spatial-diagnostics/` now provides analytical source tables, a runnable figure script,
a recorded host proposal/guided draft and a public-API replay. The example distinguishes a new
host attempt from recorded replay and includes a `--prepare-only` path without model answers.
The wall map preserves physical facet widths with one color scale; the small native table carries
the four numerical bindings. SVG/PDF/PNG/TIFF, source CSV and the editable local script travel
with the package. No automatic extrema, thresholds or new field-integration framework was added.

Verification and observed output:

- 591 publication/analysis/skill tests passed; 2 optional Pandoc tests skipped. An additional
  assertion for single manuscript caption numbering passed its affected test after that run.
- Fresh preparation does not include recorded answers. Relocation/reassembly, both sets of
  weighted answers, byte-identical relocated plot pixels, live SVG text, 160 mm Word image width,
  native table and two-character/zero-spacing body paragraphs are covered by focused tests.
- Ruff, changed-file formatting and the two modified skills' validation passed.
- The actual example DOCX was generated with the bundled Python and the existing public export
  function. The canonical document renderer used installed LibreOffice on Windows and produced
  one PDF/PNG page. The controller inspected the complete page: text, units, shared colorbar,
  figure caption and table were readable, with no observed clipping or overlap. This is one
  manuscript-width page inspection, not a journal-wide formatting guarantee.

### D: local transfer and release work remaining

A wheel was built in a temporary directory, installed non-editably to a separate target, and
imported under Python isolated mode with its actual module path checked. The copied public
example ran outside the repository, including calculations, figure task import, section assembly,
Word export and the updated packaged QoI skill. The build used normal isolated build dependencies
because the development environment did not contain Hatchling. Version metadata deliberately
remains 0.9.0 until release preparation; this development wheel is not a public 0.9.0 replacement.
A separate read-only scientific check found the four numerical bindings, area definitions,
terminal-facet interpretation and independent volume treatment consistent with the example's
source tables. Its conclusion applies to this example only, not broad host writing maturity.

Remaining before v0.10 publication: final version/documentation/example packaging, full current
regression and Windows/Linux Python 3.10–3.12 CI, then authorized integration/release. Local tests
used Python 3.14 and do not replace that CI. Do not restart A–C or repeatedly polish the recorded
subsection. Broader real-project scientific validation and deferred capabilities remain as in
Section 7; this example does not close them.

Author feedback after B/C found a missed visual defect: numeric headers were left-aligned while
their values were right-aligned. The shared Word table renderer now applies column alignment to
headers and values alike. A regression reproduced the defect before the fix; 27 affected tests
then passed. The corrected one-page Word/PDF was rendered through Word and inspected. It is under
`private-fixtures/v010-host-trial/public-replay/table-alignment-fix/`; the previous PDF is retained
but superseded. No source values, column widths, manuscript text or figure assets changed.
