"""CLI for running retrieval benchmarks.

Example usage:
    python -m tests.benchmarks.run_benchmarks \\
        --dataset sia-code-click \\
        --output results/benchmark_results.json
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.benchmarks.datasets.simple_loader import load_sia_code_test_dataset
from tests.benchmarks.harness import RetrievalBenchmark

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def dummy_retriever(query: str) -> list:
    """Placeholder retriever for demo purposes.

    In real usage, this would integrate with sia-code's search backend.
    """
    # TODO: Integrate with actual sia-code backend
    logger.warning("Using dummy retriever - integrate with sia-code backend for real results")
    return []


def main():
    parser = argparse.ArgumentParser(description="Run retrieval benchmarks")
    parser.add_argument(
        "--dataset",
        choices=["sia-code-click", "sia-code-pqueue"],
        default="sia-code-click",
        help="Dataset to evaluate on",
    )
    parser.add_argument(
        "--k-values", nargs="+", type=int, default=[1, 5, 10], help="K values for @k metrics"
    )
    parser.add_argument("--output", type=Path, help="Path to save results JSON")
    parser.add_argument("--verbose", action="store_true", help="Print detailed per-query results")

    args = parser.parse_args()

    # Load dataset
    logger.info(f"Loading dataset: {args.dataset}")
    repo_name = args.dataset.replace("sia-code-", "")
    dataset = load_sia_code_test_dataset(repo_name)
    logger.info(f"Loaded {len(dataset)} queries")

    # Create benchmark
    benchmark = RetrievalBenchmark(dataset, k_values=args.k_values)

    # Evaluate (using dummy retriever for now)
    logger.info("Running evaluation...")
    results = benchmark.evaluate(dummy_retriever, verbose=args.verbose)

    # Print results
    print("\n=== Benchmark Results ===")
    print(f"Dataset: {args.dataset}")
    print(f"Queries: {len(dataset)}\n")

    for metric, value in sorted(results.items()):
        print(f"{metric:<15} {value:.4f}")

    # Save results
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(
                {
                    "dataset": args.dataset,
                    "num_queries": len(dataset),
                    "k_values": args.k_values,
                    "metrics": results,
                },
                f,
                indent=2,
            )
        logger.info(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
