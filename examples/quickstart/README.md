# Synthetic Quickstart

This example contains invented duct-flow screening data. It does not represent an industrial
case, a solver-native export, or validation evidence.

Copy this directory to a writable scratch location, change into the copied directory, and run:

```text
cfdpaper init project --project-id synthetic-duct-study
cfdpaper inspect project
cfdpaper plan project --candidates candidates.json
cfdpaper status project
```

The commands create local state under `project/.cfdpaper/`. The planning report is written to
`project/.cfdpaper/outputs/plan/topic-ranking.json` and the final status includes a `plan`
checkpoint.

Expected planning boundary:

```text
Plan complete: outcome=missing-evidence; leading=pressure-loss-screening; gaps=4; approval=none
```

`inspect` indexes the files, but v0.1.0 does not expose a CLI command that promotes indexed files
to verified scientific evidence. The example candidates reference intentionally unregistered
`demo-` evidence IDs, so `plan` reports the missing IDs and evidence kinds and refuses to call
either candidate defensible. This is a successful workflow demonstration, not a
manuscript-production claim.
