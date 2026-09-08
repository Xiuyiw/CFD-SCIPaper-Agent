# Single-figure scientific writing: minimal development specification

2026-09-08. The author has now authorized continuous implementation through v0.4.0 release. The completed host experiment informs, but does not itself prove, product behavior.

## Execution sequence for v0.4.0

1. Implement a section workspace: one or several supplied figures, evidence items with source locators, paragraph duties, optional verified literature, and an editable host-response format. Prepare a portable writing/review package; accept a host-authored draft with explicit evidence/figure links. Preserve numeric values through evidence tokens, not freehand recalculation. Keep manuscript prose, captions and evidence notes separate.
2. Add CLI routing under `write --artifact results-section`, preserving existing results-paragraph behavior. Multiple section IDs and explicitly chosen new output directories allow analyses and author-edited drafts to coexist without overwriting.
3. Export Markdown and DOCX subsection previews with actual figures/captions, via the existing optional docs dependency. Add a self-contained review package and record imported review comments as suggestions, never as approvals or silent text edits.
4. Extend the existing writing Skill and provide a public, clearly synthetic non-combustion example. Run the different P04 multi-evidence example privately to inspect scientific depth and preserve the original assets.
5. Run focused and full tests, lint, package installation and CLI examples; review the actual DOCX rendering. Update documentation, capabilities and version, push the release candidate for Windows/Linux CI, then publish v0.4.0 only on successful verification.

No new full-manuscript framework, source solver, database migration or permanent review service is required. Public contracts.py/schemas remain unchanged unless an actual integration need is identified. The explicit author authorization supersedes earlier experiment-only stopping points below; historical results remain partial, not retrospectively upgraded.

## Implementation result

The four section operations and CLI entry are implemented. The public two-figure
analytical example runs through package, assembly, and DOCX. A separate private
P04 Fig.12/13 host replay produced a four-paragraph draft and embedded both images;
Word-rendered output was inspected page by page. The replay distinguishes stronger
reaction from weaker normalized feedback, but remains too numeric and repeats
limitations. It demonstrates integration and a useful draft, not autonomous
publication quality or a general scientific benchmark. No P04 original was modified.

Local verification: 1094 tests passed, two skipped; focused specification and code
review completed. Isolated wheel installation and the subsection example passed.
Candidate CI run 34183702482 passed all six Windows/Linux Python 3.10–3.12 tests
and the release-package job, including installed-wheel subsection DOCX generation.

## Original single-figure experiment outcome sought

Given an existing scientific figure, corresponding metrics and comparison definitions, produce an editable Results and Discussion subsection and a self-contained caption. Improve scientific explanation, not just text length or the number of cited values. A figure may contain several fields; this is not yet multi-figure section assembly.

## Input and output

- Reuse existing project evidence where available. Accept an image, case/panel mapping, display units, the comparison question and relevant quantitative diagnostics with sampling definitions. Missing nonessential information does not stop supported writing.
- The host must distinguish viewing an image from reading attributed observations. Neither permits estimating precise data from colors.
- Return an argument outline, manuscript prose, caption and short evidence notes. Evidence notes are separate from prose and are not a new database or approval object.
- Preserve the author's figure and text. This experiment writes a new candidate, not a replacement manuscript.

## Three targeted behaviors

1. Compare corresponding physical regions between cases before making within-case contrasts. Link the visible redistribution to selected diagnostics, maintaining the distinction between sampled and continuous quantities.
2. Explain relevant transport, source or geometric relationships with proportionate attribution. Keep material interpretive limits at the point where needed; do not repeatedly interrupt the narrative with inventories of unperformed checks.
3. Make the caption identify the comparison, panels, quantities, units and essential display semantics. Leave mechanism discussion and redundant caveats in their appropriate sections.

These changes address observed baseline weaknesses. The baseline was scientifically competent, so a revised draft must preserve its factual accuracy and useful physical reasoning; it need not outperform every stylistic choice.

## Experiment and acceptance

- One baseline already exists. It used the general scientific-writing skill, not the product's CLI writing skill.
- Run once in a fresh writer context with the same research input and inherited host model configuration, adding only generic single-figure guidance. Keep the general scientific-writing skill in both conditions. Preserve first outputs; do not leak the baseline or evaluation reference.
- Evaluate actual passages for cross-case explanation, limitation placement and caption economy, alongside values, case IDs, units and inference. Record regressions rather than treating a shorter draft as automatically better.
- Retain the guidance if it gives a useful local improvement without introducing a substantive scientific error. Mixed outcomes should be reported as mixed, with a bounded next action; do not enter an indefinite rewriting loop.
- One pair does not establish causal improvement or generality. Literature integration and autonomous intake are outside this test because the input is curated and no verified literature content is supplied.

## Product integration after the experiment

Use the result to extend the existing writing skill with an explicit image-assisted mode, without pretending that mode runs through the current template renderer. Preserve the current numerical renderer and its tests. Decide the smallest input/output integration against actual code before adding any public command or schema.

Concrete integration points: `skills/cfd-evidence-writing/SKILL.md` for routing and a short on-demand reference for figure interpretation. Keep `src/cfdpaper/publication/results_paragraph.py`, the existing `write_project` CLI behavior and `tests/publication/test_results_paragraph.py` unchanged in the first host-assisted increment. Update `tests/test_v03_skills.py` only when the distributed skill is actually changed. The present private guidance is an experiment, not an installed fifth product skill.

Next test in the approved roadmap: a different multi-evidence P04 question concerning field observations and quantitative interpretation. No new solver, registry, hashing layer or review service belongs to this slice.

## First guidance experiment result

The one-pair host experiment is complete: cross-field organization and caption economy improved, while repeated reader-facing limitations persisted. Preserve separate manuscript and evidence-note outputs as a concrete integration responsibility, not merely a general prompt preference. No product deployment is authorized by the experiment's result alone.

An evidence-note error also identified a necessary semantic distinction: converting a cell-integrated source to a volumetric source requires cell volume; summing cell-integrated values over a defined region requires complete values and region membership, not that conversion. The image alone cannot provide either complete calculation. Avoid generic “missing volume prevents all source analysis” rules.

Do not schedule further rewrites of the same case in this step. Carry the effective organization guidance forward and resolve the remaining output-separation and quantity-definition issues in the next bounded integration design. Private original outputs and comparison are retained separately from this public specification.
