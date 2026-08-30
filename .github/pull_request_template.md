## Summary

<!-- Explain the user-facing or scientific-assurance outcome and why this change is needed. -->

## Scope and boundaries

<!-- List important assumptions, unsupported cases, and author-review boundaries. -->

## Verification

- [ ] Tests cover the changed behavior and pass locally.
- [ ] `python -m ruff check .` passes.
- [ ] `python -m ruff format --check .` passes for the changed public code and documentation.
- [ ] Packaging or CLI smoke checks were run when the public surface changed.
- [ ] Units, provenance, missing-data behavior, and failure modes were reviewed where relevant.

Commands and results:

```text
Paste concise verification output here.
```

## Public-data and licensing checklist

- [ ] No confidential solver file, proprietary mesh, unpublished manuscript/result, credential,
      private absolute path, personal identifier, or company-owned dataset is included.
- [ ] New fixtures are synthetic or redistributable and their origin is documented.
- [ ] I have the right to submit this contribution under Apache License 2.0.
- [ ] Required third-party licenses or attribution notices are identified.

## Related issue

<!-- Use "Closes #123" when applicable. -->
