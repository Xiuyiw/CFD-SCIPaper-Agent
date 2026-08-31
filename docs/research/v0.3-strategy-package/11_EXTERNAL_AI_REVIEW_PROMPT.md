# External Review Prompt for the CFD-Paper-Agent V0.3 Strategy Package

## Your role

Act as an independent senior reviewer with expertise spanning CFD research practice, scientific software, research visualization, academic writing, agentic systems and developer-facing products. Review the supplied **CFD-Paper-Agent V0.3 Strategy Review Package** as a product-and-science design candidate.

Do not redesign the project from zero. Do not assume that more automation, more agents, more registries or more review layers are inherently better. Your task is to identify material defects, unsupported claims, missing mechanisms and high-value corrections in the proposed path from mature CFD results to defensible analysis, figures and academic text.

## Product context and non-negotiable boundaries

CFD-Paper-Agent is an author-in-the-loop, semi-automated system for projects that already possess mature CFD results. The current public v0.2.0 supports local project state, evidence-bounded topic candidates, ranking and explicit author approval; it does **not** yet deliver generic solver extraction, analysis, publication figures, manuscript production or revision.

Evaluate the candidate design against these boundaries:

1. Scientific qualification precedes plotting and writing: case comparability, units, convergence, conservation, QoI meaning, complete-sequence trends, verification/validation status and claim ceiling cannot be bypassed.
2. Missing information remains missing. The system may return `insufficient`, `restricted` or a minimum evidence gap instead of a complete-looking paper claim.
3. Locked evidence flows one way into figures and writing; presentation tools and language models cannot change values, case identity, trend classification or claim strength.
4. The generic core remains solver- and domain-independent. Solver and domain knowledge enters through read-only adapters, tested Skills and project context.
5. The default workflow contains three real author checkpoints, not synthetic approvals.
6. Raw results are read-only. External retrieval can locate evidence but cannot prove a scientific conclusion.
7. Product effort is targeted at 55% scientific understanding/analysis, 25% figures/writing, 10% adapters/usability and 10% necessary reliability/provenance/author authority.
8. Scope must remain proportional. A new framework, dependency, registry, approval layer or report is justified only if omitting it would make the current user outcome fail or become materially false.

If you challenge one of these boundaries, identify the concrete user task it prevents, the evidence for the problem and a smaller implementable alternative.

## Evidence discipline

Use the package's reading guide and source manifest. When you can access the internet, verify only the external facts that materially affect your finding, preferring the fixed repository location, official specification or official product documentation cited in the package. When you cannot verify a claim, label it `not independently verified`; do not convert uncertainty into an accusation or a fact.

Keep these categories separate:

- current v0.2.0 product fact;
- fixed-source external project fact;
- commercial official claim or observable workflow;
- controller inference;
- future proposal that still requires implementation and real-project validation.

Do not require a full repeat of the 33-candidate search or all 23 deep dives unless you identify a specific coverage failure that could change the product architecture. A preference for another library is not a finding unless it improves a named user outcome and you compare license, dependency, scientific boundary and validation cost.

## Required review dimensions

Review each dimension separately. Cross-reference findings where one defect affects several dimensions rather than duplicating it.

### 1. Factual accuracy

- Are v0.2.0 capabilities separated from experimental, roadmap and unimplemented items?
- Do open-source claims match the cited fixed code/test locations and licenses?
- Are commercial claims consistently limited to official public claims or observable workflows?
- Are direct-reuse and reimplementation recommendations supported by precise source locations?

### 2. CFD scientific boundaries

- Can the proposed design stop incomparable cases, unit conflicts, weak convergence, conservation gaps, invalid aggregation, incomplete sequences and unjustified verification/validation claims before figures or prose are produced?
- Are QoI definitions, operators, sampling, missing-data policy and claim ceiling sufficiently explicit without becoming domain-specific bureaucracy?
- Could any component silently turn discrete CFD screening into monotonic laws, continuous optima, stability boundaries or experimental validation?

### 3. Benchmark sufficiency and transfer quality

- Do the 16 open-source/academic deep dives and 7 commercial workflows cover all seven capability tracks with genuinely distinct mechanisms?
- Is any important class of mechanism absent enough to invalidate the design, rather than merely expand the catalog?
- Are conclusions transferred at the right level (`direct reuse`, `reimplement`, `idea-only`, `reject`)?

### 4. Built-in Skill system

- Are Skills discoverable, progressively disclosed, relative-path portable and testable across hosts?
- Does each proposed Skill have a real repeated scientific task, input/output contract, evidence prerequisites, stop condition, fallback and positive/negative/adversarial evaluation?
- Are scientific, figure and writing permissions separated so that a Skill cannot fabricate approval or upgrade evidence?
- Should any proposed Skill be merged, deferred, reduced to a reference/template/script or removed?

### 5. Product architecture

- Are the evidence, scientific-analysis, figure/writing, Skill, adapter and user-orchestration layers separated by enforceable data flow rather than prose alone?
- Is the architecture lighter than a generic workflow/RAG platform while still supporting interruption, stale-input invalidation and reproducibility?
- Does it preserve a genuinely broad CFD core instead of encoding a combustion-specific ontology?

### 6. Implementation feasibility

- Can the v0.3 slice be implemented and tested with the stated Python/CLI stack and without the deferred heavy dependencies?
- Are candidate QoI contracts, qualification states, FigureContract, source data, SVG/PNG QA and one evidence-linked results paragraph a coherent vertical slice?
- Identify hidden dependencies, ambiguous interfaces or validation fixtures that would block implementation.

### 7. Ordinary-user experience

- Can a researcher with mature exported CFD results but no knowledge of internal evidence registries complete the workflow?
- Are required inputs discoverable from the data and scientific question where possible, with actionable minimum correction requests where automation cannot decide?
- Do the three author checkpoints expose meaningful scientific decisions without forcing users to understand internal governance concepts?

### 8. Version slicing and release claims

- Is v0.3 small enough to deliver but valuable enough to exceed v0.2.0 in a visible end-to-end way?
- Are VTK, literature evidence, full manuscript workspaces, DOCX/LaTeX, revision and native solver adapters deferred consistently?
- Do later version horizons avoid becoming hidden v0.3 acceptance criteria or unsupported claims of broad universality?

### 9. Unified rules and governance

- Do the principles protect scientific truth and author authority without allowing internal audit language or security theatre to dominate the product?
- Are any rules duplicated, unenforceable, contradictory or likely to create the same false-completion problem they aim to prevent?
- Which rules must remain normative, which belong in a Skill or test, and which should be removed?

## Severity and adoption scales

Use these severities:

- `critical`: could cause false scientific claims, corrupt locked evidence, fabricate author approval, expose private material, or make the proposed product fundamentally unusable.
- `important`: materially weakens scientific defensibility, architecture, implementation feasibility or ordinary-user success; should be resolved before v0.3 implementation begins.
- `minor`: localized ambiguity or inconsistency worth correcting but not blocking the architecture.
- `preference`: stylistic or alternative-design preference with no demonstrated material effect. Report sparingly.

Use these adoption levels:

- `must adopt`: needed before author approval or v0.3 implementation.
- `recommended`: clear net benefit supported by evidence, but not a blocker.
- `optional`: context-dependent improvement that should not expand v0.3 by default.
- `reject`: conflicts with evidence, product boundaries, implementation economy or scientific priorities.

## Required response format

Return one self-contained Markdown report with the following sections.

Before section A, add a short metadata block containing:

- `Model/provider`: use the actual model and provider when known; otherwise write `unknown`.
- `Review date`: use `YYYY-MM-DD`.
- `Web access`: `yes` or `no`; if `yes`, state whether any package claim was independently checked online.

These fields describe this review run only. Do not create a registry, approval record or additional review layer.

### A. Executive verdict

State one of:

- `APPROVE FOR AUTHOR RECONCILIATION`
- `APPROVE WITH TARGETED REVISIONS`
- `MAJOR REVISION BEFORE AUTHOR RECONCILIATION`
- `NOT DEFENSIBLE IN CURRENT FORM`

In no more than 250 words, identify the strongest aspect, the main remaining risk and whether v0.3 implementation should remain paused.

### B. Review coverage

List the package files/sections actually examined, any source facts independently checked and any areas you could not verify. Do not claim full verification if you sampled reports.

### C. Findings

Provide a table or repeated structured blocks. Every finding must contain all fields:

| Field | Required content |
|---|---|
| Finding ID | Stable identifier such as `FACT-01`, `SCI-02`, `SKILL-03`, `ARCH-01`, `UX-01`, `ROAD-01` or `RULE-01`. |
| Severity | `critical`, `important`, `minor` or `preference`. |
| Review dimension | One of the nine required dimensions. |
| Exact location | File and section/table/item; include quoted wording only when needed. |
| Evidence and rationale | Package evidence, independently checked source and the concrete failure mode. Separate fact from inference. |
| Recommended revision | Smallest specific correction that resolves the problem. Do not say only “add more detail”. |
| New evidence required? | `no`, or name the exact missing evidence and why it changes the decision. |
| Conflict with current constraints | `none`, or identify the precise frozen boundary affected and whether the conflict is justified. |
| Adoption level | `must adopt`, `recommended`, `optional` or `reject`. |

Do not split one root cause into many repetitive findings. Do not manufacture findings to fill every dimension; use `no material finding` in Section D when appropriate.

### D. Dimension-level conclusions

For each of the nine dimensions, state:

1. `adequate`, `adequate with revision`, or `inadequate`;
2. the highest-severity linked finding, or `no material finding`;
3. one sentence explaining the judgment.

### E. Proposed adoption summary

Group your recommendations into `must adopt`, `recommended`, `optional` and `reject`. Explicitly flag any recommendation that should be deferred beyond v0.3 rather than added to the current slice.

### F. Minimum author decisions

List only decisions that genuinely require the author rather than an implementation detail the development team can resolve. If none exist, write `none`.

### G. Final check on implementation start

Answer directly:

1. Is the proposed v0.3 vertical slice scientifically defensible?
2. Is it small and coherent enough to implement next?
3. Which `must adopt` findings, if any, must be closed first?

Do not write implementation code, simulate user approval, draft a replacement strategy package or begin a second review cycle.
