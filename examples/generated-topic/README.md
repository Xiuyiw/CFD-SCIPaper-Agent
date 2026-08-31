# Generated-topic walkthrough

This synthetic example demonstrates the v0.2 planning path from mature structured records to
evidence-bounded topic candidates. It does not represent a validated CFD study.

```bash
python examples/generated-topic/prepare_project.py generated-topic-project
cfdpaper plan generated-topic-project --provider offline
```

The command writes recoverable artifacts under
`generated-topic-project/.cfdpaper/outputs/plan/`, prints 2–4 ranked candidates, and leaves author
approval unset. Re-running it reuses the matching journal; `--regenerate` starts a new deterministic
attempt.

The example deliberately begins with structured scientific records. Automatic extraction from raw
solver result files remains outside v0.2.0.
