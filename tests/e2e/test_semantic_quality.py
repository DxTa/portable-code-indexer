"""Semantic search quality tests with embeddings enabled.

Tests measure search quality using ground-truth queries from repository documentation.
Requires OPENAI_API_KEY to be set for embeddings.
"""

import pytest
from pathlib import Path

from .base_e2e_test import BaseE2ETest


class SemanticQualityMixin:
    """Mixin for semantic quality testing methods."""

    def calculate_reciprocal_rank(self, results: dict, ground_truth: dict) -> float:
        """Calculate reciprocal rank for a query.

        Args:
            results: Search results from CLI
            ground_truth: Dict with expected_symbols and expected_files

        Returns:
            Reciprocal rank (1/rank of first relevant result, 0 if none found)
        """
        result_list = results.get("results", [])

        expected_symbols = ground_truth.get("expected_symbols", [])
        expected_files = ground_truth.get("expected_files", [])

        for rank, result in enumerate(result_list, start=1):
            chunk = result["chunk"]
            symbol = chunk.get("symbol", "").lower()
            file_path = chunk.get("file_path", "").lower()

            # Check if this result matches expected symbols or files
            symbol_match = any(exp.lower() in symbol for exp in expected_symbols)
            file_match = any(exp.lower() in file_path for exp in expected_files)

            if symbol_match or file_match:
                return 1.0 / rank

        return 0.0  # No relevant result found

    def calculate_hit_at_k(self, results: dict, ground_truth: dict, k: int = 1) -> bool:
        """Check if any relevant result appears in top-k.

        Args:
            results: Search results from CLI
            ground_truth: Dict with expected_symbols and expected_files
            k: Number of top results to check

        Returns:
            True if relevant result found in top-k, False otherwise
        """
        result_list = results.get("results", [])[:k]

        expected_symbols = ground_truth.get("expected_symbols", [])
        expected_files = ground_truth.get("expected_files", [])

        for result in result_list:
            chunk = result["chunk"]
            symbol = chunk.get("symbol", "").lower()
            file_path = chunk.get("file_path", "").lower()

            symbol_match = any(exp.lower() in symbol for exp in expected_symbols)
            file_match = any(exp.lower() in file_path for exp in expected_files)

            if symbol_match or file_match:
                return True

        return False


class TestSemanticQualityClick(BaseE2ETest, SemanticQualityMixin):
    """Ground-truth semantic search tests for Click repository."""

    GROUND_TRUTH_QUERIES = [
        {
            "query": "how to create a command line interface",
            "expected_symbols": ["command", "Command", "decorator"],
            "expected_files": ["decorators.py", "core.py"],
            "min_mrr": 0.3,
        },
        {
            "query": "how to add options to a command",
            "expected_symbols": ["option", "Option"],
            "expected_files": ["decorators.py", "core.py"],
            "min_mrr": 0.3,
        },
        {
            "query": "how to prompt for user input",
            "expected_symbols": ["prompt", "Prompt"],
            "expected_files": ["termui.py", "decorators.py"],
            "min_mrr": 0.2,
        },
        {
            "query": "handle command line arguments",
            "expected_symbols": ["argument", "Argument", "parameter"],
            "expected_files": ["core.py", "decorators.py"],
            "min_mrr": 0.2,
        },
        {
            "query": "automatic help generation",
            "expected_symbols": ["help", "format_help"],
            "expected_files": ["core.py", "formatting.py"],
            "min_mrr": 0.2,
        },
    ]

    def test_semantic_search_mrr(self, indexed_repo):
        """Measure Mean Reciprocal Rank for ground-truth queries."""
        total_rr = 0
        hit_at_1 = 0
        hit_at_5 = 0

        print("\n=== Semantic Search Quality Results ===\n")

        for gt in self.GROUND_TRUTH_QUERIES:
            # Run semantic search (no --regex flag)
            results = self.search_json(gt["query"], indexed_repo, regex=False, limit=10)

            # Calculate metrics
            rr = self.calculate_reciprocal_rank(results, gt)
            hit1 = self.calculate_hit_at_k(results, gt, k=1)
            hit5 = self.calculate_hit_at_k(results, gt, k=5)

            total_rr += rr
            if hit1:
                hit_at_1 += 1
            if hit5:
                hit_at_5 += 1

            print(f"Query: {gt['query'][:50]}...")
            print(f"  RR: {rr:.3f}  Hit@1: {hit1}  Hit@5: {hit5}")

            # Show top result for debugging
            if results.get("results"):
                top = results["results"][0]
                print(f"  Top: {top['chunk']['symbol']} in {Path(top['chunk']['file_path']).name}")
            print()

        # Calculate aggregate metrics
        num_queries = len(self.GROUND_TRUTH_QUERIES)
        mrr = total_rr / num_queries
        hit1_pct = (hit_at_1 / num_queries) * 100
        hit5_pct = (hit_at_5 / num_queries) * 100

        print("=== Aggregate Metrics ===")
        print(f"MRR@10: {mrr:.3f}")
        print(f"Hit@1:  {hit1_pct:.1f}%  ({hit_at_1}/{num_queries})")
        print(f"Hit@5:  {hit5_pct:.1f}%  ({hit_at_5}/{num_queries})")
        print()

        # Assert minimum quality thresholds
        assert mrr >= 0.2, f"MRR {mrr:.3f} below threshold 0.2"
        assert hit5_pct >= 40, f"Hit@5 {hit5_pct:.1f}% below threshold 40%"

    def test_semantic_vs_lexical_comparison(self, indexed_repo):
        """Compare semantic search to lexical search for natural language queries."""
        queries = [
            "how to create a command line interface",
            "handle user arguments",
            "display help messages",
        ]

        print("\n=== Semantic vs Lexical Comparison ===\n")

        for query in queries:
            semantic = self.search_json(query, indexed_repo, regex=False, limit=5)
            lexical = self.search_json(query, indexed_repo, regex=True, limit=5)

            sem_count = len(semantic.get("results", []))
            lex_count = len(lexical.get("results", []))

            print(f"Query: {query[:40]}...")
            print(f"  Semantic: {sem_count} results")
            print(f"  Lexical:  {lex_count} results")

            # Show if semantic found something lexical didn't
            if sem_count > 0 and lex_count == 0:
                print("  ✓ Semantic found results where lexical found none")

            print()

    def test_top_result_relevance(self, indexed_repo):
        """Verify top semantic result is contextually relevant."""
        test_cases = [
            {
                "query": "how to create a command",
                "relevant_keywords": ["command", "@click", "decorator", "def"],
            },
            {
                "query": "add options to commands",
                "relevant_keywords": ["option", "@click", "parameter"],
            },
        ]

        print("\n=== Top Result Relevance ===\n")

        for case in test_cases:
            results = self.search_json(case["query"], indexed_repo, regex=False, limit=3)

            if not results.get("results"):
                print(f"Query: {case['query']}")
                print("  No results found")
                print()
                continue

            top_result = results["results"][0]
            code = top_result["chunk"]["code"].lower()
            symbol = top_result["chunk"]["symbol"].lower()

            # Check if top result contains relevant keywords
            relevance_score = sum(
                1 for kw in case["relevant_keywords"] if kw.lower() in code or kw.lower() in symbol
            )

            print(f"Query: {case['query']}")
            print(f"  Top result: {top_result['chunk']['symbol']}")
            print(f"  Relevance: {relevance_score}/{len(case['relevant_keywords'])} keywords found")
            print()

            # Top result should contain at least some relevant keywords
            assert relevance_score > 0, (
                f"Top result for '{case['query']}' contains no relevant keywords"
            )


class TestSemanticQualityPQueue(BaseE2ETest, SemanticQualityMixin):
    """Ground-truth semantic search tests for p-queue repository."""

    GROUND_TRUTH_QUERIES = [
        {
            "query": "how to limit concurrency in async operations",
            "expected_symbols": ["PQueue", "concurrency"],
            "expected_files": ["queue.ts", "index.ts"],
            "min_mrr": 0.3,
        },
        {
            "query": "how to pause and resume a queue",
            "expected_symbols": ["pause", "start"],
            "expected_files": ["queue.ts"],
            "min_mrr": 0.3,
        },
        {
            "query": "wait for queue to become empty",
            "expected_symbols": ["onEmpty", "empty"],
            "expected_files": ["queue.ts"],
            "min_mrr": 0.3,
        },
        {
            "query": "rate limiting async operations",
            "expected_symbols": ["intervalCap", "interval", "rate"],
            "expected_files": ["queue.ts"],
            "min_mrr": 0.2,
        },
    ]

    def test_semantic_search_mrr(self, indexed_repo):
        """Measure Mean Reciprocal Rank for p-queue ground-truth queries."""
        total_rr = 0
        hit_at_1 = 0
        hit_at_5 = 0

        print("\n=== Semantic Search Quality Results (p-queue) ===\n")

        for gt in self.GROUND_TRUTH_QUERIES:
            results = self.search_json(gt["query"], indexed_repo, regex=False, limit=10)

            rr = self.calculate_reciprocal_rank(results, gt)
            hit1 = self.calculate_hit_at_k(results, gt, k=1)
            hit5 = self.calculate_hit_at_k(results, gt, k=5)

            total_rr += rr
            if hit1:
                hit_at_1 += 1
            if hit5:
                hit_at_5 += 1

            print(f"Query: {gt['query'][:50]}...")
            print(f"  RR: {rr:.3f}  Hit@1: {hit1}  Hit@5: {hit5}")

            if results.get("results"):
                top = results["results"][0]
                print(f"  Top: {top['chunk']['symbol']} in {Path(top['chunk']['file_path']).name}")
            print()

        num_queries = len(self.GROUND_TRUTH_QUERIES)
        mrr = total_rr / num_queries
        hit1_pct = (hit_at_1 / num_queries) * 100
        hit5_pct = (hit_at_5 / num_queries) * 100

        print("=== Aggregate Metrics ===")
        print(f"MRR@10: {mrr:.3f}")
        print(f"Hit@1:  {hit1_pct:.1f}%  ({hit_at_1}/{num_queries})")
        print(f"Hit@5:  {hit5_pct:.1f}%  ({hit_at_5}/{num_queries})")
        print()

        assert mrr >= 0.2, f"MRR {mrr:.3f} below threshold 0.2"
        assert hit5_pct >= 40, f"Hit@5 {hit5_pct:.1f}% below threshold 40%"


# Pytest configuration for running these tests
pytestmark = pytest.mark.skipif(
    "not config.getoption('--run-semantic-quality')",
    reason="Semantic quality tests require --run-semantic-quality flag and OPENAI_API_KEY",
)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--run-semantic-quality"])
