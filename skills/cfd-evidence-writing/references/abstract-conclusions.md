# Abstract and Conclusions from established results

Write these sections after reading the current Results and Discussion, the paper spine, and the
Introduction's stated question and contribution. Use current evidence, not an earlier outline's promises.
This guidance applies to host-authored prose; it does not generate or approve a complete paper.

## Fix the evidence boundary before drafting

- Identify the question actually answered, the comparisons used, and the strongest supported findings.
- Select a few decisive numerical or spatial anchors already present in the Results/Discussion.
  Do not force a number into every sentence or require a quota of findings.
- Preserve each quantity's case scope, units, denominator and meaning. A normalized indicator is not
  automatically an efficiency, conserved fraction, stability limit or optimum.
- Read the current source-bound values. A historical draft labeled final or locked can contain
  superseded values; do not restore it because its wording is more polished.
- Do not introduce new calculations, datasets, cases, mechanisms or literature claims here.
  If a genuinely necessary result is missing, establish it in the appropriate body section first.
- Distinguish the result observed in this study from an interpretation supported by that result.
  Retain uncertainty that materially changes the meaning; keep internal process notes out of the prose.

## Abstract: a self-contained scientific answer

State the problem and why the unresolved aspect matters with only the background needed to orient
the reader. Specify the approach and relevant study scope without reproducing the Methods section.
Present the principal findings in a useful order: the main response, the explanatory relation, and
the bounded implication when each is supported. The argument decides the sentence count.

Use concrete quantities and comparisons instead of "significant improvement" or "better performance"
without a defined basis. Do not imply statistical significance from a deterministic CFD difference.
Define a necessary abbreviation on first use and omit internal case codes unless essential to meaning.
The abstract must stand without figure/table pointers, unexplained notation or references to evidence notes.
Follow an explicit venue requirement for structured headings, length or citations rather than imposing
one abstract template on all journals. Do not add citations merely to make the abstract look complete.

Keep method fidelity and claim strength aligned: steady screening cannot establish a dynamic boundary;
a sampled location is not a continuously resolved extremum; model agreement is not new validation.
Mention a limitation only when omitting it would alter the reader's interpretation of the central result.
Finish with the scientific or engineering meaning established here, not a promised future study.

## Conclusions: synthesize, do not repeat the abstract

Answer the Introduction's research question directly. Organize the main findings by what they resolve,
not by figure order or a chronological account of the analysis workflow.
Connect complementary evidence to the explanation: which observation establishes the response,
which quantity explains a relationship, and where a competing interpretation remains viable.
Do not turn this into a mandatory sequence repeated for every finding.

Retain only numerical anchors needed to make the conclusions concrete and distinguish their scope.
Avoid copying paragraphs from Results, retelling every trend, or enumerating routine modeling steps
as contributions. A useful conclusion compresses the argument while preserving its physical meaning.
An observed association can motivate a design priority without proving an untested redesign will work.
Do not convert a locally stronger response into overall superiority, or a composite index into a
universal ranking. Keep jointly varied factors visible when their independent effects are unresolved.

If needed, state the consequential limitation and the smallest useful next question once, in proportion
to their importance. Do not end with an unbounded research wish list or defensive caveats that erase
the supported contribution. Prefer the author's or venue's requested paragraph/list format.

## Read the beginning and end together

Check Title, Introduction, Abstract and Conclusions against the current body of the manuscript:
the question, terminology, comparison scope, numerical direction and claimed contribution must agree.
If the evidence narrowed the study, revise the framing rather than inflating the conclusion to match
an old promise. If no body passage supports a summary claim, remove or defer that claim.
Use supported value tokens when available; separately read free-text quantities and qualitative
claims. Token binding and global numbering cannot detect every stale interpretation.

In manuscript tasks, `evidence_bindings` maps a local evidence ID to its owning section/evidence
in `manuscript-context.json`. Use that local ID in value tokens and paragraph evidence lists;
read the owner rather than entering a second numeric copy. `depends_on` identifies body sections
whose argument the summary consumes. Read `CHANGES.md` on continuation and reconsider the listed
passages, including whether an old image or a free-text direction still agrees with current data.
Do not describe source-driven numeric refresh as automatic revision of the scientific argument.

Preserve author edits and record unresolved scientific choices in existing evidence notes. Re-read
affected summary statements after a source, comparison or body argument changes; do not claim that
the software automatically propagates scientific meaning across all chapters.
Keep the current manuscript formatting rules: body indentation and spacing are paragraph properties,
while headings, captions and other non-body elements retain their separate styles.
