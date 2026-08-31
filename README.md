# CFD-Paper-Agent

CFD-Paper-Agent is an open-source, author-in-the-loop research workflow for turning mature CFD
evidence into defensible research directions. **v0.2.0** adds evidence-bounded topic generation
to the installable CLI: it can initialize and inspect a project, maintain resumable scientific
state, rank author candidates, or generate two to four provisional candidates from mature
structured records.

Scientific judgment, evidence qualification, validation, and publication decisions remain with
the author. Candidate generation stops at explicit evidence gaps and never grants approval.

## Capability matrix

| Capability | State | v0.2.0 boundary |
|---|---|---|
| `cfdpaper init`, `inspect`, and `status` | Available in v0.2.0 | Create local SQLite state, index files, track staleness, and resume work. |
| Author-supplied `cfdpaper plan` | Available in v0.2.0 | Rank schema-v1 candidate JSON; explicit author input takes precedence. |
| Evidence-bounded topic generation | Available in v0.2.0 | Generate two to four provisional candidates only from mature structured records. |
| Offline generation, reuse, and regeneration | Available in v0.2.0 | Deterministic offline mode, recoverable artifacts, and explicit `--regenerate`. |
| Strict/fast reinspection policy and extension contracts | Experimental | Interfaces are present, but broader project behavior is still being validated. |
| Optional provider and adapter extension points | Experimental | No provider transport or general solver-native support is claimed. |
| `analyze`, `figure`, `write`, `review`, `revise`, and `export` | Roadmap | CLI placeholders exit non-zero and do not produce artifacts. |
| Fluent, STAR-CCM+, and other native solver adapters | Roadmap | Use small synthetic or neutral exported files for the current release. |

## Install from a public checkout

CFD-Paper-Agent targets CPython 3.10–3.12. From the repository root:

```text
python -m pip install -e .
cfdpaper --help
```

## Reproducible Quickstart

Copy `examples/quickstart` to a writable temporary directory, change into the copied directory,
and run:

```text
cfdpaper init project --project-id synthetic-duct-study
cfdpaper inspect project
cfdpaper plan project --candidates candidates.json
cfdpaper status project
```

The example uses invented, non-sensitive duct-flow values. Expected planning output includes:

```text
Plan complete: outcome=missing-evidence; leading=pressure-loss-screening; gaps=4; approval=none
```

That result is intentional. `inspect` builds a file index, but the public CLI does not promote
indexed files to verified evidence records. `plan` still writes
`project/.cfdpaper/outputs/plan/topic-ranking.json`, stores a checkpoint, and refuses to call the
candidate defensible. See the [example walkthrough](examples/quickstart/README.md).

## Generated topic planning

When mature structured case, boundary, convergence, conservation, QoI-definition, and QoI records
already exist, omit `--candidates` to use generated planning:

```text
cfdpaper plan PROJECT_ROOT
cfdpaper plan PROJECT_ROOT --candidates AUTHOR_CANDIDATES.json
cfdpaper plan PROJECT_ROOT --provider offline
cfdpaper plan PROJECT_ROOT --provider auto
cfdpaper plan PROJECT_ROOT --regenerate
```

A complete synthetic walkthrough that creates mature structured records and exercises automatic
generation is available in [`examples/generated-topic`](examples/generated-topic/README.md).

`offline` is deterministic and requires no API key. `auto` falls back to the same offline candidate
skeletons when no provider is available; provider transport integrations are not included in this
release. Author files take precedence over generated candidates. A changed scientific snapshot
invalidates reuse, while non-scientific generation changes require `--regenerate`.

Generated artifacts under `.cfdpaper/outputs/plan/` retain candidate-to-evidence provenance and
the minimum missing-data list. They are recoverable project artifacts, not a stable public
interchange schema. Ordinary indexed files are not automatically promoted to mature scientific
records; this release therefore does not claim raw-result-to-topic automation.

`--approve-topic` must be paired with `--author`. Approval records the selected direction and its
evidence-dependent scope; real author approval is still required and does not execute analysis or manuscript production. No roadmap
command reports success in v0.2.0.

## Public documentation

- [Documentation index](docs/README.md)
- [Architecture overview](docs/architecture/overview.md)
- [Roadmap](docs/ROADMAP.md)
- [v0.2.0 release notes](docs/releases/v0.2.0.md)
- [v0.1.0 release notes](docs/releases/v0.1.0.md)
- [Limitations](docs/limitations.md)
- [Contributing and issue-reporting guidance](CONTRIBUTING.md)
- [Citation metadata](CITATION.cff)

## Data and scientific boundary

Do not commit confidential solver cases, unpublished manuscripts, company data, credentials, or
licensed files. File presence is not validation: comparability, convergence, conservation, units,
QoI definitions, source provenance, and claim scope still require scientific review.

## License

Apache-2.0 for the source code. The Quickstart data are synthetic and provided solely for software
demonstration.
