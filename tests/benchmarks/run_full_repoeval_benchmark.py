#!/usr/bin/env python3
"""
Full RepoEval Benchmark - Matching cAST Paper Setup

This script runs the complete RepoEval benchmark exactly as described in the cAST paper:
- All 8 Python repositories
- All 200 queries per repository (1,600 total)
- File-level Recall@5, Precision@5, nDCG@5
- Results comparable to published cAST results

Usage:
    python run_full_repoeval_benchmark.py
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

# Repository configurations
REPOSITORIES = [
    {
        "name": "huggingface_diffusers",
        "path": "/tmp/CodeT/RepoCoder/repositories/huggingface_diffusers",
        "queries": 200,
    },
    {
        "name": "nerfstudio-project_nerfstudio",
        "path": "/tmp/CodeT/RepoCoder/repositories/nerfstudio-project_nerfstudio",
        "queries": 200,
    },
    {
        "name": "awslabs_fortuna",
        "path": "/tmp/CodeT/RepoCoder/repositories/awslabs_fortuna",
        "queries": 200,
    },
    {
        "name": "huggingface_evaluate",
        "path": "/tmp/CodeT/RepoCoder/repositories/huggingface_evaluate",
        "queries": 200,
    },
    {
        "name": "google_vizier",
        "path": "/tmp/CodeT/RepoCoder/repositories/google_vizier",
        "queries": 200,
    },
    {
        "name": "alibaba_FederatedScope",
        "path": "/tmp/CodeT/RepoCoder/repositories/alibaba_FederatedScope",
        "queries": 200,
    },
    {
        "name": "pytorch_rl",
        "path": "/tmp/CodeT/RepoCoder/repositories/pytorch_rl",
        "queries": 200,
    },
    {
        "name": "opendilab_ACE",
        "path": "/tmp/CodeT/RepoCoder/repositories/opendilab_ACE",
        "queries": 200,
    },
]

# Embedding configurations to test (based on preliminary results)
CONFIGS = [
    {
        "name": "bge_small_w05",
        "embedding_enabled": True,
        "embedding_model": "BAAI/bge-small-en-v1.5",
        "embedding_dims": 384,
        "vector_weight": 0.5,  # Best from preliminary results
        "description": "BGE-small hybrid (w=0.5) - Best preliminary result",
    },
    {
        "name": "lexical_only",
        "embedding_enabled": False,
        "embedding_model": "BAAI/bge-small-en-v1.5",
        "embedding_dims": 384,
        "vector_weight": 0.0,
        "description": "Lexical-only (FTS5 BM25) - Baseline",
    },
]

DATASET_PATH = Path(
    "/tmp/CodeT/RepoCoder/datasets/api_level_completion_2k_context_codex.test.jsonl"
)
RESULTS_DIR = Path("results/repoeval_full")
PCI_DIR = Path("/home/dxta/dev/portable-code-index/pci")


def index_repository(repo_path: Path, config: dict) -> tuple[float, dict]:
    """Index a repository with given configuration."""
    print(f"    Indexing {repo_path.name}...")

    # Clean old index
    sia_dir = repo_path / ".sia-code"
    if sia_dir.exists():
        import shutil

        shutil.rmtree(sia_dir)

    # Initialize with config
    init_script = f"""
import sys
sys.path.insert(0, '{PCI_DIR}')
from pathlib import Path
from sia_code.config import Config
from sia_code.cli import create_backend

sia_dir = Path('.sia-code')
sia_dir.mkdir(parents=True, exist_ok=True)
(sia_dir / 'cache').mkdir(exist_ok=True)

config = Config()
config.embedding.enabled = {config["embedding_enabled"]}
config.embedding.model = '{config["embedding_model"]}'
config.embedding.dimensions = {config["embedding_dims"]}
config.search.vector_weight = {config["vector_weight"]}
config.save(sia_dir / 'config.json')

backend = create_backend(sia_dir, config)
backend.create_index()
backend.close()
"""

    result = subprocess.run(
        [sys.executable, "-c", init_script],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Init failed: {result.stderr}")

    # Index repository
    start = time.time()
    # Use the sia-code from the same environment as the running Python
    sia_code_path = str(Path(sys.executable).parent / "sia-code")
    result = subprocess.run(
        [sia_code_path, "index", "."],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=1800,  # 30 minutes max
    )
    index_time = time.time() - start

    # Parse stats
    stats = {"files": 0, "chunks": 0}
    for line in result.stdout.split("\n"):
        if "Files indexed:" in line:
            stats["files"] = int(line.split(":")[-1].strip())
        elif "Total chunks:" in line:
            stats["chunks"] = int(line.split(":")[-1].strip())

    # Get index size
    index_size = sum(f.stat().st_size for f in sia_dir.rglob("*") if f.is_file())
    stats["size_mb"] = index_size / (1024 * 1024)
    stats["index_time"] = index_time

    print(
        f"      Indexed: {stats['files']} files, {stats['chunks']} chunks, {stats['size_mb']:.1f} MB, {index_time:.1f}s"
    )

    return index_time, stats


def run_benchmark(repo_name: str, repo_path: Path, num_queries: int) -> dict:
    """Run benchmark on a repository."""
    print(f"    Running benchmark ({num_queries} queries)...")

    result_file = RESULTS_DIR / f"{repo_name}.json"

    result = subprocess.run(
        [
            sys.executable,
            str(PCI_DIR / "tests/benchmarks/run_repoeval_benchmark.py"),
            "--repo",
            repo_name,
            "--sample-size",
            str(num_queries),
            "--output",
            str(result_file),
        ],
        cwd=PCI_DIR,
        capture_output=True,
        text=True,
        timeout=num_queries * 30,  # 30s per query
    )

    # Load results
    if result_file.exists():
        with open(result_file) as f:
            return json.load(f)
    else:
        print("      WARNING: No results file generated")
        print(f"      stdout: {result.stdout[-200:]}")
        print(f"      stderr: {result.stderr[-200:]}")
        return {"error": "Benchmark failed"}


def aggregate_results(repo_results: list[dict]) -> dict:
    """Aggregate results across repositories."""
    total_queries = sum(r.get("total_queries", 0) for r in repo_results)
    processed = sum(r.get("queries_processed", 0) for r in repo_results)
    failed = sum(r.get("queries_failed", 0) for r in repo_results)

    # Weighted average by queries processed
    metrics = {}
    for metric in [
        "recall@1",
        "recall@5",
        "recall@10",
        "precision@1",
        "precision@5",
        "precision@10",
        "mrr",
    ]:
        total = 0
        for r in repo_results:
            if metric in r and r.get("queries_processed", 0) > 0:
                total += r[metric] * r["queries_processed"]
        metrics[metric] = total / processed if processed > 0 else 0

    return {
        "total_queries": total_queries,
        "queries_processed": processed,
        "queries_failed": failed,
        **metrics,
    }


def main():
    """Run full RepoEval benchmark."""
    print("=" * 80)
    print("Full RepoEval Benchmark - cAST Paper Setup")
    print("=" * 80)
    print(f"\nDataset: {DATASET_PATH}")
    print(f"Repositories: {len(REPOSITORIES)}")
    print(f"Total queries: {sum(r['queries'] for r in REPOSITORIES)}")
    print(f"Configurations: {len(CONFIGS)}")
    print(f"Results directory: {RESULTS_DIR}")
    print()

    # Create results directory
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Track overall results
    all_results = []

    # For each configuration
    for config_idx, config in enumerate(CONFIGS, 1):
        print(f"\n{'=' * 80}")
        print(f"Configuration {config_idx}/{len(CONFIGS)}: {config['name']}")
        print(f"  {config['description']}")
        print(f"{'=' * 80}\n")

        config_results = {
            "config": config,
            "repositories": [],
            "started_at": datetime.now().isoformat(),
        }

        # For each repository
        for repo_idx, repo in enumerate(REPOSITORIES, 1):
            print(f"  Repository {repo_idx}/{len(REPOSITORIES)}: {repo['name']}")

            repo_path = Path(repo["path"])
            if not repo_path.exists():
                print(f"    ERROR: Repository not found at {repo_path}")
                continue

            try:
                # Index repository
                index_time, index_stats = index_repository(repo_path, config)

                # Run benchmark
                benchmark_results = run_benchmark(repo["name"], repo_path, repo["queries"])

                # Store results
                repo_result = {
                    "name": repo["name"],
                    "queries": repo["queries"],
                    "index_stats": index_stats,
                    "benchmark": benchmark_results,
                }
                config_results["repositories"].append(repo_result)

                # Print results
                recall5 = benchmark_results.get("recall@5", 0) * 100
                precision5 = benchmark_results.get("precision@5", 0) * 100
                processed = benchmark_results.get("queries_processed", 0)
                failed = benchmark_results.get("queries_failed", 0)

                print(
                    f"    Results: Recall@5={recall5:.1f}%, Precision@5={precision5:.1f}%, Processed={processed}/{repo['queries']}, Failed={failed}"
                )
                print()

            except Exception as e:
                print(f"    ERROR: {e}")
                import traceback

                traceback.print_exc()
                continue

        # Aggregate results for this configuration
        config_results["completed_at"] = datetime.now().isoformat()
        config_results["aggregate"] = aggregate_results(config_results["repositories"])

        # Save configuration results
        config_file = RESULTS_DIR / f"{config['name']}_full.json"
        with open(config_file, "w") as f:
            json.dump(config_results, f, indent=2)

        print(f"\n{'=' * 80}")
        print(f"Configuration {config['name']} - Aggregate Results")
        print(f"{'=' * 80}")
        print(f"  Total queries: {config_results['aggregate']['total_queries']}")
        print(f"  Queries processed: {config_results['aggregate']['queries_processed']}")
        print(f"  Queries failed: {config_results['aggregate']['queries_failed']}")
        print(f"  Recall@1: {config_results['aggregate']['recall@1'] * 100:.1f}%")
        print(f"  Recall@5: {config_results['aggregate']['recall@5'] * 100:.1f}%")
        print(f"  Recall@10: {config_results['aggregate']['recall@10'] * 100:.1f}%")
        print(f"  Precision@5: {config_results['aggregate']['precision@5'] * 100:.1f}%")
        print(f"  MRR: {config_results['aggregate']['mrr']:.3f}")
        print(f"\nResults saved to: {config_file}")

        all_results.append(config_results)

    # Save combined results
    summary_file = RESULTS_DIR / "benchmark_summary.json"
    summary = {
        "benchmark": "RepoEval Full (cAST Paper Setup)",
        "dataset": str(DATASET_PATH),
        "total_repositories": len(REPOSITORIES),
        "total_queries": sum(r["queries"] for r in REPOSITORIES),
        "configurations": all_results,
        "completed_at": datetime.now().isoformat(),
    }

    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)

    # Print final comparison
    print(f"\n{'=' * 80}")
    print("FINAL RESULTS - All Configurations")
    print(f"{'=' * 80}\n")
    print(f"{'Configuration':<30} {'Recall@5':<12} {'Precision@5':<12} {'MRR':<8}")
    print("-" * 80)

    for result in all_results:
        name = result["config"]["name"]
        agg = result["aggregate"]
        print(
            f"{name:<30} {agg['recall@5'] * 100:<12.1f} {agg['precision@5'] * 100:<12.1f} {agg['mrr']:<8.3f}"
        )

    print(f"\n{'=' * 80}")
    print("Comparison with cAST Paper Results")
    print(f"{'=' * 80}\n")

    # Find best result
    best_config = max(all_results, key=lambda x: x["aggregate"]["recall@5"])
    best_recall5 = best_config["aggregate"]["recall@5"] * 100

    cast_recall5 = 77.0  # Average from cAST paper

    print(f"cAST (paper average):        {cast_recall5:.1f}%")
    print(f"Sia-code (best config):      {best_recall5:.1f}%")
    print(f"Difference:                  {best_recall5 - cast_recall5:+.1f} percentage points")
    print(f"Ratio:                       {best_recall5 / cast_recall5:.2f}x")

    print(f"\nFull results saved to: {summary_file}")
    print()


if __name__ == "__main__":
    main()
