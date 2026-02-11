# Benchmark Results (Compact)

## Headline

- RepoEval Recall@5: **89.9%** (reported)
- Improvement over cAST baseline: **+12.9 points** (reported)

## Practical Takeaways

- Lexical-heavy search performs strongly for code identifiers.
- Hybrid can still be useful for natural-language style queries.
- For daily debugging, `--regex` is often the fastest path.

## Recommended Starting Config

```bash
sia-code config set search.vector_weight 0.0
```

Then adjust only if your query style is mostly conceptual.

## Where to find raw benchmark tooling

- `tests/benchmarks/`
- `results/academic/`

## Related Docs

- `docs/BENCHMARK_METHODOLOGY.md`
- `docs/PERFORMANCE_ANALYSIS.md`
