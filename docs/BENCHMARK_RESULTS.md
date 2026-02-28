# Benchmark Results (Compact)

## Headline

- RepoEval Recall@5: **89.9%** (reported)
- Improvement over cAST baseline: **+12.9 points** (reported)

> Note: These numbers are historical baselines from legacy in-process retrievers. Current CLI `search` and `research` are ChunkHound-backed.

## Practical Takeaways

- Lexical-heavy search performs strongly for code identifiers.
- For legacy retriever experiments, hybrid can still help natural-language style queries.
- For daily debugging, `--regex` is often the fastest path.

## Recommended Starting Config

```bash
sia-code config set chunkhound.default_search_mode regex
```

For legacy benchmark experiments, `search.vector_weight` remains available in the in-process retriever stack.

## Where to find raw benchmark tooling

- `tests/benchmarks/`
- `results/academic/`

## Related Docs

- `docs/BENCHMARK_METHODOLOGY.md`
- `docs/PERFORMANCE_ANALYSIS.md`
