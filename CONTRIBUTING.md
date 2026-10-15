# Contributing

## Product and development principles

CFD-Paper-Agent is a specialist tool suite used by a host AI and a research author. It works from
existing CFD results toward scientific analysis, figures and manuscripts, technical reports or
conference papers. It is not a replacement foundation model, a new solver, or an autonomous
publication authority. The current development sequence and acceptance criteria live in the
[Research Workbench plan](docs/research/CFD_RESEARCH_WORKBENCH_UPGRADE.md).

- Prioritize scientific analysis (55%), figures and writing (25%), interoperability and usability
  (10%), and necessary reliability (10%). These are effort priorities, not code-line quotas.
- Improve a complete user task, not an isolated field or prompt. Analysis, scientific figures and
  writing must advance together. A successful export or green test suite is not scientific validation.
- Apply **STOP THAT SHIT**: implement requested work and its necessary consequences, then stop.
  Avoid speculative infrastructure, duplicate registries, approval ceremonies and repeated reviews.
  This does not excuse missing physics, unreadable figures or broken manuscript formatting.
- Let the host inspect available materials before asking the author for information. Normally the
  author decides the research question, the evidence/figure approach, and the final deliverable.
  Do not require repeated permission for routine steps already within the approved task.
- Preserve missing information and distinguish observations, interpretations, controls and external
  validation. Exact numbers still need compatible case, spatial domain, operator/weight, time support
  and reference state. Algebraic restatements are not independent evidence.
- Raw solver files and frozen scientific materials are read-only. Derived outputs use isolated
  directories. New solving, parameter fitting or expanding the case set needs separate authorization.
- Preserve author edits from the first implementation. A figure's author-edited local script takes
  precedence over a generated template. Do not silently overwrite manuscripts, comments or styles.
- Keep the core solver- and subject-neutral; domain knowledge belongs in documented recipes,
  adapters and task context. Reuse the existing SQLite/FTS, IDs, calculations and document bindings.
- Source changes drive deterministic recalculation/redrawing and targeted writing context. Scientific
  interpretation remains the host/author's responsibility; do not certify causality by a status flag.
- Figures need real source data, runnable local scripts, editable SVG/PDF and readable previews.
  Match the visual grammar to the evidence; two scalar values do not automatically justify a full figure.
- Default manuscript body paragraphs use a two-character first-line indent and zero spacing before
  and after. Headings, captions and tables have distinct styles; an explicit journal template wins.
  Check actual Word/PDF pages, not only document XML or file existence.
- Load the five bundled skills and their references as needed. Rule changes, code support and
  real-task effectiveness are separate results. Manually repairing a sample is not a product upgrade.
- Pre-submission review is bounded; revision is triggered by a real decision letter or reviewer
  comments. Submission clicks and appeals remain author-led.
- Maintain one current plan and a concise recovery entry. Retain historical assets and decisions,
  but do not inherit old pending tasks, approvals or superseded physical definitions as current facts.
- The controller owns shared definitions, IDs, dependency coordination and release configuration.
  Delegate bounded modules; do not let parallel teams build competing update chains.
- Evaluate first outputs separately from feedback-assisted revisions. Use known projects for
  regression, and label held-out or unfamiliar tests honestly. Report software and scientific effects
  separately. Reuse unchanged valid checks rather than repeatedly regenerating proofs.
- Publish complete, tested capability increments. A version number, test count or document count
  does not establish generality. Adjust later implementation priorities using actual user-task results.

Historical P04, cooling, battery and Gate 5 materials retain distinct roles: positive scientific
writing/figure examples, definition and comparison failures, and private regressions. They must not
be copied into public fixtures without permission and suitable rights. Use the accepted P04 distinction
between cell-integrated Heat of Reaction and separately calculated volumetric HRR, not its superseded
representative-cell-volume conversion. Preserve full external reviews, not just extracted JSON findings.

## Development setup

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

The public CI targets CPython 3.10-3.12 on Windows and Linux. Other interpreters and platforms are
welcome, but they are not release-supported without repeatable CI evidence. Contributions should
be solver-agnostic unless they live in an adapter package.

## Scientific contribution requirements

- Add a failing test before implementation.
- Preserve missing data as missing.
- Attach units and exact source locators to extracted values.
- Do not introduce project-specific scientific claims into the core.
- New adapters must pass the read-only adapter contract.
- New figure or writing behavior must be tested with generic fixtures.

Private solver files, unpublished manuscripts, company data, and copyrighted PDFs must not be
committed.

Use synthetic or redistributable fixtures in tests and issue reports. Do not upload native solver
projects, proprietary meshes, unpublished numerical results, API credentials, private absolute
paths, or personal identifiers. A neutral exported format is preferred when a solver-specific
defect must be reproduced.

## Licensing contributions

The repository is distributed under the Apache License 2.0. Unless explicitly stated otherwise,
an intentional contribution submitted for inclusion in this project is provided under the same
license, as described by Section 5 of the license. Contributors must have the right to submit all
code, documentation, tests, and data they provide. Do not copy material whose license is unknown or
incompatible; identify any required third-party attribution in the pull request.
