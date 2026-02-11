# Test Results (Compact)

This file tracks high-level verification outcomes.

## What is covered

- unit tests (`tests/unit/`)
- integration tests (`tests/integration/`)
- e2e CLI scenarios (`tests/e2e/`)
- benchmark harness checks (`tests/benchmarks/`)

## Typical Commands

```bash
pytest -q
pytest tests/integration -q
pytest tests/e2e -q
pytest tests/benchmarks -q
```

## Reporting Guidance

- Keep this file brief.
- Put detailed logs in CI artifacts or issue comments.
- Link failures to exact test path and command.
