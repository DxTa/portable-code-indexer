# Benchmarks (Compact)

Benchmark utilities for retrieval quality and performance checks.

## Main goals

- compare retrieval modes/configurations
- measure recall-oriented quality metrics
- track indexing/query performance trends

## Run

```bash
pytest tests/benchmarks -q
pkgx python tests/benchmarks/run_repoeval_benchmark.py
pkgx python tests/benchmarks/run_full_repoeval_benchmark.py
```

## Output locations

- script outputs under benchmark/result directories
- curated academic snapshots under `results/academic/`

Keep this README short; put deep benchmark analysis in docs only when needed.
