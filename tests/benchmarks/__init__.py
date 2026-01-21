"""Benchmark suite for sia-code retrieval quality.

Implements academic benchmarks (RepoEval, SWE-bench style) with metrics:
- Recall@k, Precision@k
- nDCG@k (Normalized Discounted Cumulative Gain)
- MRR (Mean Reciprocal Rank)
- Hit@k

Enables comparison with ChunkHound and other code search tools.
"""

from .metrics import (
    recall_at_k,
    precision_at_k,
    ndcg_at_k,
    mean_reciprocal_rank,
    hit_at_k,
)
from .harness import RetrievalBenchmark

__all__ = [
    "recall_at_k",
    "precision_at_k",
    "ndcg_at_k",
    "mean_reciprocal_rank",
    "hit_at_k",
    "RetrievalBenchmark",
]
