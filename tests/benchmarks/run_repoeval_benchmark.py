"""Run RepoEval benchmark on sia-code to establish absolute baseline.

This script:
1. Loads RepoEval queries for a specific repository
2. Runs sia-code search on each query
3. Computes retrieval metrics (Recall@k, Precision@k, MRR)
4. Compares against ground truth files
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.benchmarks.datasets.repoeval_loader import (
    load_repoeval,
    get_ground_truth_files,
    RepoEvalQuery,
)
from tests.benchmarks.metrics import recall_at_k, precision_at_k, mean_reciprocal_rank


def run_sia_code_search(repo_path: Path, query: str, top_k: int = 10) -> list[str]:
    """Run sia-code search and return file paths.

    Args:
        repo_path: Path to the indexed repository
        query: Search query
        top_k: Number of results to return

    Returns:
        List of file paths (relative to repo)
    """
    try:
        # Use 'sia-code' from the same environment as the running Python
        sia_code_path = str(Path(sys.executable).parent / "sia-code")
        result = subprocess.run(
            [sia_code_path, "search", query, "--limit", str(top_k)],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=30,
        )

        if result.returncode != 0:
            print(f"ERROR: sia-code search failed: {result.stderr}", file=sys.stderr)
            return []

        # Parse output to extract file paths
        # Handle line wrapping: paths may be split across multiple lines
        files = []
        lines = result.stdout.strip().split("\n")

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Look for lines starting with "/" (absolute paths)
            if line.startswith("/"):
                # Check if next line completes the path (filename with ":")
                full_path = line
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # If next line starts with filename char (including underscore) and has ":", it's the continuation
                    if (
                        next_line
                        and (next_line[0].isalnum() or next_line[0] == "_")
                        and ":" in next_line
                    ):
                        full_path = line + next_line
                        i += 1  # Skip the next line since we consumed it

                # Extract file path (before the ":")
                if ":" in full_path:
                    file_path = full_path.split(":")[0].strip()

                    # Convert absolute path to relative path
                    file_path = str(Path(file_path).resolve())
                    repo_path_str = str(repo_path.resolve())

                    if file_path.startswith(repo_path_str):
                        # Make relative to repo
                        file_path = file_path[len(repo_path_str) :].lstrip("/")
                    else:
                        # Already relative, normalize
                        file_path = file_path.lstrip("./")

                    files.append(file_path)

            i += 1

        return files

    except subprocess.TimeoutExpired:
        print(f"WARNING: Search timed out for query: {query[:50]}...", file=sys.stderr)
        return []
    except Exception as e:
        print(f"ERROR: Search failed: {e}", file=sys.stderr)
        return []


def run_benchmark(
    repo_path: Path,
    dataset_path: Path,
    repo_name: str,
    max_queries: Optional[int] = None,
    k_values: list[int] = [1, 5, 10],
) -> dict:
    """Run benchmark on a repository.

    Args:
        repo_path: Path to the indexed repository
        dataset_path: Path to RepoEval dataset JSONL
        repo_name: Repository name to filter (e.g., "huggingface_diffusers")
        max_queries: Maximum queries to evaluate (None = all)
        k_values: K values for Recall@k and Precision@k

    Returns:
        Dictionary of results
    """
    # Load queries
    print(f"Loading queries for {repo_name}...")
    queries = load_repoeval(dataset_path, repo_filter=repo_name, max_queries=max_queries)
    print(f"Loaded {len(queries)} queries")

    # Initialize results
    results = {f"recall@{k}": [] for k in k_values}
    results.update({f"precision@{k}": [] for k in k_values})
    results["mrr"] = []
    results["queries_processed"] = 0
    results["queries_failed"] = 0

    # Run retrieval for each query
    for i, query in enumerate(queries):
        if (i + 1) % 10 == 0:
            print(f"Processing query {i + 1}/{len(queries)}...")

        # Get ground truth
        ground_truth_files = get_ground_truth_files(query)

        # Run search
        retrieved_files = run_sia_code_search(repo_path, query.query_text, top_k=max(k_values))

        if not retrieved_files:
            results["queries_failed"] += 1
            # Add 0 scores for this query
            for k in k_values:
                results[f"recall@{k}"].append(0.0)
                results[f"precision@{k}"].append(0.0)
            results["mrr"].append(0.0)
            continue

        results["queries_processed"] += 1

        # Compute metrics for each k
        for k in k_values:
            recall = recall_at_k(retrieved_files[:k], set(ground_truth_files), k)
            precision = precision_at_k(retrieved_files[:k], set(ground_truth_files), k)
            results[f"recall@{k}"].append(recall)
            results[f"precision@{k}"].append(precision)

        # Compute MRR
        mrr = mean_reciprocal_rank(retrieved_files, set(ground_truth_files))
        results["mrr"].append(mrr)

    # Aggregate results
    aggregated = {
        "repo_name": repo_name,
        "total_queries": len(queries),
        "queries_processed": results["queries_processed"],
        "queries_failed": results["queries_failed"],
    }

    for k in k_values:
        recall_scores = [
            r for r in results[f"recall@{k}"] if r > 0 or results["queries_processed"] > 0
        ]
        precision_scores = [
            p for p in results[f"precision@{k}"] if p > 0 or results["queries_processed"] > 0
        ]

        aggregated[f"recall@{k}"] = (
            sum(recall_scores) / len(recall_scores) if recall_scores else 0.0
        )
        aggregated[f"precision@{k}"] = (
            sum(precision_scores) / len(precision_scores) if precision_scores else 0.0
        )

    mrr_scores = [m for m in results["mrr"] if m > 0 or results["queries_processed"] > 0]
    aggregated["mrr"] = sum(mrr_scores) / len(mrr_scores) if mrr_scores else 0.0

    return aggregated


def main():
    import argparse

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Run RepoEval benchmark on sia-code")
    parser.add_argument("--repo", default="huggingface_diffusers", help="Repository name")
    parser.add_argument("--output", type=Path, help="Output JSON file path")
    parser.add_argument("--sample-size", type=int, default=50, help="Number of queries to test")
    args = parser.parse_args()

    # Configuration
    repo_name = args.repo
    repo_path = Path(f"/tmp/CodeT/RepoCoder/repositories/{repo_name}")
    dataset_path = Path(
        "/tmp/CodeT/RepoCoder/datasets/api_level_completion_2k_context_codex.test.jsonl"
    )

    # Check paths exist
    if not repo_path.exists():
        print(f"ERROR: Repository not found: {repo_path}")
        print("Please extract RepoEval repositories first")
        sys.exit(1)

    if not dataset_path.exists():
        print(f"ERROR: Dataset not found: {dataset_path}")
        sys.exit(1)

    if not (repo_path / ".sia-code").exists():
        print(f"ERROR: Repository not indexed: {repo_path}")
        print("Run 'sia-code index' first")
        sys.exit(1)

    # Run benchmark (start with small sample for testing)
    print("\n=== RepoEval Benchmark: Sia-code Absolute Performance ===\n")
    print(f"Running with {args.sample_size} queries...")
    print(f"(Each query takes ~15s, so this will take ~{args.sample_size * 15 / 60:.0f} minutes)")

    results = run_benchmark(
        repo_path=repo_path,
        dataset_path=dataset_path,
        repo_name=repo_name,
        max_queries=args.sample_size,
        k_values=[1, 5, 10],
    )

    # Print results
    print("\n=== Results ===\n")
    print(f"Repository: {results['repo_name']}")
    print(f"Total queries: {results['total_queries']}")
    print(f"Queries processed: {results['queries_processed']}")
    print(f"Queries failed: {results['queries_failed']}")
    print()
    print(f"Recall@1:  {results['recall@1']:.1%}")
    print(f"Recall@5:  {results['recall@5']:.1%}")
    print(f"Recall@10: {results['recall@10']:.1%}")
    print()
    print(f"Precision@1:  {results['precision@1']:.1%}")
    print(f"Precision@5:  {results['precision@5']:.1%}")
    print(f"Precision@10: {results['precision@10']:.1%}")
    print()
    print(f"MRR: {results['mrr']:.3f}")

    # Save results
    if args.output:
        output_file = args.output
    else:
        output_file = (
            Path(__file__).parent.parent.parent
            / "results"
            / "repoeval"
            / f"sia-code_{repo_name}_baseline.json"
        )

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {output_file}")

    # Compare with cAST
    print("\n=== Comparison with cAST (from paper) ===\n")
    cast_recall_5 = 0.77  # Average from cAST paper
    sia_recall_5 = results["recall@5"]

    print(f"cAST Recall@5 (RepoEval):    ~{cast_recall_5:.1%}")
    print(f"Sia-code Recall@5 (RepoEval): {sia_recall_5:.1%}")
    print(f"Difference:                   {sia_recall_5 - cast_recall_5:+.1%}")

    if sia_recall_5 < cast_recall_5:
        ratio = cast_recall_5 / sia_recall_5 if sia_recall_5 > 0 else float("inf")
        print(f"cAST is {ratio:.1f}x better in absolute performance")
    else:
        ratio = sia_recall_5 / cast_recall_5
        print(f"Sia-code is {ratio:.1f}x better in absolute performance!")


if __name__ == "__main__":
    main()
