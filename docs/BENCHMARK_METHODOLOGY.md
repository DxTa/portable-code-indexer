# Benchmark Methodology (Compact)

This project uses RepoEval-style retrieval evaluation for search quality checks.

> Note: The benchmark harness in `tests/benchmarks/` targets legacy in-process retrievers. ChunkHound-backed CLI search/research should be benchmarked separately as end-to-end CLI runs.

## Scope

- Evaluate retrieval quality (not answer generation)
- Compare lexical, hybrid, and semantic settings in the legacy retriever stack
- Use consistent query set and top-k metrics

## Minimal Reproduction Flow

```bash
# run benchmark harness
pytest tests/benchmarks -q

# run benchmark scripts
pkgx python tests/benchmarks/run_repoeval_benchmark.py
pkgx python tests/benchmarks/run_full_repoeval_benchmark.py
```

## What to record

- Recall@k (especially Recall@5)
- indexing time and query latency
- configuration used (`chunkhound.default_search_mode` for CLI runs, `vector_weight` for legacy runs, embedding settings)

## Fairness Rules

- Same datasets and query sets across runs
- Same `k` and output filtering conditions
- Clean index when comparing major config changes

## Related Paths

- `tests/benchmarks/metrics.py`
- `tests/benchmarks/retrievers.py`
- `results/academic/`
