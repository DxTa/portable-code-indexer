"""Benchmark harness for retrieval evaluation.

Provides infrastructure to evaluate retrieval systems on standard benchmarks.
Compatible with RepoEval, SWE-bench, and CrossCodeEval datasets.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Callable, Any
from statistics import mean

from .metrics import calculate_all_metrics

logger = logging.getLogger(__name__)


@dataclass
class Query:
    """A single benchmark query with ground truth."""

    id: str
    query_text: str
    relevant_docs: Set[str]  # IDs of relevant documents
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchmarkDataset:
    """A collection of queries for benchmarking."""

    name: str
    queries: List[Query]
    corpus: Dict[str, str] = field(default_factory=dict)  # doc_id -> content
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.queries)

    @classmethod
    def from_json(cls, path: Path) -> "BenchmarkDataset":
        """Load dataset from JSON file.

        Expected format:
        {
            "name": "dataset_name",
            "queries": [
                {
                    "id": "q1",
                    "query_text": "how to create a command",
                    "relevant_docs": ["doc1", "doc2"]
                }
            ],
            "corpus": {
                "doc1": "content here..."
            }
        }
        """
        with open(path) as f:
            data = json.load(f)

        queries = [
            Query(
                id=q["id"],
                query_text=q["query_text"],
                relevant_docs=set(q["relevant_docs"]),
                metadata=q.get("metadata", {}),
            )
            for q in data.get("queries", [])
        ]

        return cls(
            name=data.get("name", path.stem),
            queries=queries,
            corpus=data.get("corpus", {}),
            metadata=data.get("metadata", {}),
        )


class RetrievalBenchmark:
    """Benchmark harness for evaluating retrieval systems."""

    def __init__(self, dataset: BenchmarkDataset, k_values: List[int] = None):
        """Initialize benchmark.

        Args:
            dataset: Dataset to evaluate on
            k_values: List of k values for @k metrics (default: [1, 5, 10])
        """
        self.dataset = dataset
        self.k_values = k_values or [1, 5, 10]

    def evaluate(
        self, retriever: Callable[[str], List[str]], max_k: int = None, verbose: bool = False
    ) -> Dict[str, float]:
        """Evaluate a retriever on the dataset.

        Args:
            retriever: Function that takes query text and returns ranked list of doc IDs
            max_k: Maximum k to retrieve (default: max of k_values)
            verbose: Print per-query results

        Returns:
            Dict of aggregated metrics across all queries
        """
        if max_k is None:
            max_k = max(self.k_values)

        all_metrics = []

        for query in self.dataset.queries:
            # Get retrieval results
            retrieved = retriever(query.query_text)[:max_k]

            # Calculate metrics for this query
            metrics = calculate_all_metrics(retrieved, query.relevant_docs, self.k_values)
            all_metrics.append(metrics)

            if verbose:
                logger.info(f"Query {query.id}: {query.query_text[:50]}...")
                logger.info(f"  Retrieved: {len(retrieved)} docs")
                logger.info(f"  Relevant: {len(query.relevant_docs)} docs")
                logger.info(f"  Metrics: {metrics}")

        # Aggregate metrics across queries
        aggregated = {}
        if all_metrics:
            for key in all_metrics[0].keys():
                aggregated[key] = mean(m[key] for m in all_metrics)

        return aggregated

    def evaluate_multiple(
        self, retrievers: Dict[str, Callable[[str], List[str]]], output_path: Path = None
    ) -> Dict[str, Dict[str, float]]:
        """Evaluate multiple retrievers and compare.

        Args:
            retrievers: Dict mapping system name to retriever function
            output_path: Optional path to save results JSON

        Returns:
            Dict mapping system name to metrics
        """
        results = {}

        for name, retriever in retrievers.items():
            logger.info(f"Evaluating {name}...")
            results[name] = self.evaluate(retriever, verbose=True)

        if output_path:
            with open(output_path, "w") as f:
                json.dump(results, f, indent=2)
            logger.info(f"Results saved to {output_path}")

        return results

    def print_comparison_table(self, results: Dict[str, Dict[str, float]]):
        """Print formatted comparison table.

        Args:
            results: Dict mapping system name to metrics (from evaluate_multiple)
        """
        if not results:
            return

        # Get all metric names
        metric_names = list(next(iter(results.values())).keys())

        # Print header
        print(f"\n{'System':<20} | " + " | ".join(f"{m:>10}" for m in metric_names))
        print("-" * (20 + len(metric_names) * 13))

        # Print rows
        for system, metrics in results.items():
            values = " | ".join(f"{metrics[m]:>10.4f}" for m in metric_names)
            print(f"{system:<20} | {values}")

        print()
