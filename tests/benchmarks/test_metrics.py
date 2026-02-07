"""Tests for benchmark metrics.

Verifies correctness of Recall, Precision, nDCG, MRR calculations.
"""

import pytest
from tests.benchmarks.metrics import (
    recall_at_k,
    precision_at_k,
    ndcg_at_k,
    mean_reciprocal_rank,
    hit_at_k,
    calculate_all_metrics,
)


class TestMetrics:
    """Test suite for retrieval metrics."""

    def test_recall_at_k_perfect(self):
        """Test recall with perfect retrieval."""
        retrieved = ["doc1", "doc2", "doc3"]
        relevant = {"doc1", "doc2", "doc3"}

        assert recall_at_k(retrieved, relevant, k=3) == 1.0
        assert recall_at_k(retrieved, relevant, k=5) == 1.0

    def test_recall_at_k_partial(self):
        """Test recall with partial retrieval."""
        retrieved = ["doc1", "doc2", "doc4"]
        relevant = {"doc1", "doc2", "doc3"}

        # Found 2 out of 3 relevant
        assert recall_at_k(retrieved, relevant, k=3) == 2 / 3

    def test_recall_at_k_none(self):
        """Test recall with no relevant docs retrieved."""
        retrieved = ["doc4", "doc5"]
        relevant = {"doc1", "doc2", "doc3"}

        assert recall_at_k(retrieved, relevant, k=2) == 0.0

    def test_precision_at_k_perfect(self):
        """Test precision with all relevant."""
        retrieved = ["doc1", "doc2", "doc3"]
        relevant = {"doc1", "doc2", "doc3"}

        assert precision_at_k(retrieved, relevant, k=3) == 1.0

    def test_precision_at_k_partial(self):
        """Test precision with some irrelevant."""
        retrieved = ["doc1", "doc4", "doc2"]
        relevant = {"doc1", "doc2", "doc3"}

        # 2 relevant out of 3 retrieved
        assert precision_at_k(retrieved, relevant, k=3) == 2 / 3

    def test_mrr_first_position(self):
        """Test MRR when first result is relevant."""
        retrieved = ["doc1", "doc4", "doc5"]
        relevant = {"doc1", "doc2"}

        assert mean_reciprocal_rank(retrieved, relevant) == 1.0

    def test_mrr_second_position(self):
        """Test MRR when second result is relevant."""
        retrieved = ["doc4", "doc1", "doc5"]
        relevant = {"doc1", "doc2"}

        assert mean_reciprocal_rank(retrieved, relevant) == 0.5

    def test_mrr_no_relevant(self):
        """Test MRR when no relevant docs retrieved."""
        retrieved = ["doc4", "doc5", "doc6"]
        relevant = {"doc1", "doc2"}

        assert mean_reciprocal_rank(retrieved, relevant) == 0.0

    def test_hit_at_k_true(self):
        """Test Hit@k when relevant doc in top-k."""
        retrieved = ["doc4", "doc1", "doc5"]
        relevant = {"doc1", "doc2"}

        assert hit_at_k(retrieved, relevant, k=2)
        assert hit_at_k(retrieved, relevant, k=5)

    def test_hit_at_k_false(self):
        """Test Hit@k when no relevant in top-k."""
        retrieved = ["doc4", "doc5", "doc1"]
        relevant = {"doc1", "doc2"}

        assert not hit_at_k(retrieved, relevant, k=2)
        assert not hit_at_k(retrieved, relevant, k=1)

    def test_ndcg_perfect_ranking(self):
        """Test nDCG with perfect ranking."""
        retrieved = ["doc1", "doc2", "doc3"]
        relevant = {"doc1", "doc2"}

        # Perfect ranking: relevant docs first
        ndcg = ndcg_at_k(retrieved, relevant, k=3)
        assert ndcg == 1.0

    def test_ndcg_imperfect_ranking(self):
        """Test nDCG with imperfect ranking."""
        retrieved = ["doc3", "doc1", "doc2"]
        relevant = {"doc1", "doc2"}

        # Relevant docs not first: nDCG < 1.0
        ndcg = ndcg_at_k(retrieved, relevant, k=3)
        assert 0 < ndcg < 1.0

    def test_calculate_all_metrics(self):
        """Test bulk metric calculation."""
        retrieved = ["doc1", "doc4", "doc2"]
        relevant = {"doc1", "doc2", "doc3"}

        metrics = calculate_all_metrics(retrieved, relevant, k_values=[1, 3, 5])

        # Check all expected metrics present
        assert "mrr" in metrics
        assert "recall@1" in metrics
        assert "recall@3" in metrics
        assert "precision@1" in metrics
        assert "precision@3" in metrics
        assert "ndcg@1" in metrics
        assert "hit@1" in metrics

        # Verify values
        assert metrics["mrr"] == 1.0  # doc1 is first
        assert metrics["recall@3"] == 2 / 3  # found 2 of 3
        assert metrics["precision@3"] == 2 / 3  # 2 relevant in top 3
        assert metrics["hit@1"] == 1.0  # doc1 in top 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
