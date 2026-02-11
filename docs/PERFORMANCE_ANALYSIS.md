# Performance Analysis (Compact)

## Typical Expectations

- `search --regex`: usually lowest-latency mode
- hybrid `search`: additional semantic overhead
- `index --update`: much faster than full rebuild for small changes

Actual speed depends on repo size, hardware, and embedding configuration.

## Quick Optimization Checklist

1. Use `sia-code index --update` for daily work
2. Use `--regex` for symbol/identifier lookup
3. Add `--no-deps` to reduce large dependency noise
4. Use `--parallel` for large initial indexing runs
5. Start embed daemon when doing repeated semantic/hybrid queries

## Useful Commands

```bash
sia-code status
sia-code compact
sia-code index --update
sia-code search --regex "pattern"
```

## Bottleneck Hints

- Slow index build: reduce indexed scope or enable parallel workers
- Slow semantic/hybrid queries: ensure embed daemon is healthy
- Noisy result set: use dependency filters (`--no-deps` / `--deps-only`)

## Related Docs

- `docs/INDEXING.md`
- `docs/QUERYING.md`
- `docs/BENCHMARK_RESULTS.md`
