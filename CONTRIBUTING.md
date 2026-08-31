# Contributing

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
