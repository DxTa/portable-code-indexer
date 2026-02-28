# Performance Analysis (Compact)

## Typical Expectations

- `search --regex`: usually lowest-latency mode
- `search --semantic-only`: usually higher latency than regex
- `index --update`: much faster than full rebuild for small changes

Actual speed depends on repo size, hardware, and ChunkHound semantic/provider setup.

## Quick Optimization Checklist

1. Use `sia-code index --update` for daily work
2. Use `--regex` for symbol/identifier lookup
3. Use tighter regex terms (or include path-like hints) to reduce noise
4. Use `--parallel` for large initial indexing runs
5. Start embed daemon when doing repeated memory embedding operations

## Useful Commands

```bash
sia-code status
sia-code compact
sia-code index --update
sia-code search --regex "pattern"
```

## Bottleneck Hints

- Slow index build: reduce indexed scope or enable parallel workers
- Slow semantic queries: verify ChunkHound provider setup and model/network health
- Noisy result set: narrow regex terms and include path-like query hints

## Related Docs

- `docs/INDEXING.md`
- `docs/QUERYING.md`
- `docs/BENCHMARK_RESULTS.md`
