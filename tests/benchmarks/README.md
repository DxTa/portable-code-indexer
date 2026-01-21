# sia-code Retrieval Benchmarks

Comprehensive benchmark suite for evaluating sia-code retrieval quality and comparing with other code search tools (ChunkHound, etc.).

## Features

- **Academic Metrics**: Recall@k, Precision@k, nDCG@k, MRR
- **Chunking Comparison**: Compare AST-aware vs fixed-line/token chunking
- **Dataset Support**: Ground-truth queries from semantic quality tests
- **Extensible**: Easy to add new datasets (RepoEval, SWE-bench, CrossCodeEval)

## Quick Start

```bash
# Run benchmark with default dataset
python -m tests.benchmarks.run_benchmarks \\
    --dataset sia-code-click \\
    --output results/benchmark_results.json

# Run with custom k values
python -m tests.benchmarks.run_benchmarks \\
    --dataset sia-code-pqueue \\
    --k-values 1 5 10 20 \\
    --verbose
```

## Metrics

| Metric | Description | Formula |
|--------|-------------|---------|
| **Recall@k** | Fraction of relevant docs in top-k | `\|relevant ∩ top_k\| / \|relevant\|` |
| **Precision@k** | Fraction of top-k that are relevant | `\|relevant ∩ top_k\| / k` |
| **nDCG@k** | Normalized Discounted Cumulative Gain | `DCG@k / IDCG@k` |
| **MRR** | Mean Reciprocal Rank | `1 / rank_of_first_relevant` |
| **Hit@k** | Binary: any relevant in top-k | `1` if relevant in top-k else `0` |

## Architecture

```
tests/benchmarks/
├── __init__.py              # Public API exports
├── metrics.py               # Core metrics (Recall, Precision, nDCG, MRR)
├── harness.py               # Benchmark infrastructure
├── datasets/
│   ├── __init__.py
│   └── simple_loader.py     # Load sia-code ground-truth queries
├── chunking_comparison.py   # Compare chunking strategies
├── run_benchmarks.py        # CLI entry point
├── test_metrics.py          # Unit tests for metrics
└── README.md                # This file
```

## Datasets

### Current: sia-code Ground Truth

Leverages existing semantic quality tests:
- **click**: 5 queries about CLI creation, options, help
- **pqueue**: 4 queries about concurrency, pause/resume, rate limiting

### Future: Standard Benchmarks

- **RepoEval**: Code completion with long contexts
- **SWE-bench**: Software engineering task patches
- **CrossCodeEval**: Multi-language cross-file reasoning

## Chunking Strategies

| Strategy | Description | Baseline |
|----------|-------------|----------|
| `sia-code-ast` | Current tree-sitter AST-aware | ✓ Default |
| `fixed-line-50` | 50 lines per chunk | ChunkHound baseline |
| `fixed-line-100` | 100 lines per chunk | Baseline |
| `fixed-token-512` | ~512 tokens per chunk | Baseline |
| `fixed-token-1024` | ~1024 tokens per chunk | Baseline |

## Integration with sia-code Backend

To use with real sia-code retrieval (not dummy):

```python
from sia_code.storage.backend import MemvidBackend
from sia_code.search.service import SearchService

# Create backend
backend = MemvidBackend(path, embedding_enabled=True)
backend.open_index()

# Create retriever function
def sia_code_retriever(query: str) -> list:
    results = backend.search_semantic(query, k=10)
    return [r.chunk.id for r in results]

# Run benchmark
benchmark = RetrievalBenchmark(dataset)
metrics = benchmark.evaluate(sia_code_retriever)
```

## Expected Results (ChunkHound Comparison)

Based on ChunkHound's cAST paper showing +4.3 Recall@5 improvement:

| Chunking | Recall@5 | Precision@5 | MRR | nDCG@10 |
|----------|----------|-------------|-----|---------|
| sia-code-ast | TBD | TBD | TBD | TBD |
| fixed-line-50 | Baseline | Baseline | Baseline | Baseline |
| cAST (target) | +4.3 pts | +2.1 pts | +0.05 | +0.04 |

## Testing

```bash
# Run metric tests
pytest tests/benchmarks/test_metrics.py -v

# Run all benchmark tests
pytest tests/benchmarks/ -v
```

## References

- ChunkHound cAST: +4.3 Recall@5 on RepoEval
- ChunkHound benchmark: https://chunkhound.github.io/benchmark/
- RepoEval: https://github.com/microsoft/CodeBERT
- SWE-bench: https://www.swebench.com/
