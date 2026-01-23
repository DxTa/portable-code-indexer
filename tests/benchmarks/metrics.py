"""Core evaluation metrics for retrieval benchmarks.

Implements standard IR metrics compatible with ChunkHound's evaluation:
- Recall@k, Precision@k
- nDCG@k (Normalized Discounted Cumulative Gain)
- MRR (Mean Reciprocal Rank)
- Hit@k
"""

import math
from typing import List, Set


def recall_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    """Calculate Recall@k.

    Recall = |relevant ∩ retrieved_top_k| / |relevant|

    Args:
        retrieved: List of retrieved document IDs (ordered by rank)
        relevant: Set of relevant document IDs (ground truth)
        k: Number of top results to consider

    Returns:
        Recall@k score in [0, 1]
    """
    if not relevant:
        return 0.0

    top_k = set(retrieved[:k])
    relevant_retrieved = top_k & relevant
    return len(relevant_retrieved) / len(relevant)


def precision_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    """Calculate Precision@k.

    Precision = |relevant ∩ retrieved_top_k| / k

    Args:
        retrieved: List of retrieved document IDs (ordered by rank)
        relevant: Set of relevant document IDs (ground truth)
        k: Number of top results to consider

    Returns:
        Precision@k score in [0, 1]
    """
    if k == 0:
        return 0.0

    top_k = set(retrieved[:k])
    relevant_retrieved = top_k & relevant
    return len(relevant_retrieved) / k


def dcg_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    """Calculate Discounted Cumulative Gain at k.

    DCG = Σ(rel_i / log2(i + 1)) for i in [1, k]

    Args:
        retrieved: List of retrieved document IDs (ordered by rank)
        relevant: Set of relevant document IDs (ground truth)
        k: Number of top results to consider

    Returns:
        DCG@k score
    """
    dcg = 0.0
    for i, doc_id in enumerate(retrieved[:k], start=1):
        if doc_id in relevant:
            # Binary relevance: 1 if relevant, 0 otherwise
            dcg += 1.0 / math.log2(i + 1)
    return dcg


def ndcg_at_k(retrieved: List[str], relevant: Set[str], k: int) -> float:
    """Calculate Normalized Discounted Cumulative Gain at k.

    nDCG = DCG@k / IDCG@k
    where IDCG is the ideal DCG (perfect ranking)

    Args:
        retrieved: List of retrieved document IDs (ordered by rank)
        relevant: Set of relevant document IDs (ground truth)
        k: Number of top results to consider

    Returns:
        nDCG@k score in [0, 1]
    """
    if not relevant:
        return 0.0

    dcg = dcg_at_k(retrieved, relevant, k)

    # Ideal DCG: all relevant docs ranked first
    ideal_retrieved = list(relevant) + [f"dummy_{i}" for i in range(k)]
    idcg = dcg_at_k(ideal_retrieved, relevant, k)

    if idcg == 0.0:
        return 0.0

    return dcg / idcg


def mean_reciprocal_rank(retrieved: List[str], relevant: Set[str]) -> float:
    """Calculate Mean Reciprocal Rank (MRR).

    MRR = 1 / rank_of_first_relevant_doc
    Returns 0 if no relevant doc found.

    Args:
        retrieved: List of retrieved document IDs (ordered by rank)
        relevant: Set of relevant document IDs (ground truth)

    Returns:
        Reciprocal rank in [0, 1]
    """
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant:
            return 1.0 / rank
    return 0.0


def hit_at_k(retrieved: List[str], relevant: Set[str], k: int) -> bool:
    """Check if any relevant document appears in top-k (binary).

    Args:
        retrieved: List of retrieved document IDs (ordered by rank)
        relevant: Set of relevant document IDs (ground truth)
        k: Number of top results to consider

    Returns:
        True if at least one relevant doc in top-k, False otherwise
    """
    top_k = set(retrieved[:k])
    return len(top_k & relevant) > 0


def calculate_all_metrics(
    retrieved: List[str], relevant: Set[str], k_values: List[int] = None
) -> dict:
    """Calculate all metrics at once for efficiency.

    Args:
        retrieved: List of retrieved document IDs (ordered by rank)
        relevant: Set of relevant document IDs (ground truth)
        k_values: List of k values to evaluate (default: [1, 5, 10])

    Returns:
        Dict with all metric values
    """
    if k_values is None:
        k_values = [1, 5, 10]

    metrics = {"mrr": mean_reciprocal_rank(retrieved, relevant)}

    for k in k_values:
        metrics[f"recall@{k}"] = recall_at_k(retrieved, relevant, k)
        metrics[f"precision@{k}"] = precision_at_k(retrieved, relevant, k)
        metrics[f"ndcg@{k}"] = ndcg_at_k(retrieved, relevant, k)
        metrics[f"hit@{k}"] = float(hit_at_k(retrieved, relevant, k))

    return metrics
