# E2E Tests (Compact)

E2E tests validate real CLI behavior against real repositories.

## Scope

- init/index/search/research/status/compact flows
- multi-language repositories
- output format checks

## Run examples

```bash
# all e2e tests
pytest tests/e2e -q

# one language suite
pytest tests/e2e/test_python_e2e.py -q
```

## Environment notes

- some tests clone remote repos
- network and runtime cost can be high
- use targeted suites locally when iterating
