# CFD-Paper-Agent

CFD-Paper-Agent is an open-source, author-in-the-loop research-workflow project for building
traceable local state around existing CFD results. **v0.1.0 — Initial Public Preview** is a narrow,
installable CLI slice: it initializes a project, indexes project files, records resumable state,
and ranks structured topic candidates supplied by the author.

The preview is intended for demonstration, feedback, and incremental development. Scientific
judgment, evidence qualification, validation, and publication decisions remain with the author.

## Capability matrix

| Capability | State | v0.1.0 boundary |
|---|---|---|
| `cfdpaper init` and `status` | Available in v0.1.0 | Create and reopen local SQLite project state. |
| `cfdpaper inspect` | Available in v0.1.0 | Index files and track explicit staleness; indexing does not create verified evidence. |
| Author-supplied `cfdpaper plan` | Available in v0.1.0 | Rank schema-v1 candidate JSON against the current evidence state and write a report. |
| Local checkpoints and restart/resume | Available in v0.1.0 | Resume the demonstrated initialization, inspection, and planning slice. |
| Strict/fast reinspection policy and extension contracts | Experimental | Interfaces are present, but broader project behavior is still being validated. |
| Optional retrieval and adapter extension points | Experimental | Not general solver-native support and not part of the Quickstart. |
| Automatic generation of evidence-bounded topic candidates | Roadmap | Targeted for v0.2.0 with explicit author review. |
| `analyze`, `figure`, `write`, `review`, `revise`, and `export` | Roadmap | CLI placeholders exit non-zero and do not produce artifacts. |
| Fluent, STAR-CCM+, and other native solver adapters | Roadmap | Use small synthetic or neutral exported files for the public preview. |

## Install from a public checkout

CFD-Paper-Agent targets CPython 3.10–3.12 for this release. From the repository root:

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

That result is intentional. `inspect` builds a file index, but the v0.1.0 public CLI does not
promote indexed files to verified evidence records. `plan` still writes
`project/.cfdpaper/outputs/plan/topic-ranking.json`, stores a checkpoint, and refuses to call the
candidate defensible. See the [example walkthrough](examples/quickstart/README.md) for the exact
boundary.

## Planning and author control

Candidate input is a schema-version-1 JSON envelope; the complete synthetic input is available in
[`examples/quickstart/candidates.json`](examples/quickstart/candidates.json). Planning performs a
fast incremental inspection before ranking. It detects file metadata and deletion changes but does
not strictly rehash unchanged files unless strict hashing is selected by the stage or user.

`--approve-topic` must be paired with `--author`. Approval records the selected direction and its
evidence-dependent scope; it does not execute analysis or manuscript production. No roadmap
command reports success in v0.1.0.

## Public documentation

- [Architecture overview](docs/architecture/overview.md)
- [Roadmap](docs/ROADMAP.md)
- [v0.1.0 release notes](docs/releases/v0.1.0.md)
- [Limitations](LIMITATIONS.md)
- [Contributing and issue-reporting guidance](CONTRIBUTING.md)
- [Citation metadata](CITATION.cff)

## Data and scientific boundary

Do not commit confidential solver cases, unpublished manuscripts, company data, credentials, or
licensed files. File presence is not validation: comparability, convergence, conservation, units,
QoI definitions, source provenance, and claim scope still require scientific review.

## License

Apache-2.0 for the source code. The Quickstart data are synthetic and provided solely for software
demonstration.
