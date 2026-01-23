"""Compare different embedding models and search strategies for sia-code.

This script benchmarks multiple configurations:
- Different embedding models (bge-small, MiniLM, lexical-only)
- Different hybrid weights (semantic vs lexical)
- Index size and search performance

Usage:
    python tests/benchmarks/compare_embeddings.py --repo huggingface_diffusers
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def run_command(cmd: list[str], cwd: Path, timeout: int = 300) -> tuple[int, str, str]:
    """Run command and return exit code, stdout, stderr."""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


def clean_index(repo_path: Path):
    """Remove existing .sia-code index."""
    sia_dir = repo_path / ".sia-code"
    if sia_dir.exists():
        import shutil

        shutil.rmtree(sia_dir)
        print(f"  Cleaned {sia_dir}")


def init_with_config(
    repo_path: Path,
    embedding_enabled: bool,
    embedding_model: str,
    embedding_dims: int,
    vector_weight: float = 0.7,
) -> float:
    """Initialize sia-code with specific configuration.

    Returns:
        Time taken to initialize (seconds)
    """
    start = time.time()

    # Run via Python to configure before init
    config_script = f"""
from pathlib import Path
from sia_code.config import Config
from sia_code.cli import create_backend

sia_dir = Path('.sia-code')
sia_dir.mkdir(parents=True, exist_ok=True)
(sia_dir / 'cache').mkdir(exist_ok=True)

config = Config()
config.embedding.enabled = {embedding_enabled}
config.embedding.model = '{embedding_model}'
config.embedding.dimensions = {embedding_dims}
config.search.vector_weight = {vector_weight}
config.save(sia_dir / 'config.json')

backend = create_backend(sia_dir, config)
backend.create_index()
backend.close()
"""

    result = subprocess.run(
        ["python", "-c", config_script],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Init failed: {result.stderr}")

    return time.time() - start


def update_vector_weight(repo_path: Path, vector_weight: float):
    """Update vector_weight in config without reinitializing."""
    config_script = f"""
from pathlib import Path
from sia_code.config import Config

sia_dir = Path('.sia-code')
config = Config.load(sia_dir / 'config.json')
config.search.vector_weight = {vector_weight}
config.save(sia_dir / 'config.json')
"""

    result = subprocess.run(
        ["python", "-c", config_script],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=10,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Config update failed: {result.stderr}")


def index_repository(repo_path: Path) -> tuple[float, dict]:
    """Index repository and return timing + stats.

    Returns:
        (indexing_time_seconds, stats_dict)
    """
    start = time.time()

    returncode, stdout, stderr = run_command(
        ["sia-code", "index", "."],
        cwd=repo_path,
        timeout=600,
    )

    indexing_time = time.time() - start

    # Parse stats from output
    stats = {
        "files_indexed": 0,
        "chunks": 0,
        "throughput": 0.0,
    }

    for line in stdout.split("\n"):
        if "Files indexed:" in line:
            stats["files_indexed"] = int(line.split(":")[-1].strip())
        elif "Total chunks:" in line:
            stats["chunks"] = int(line.split(":")[-1].strip())
        elif "Throughput:" in line:
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "chunks/s":
                    stats["throughput"] = float(parts[i - 1])

    return indexing_time, stats


def get_index_size(repo_path: Path) -> int:
    """Get .sia-code directory size in bytes."""
    sia_dir = repo_path / ".sia-code"
    if not sia_dir.exists():
        return 0

    total = 0
    for path in sia_dir.rglob("*"):
        if path.is_file():
            total += path.stat().st_size

    return total


def run_benchmark(
    repo_path: Path,
    sample_size: int,
    output_file: Path,
) -> dict:
    """Run RepoEval benchmark.

    Returns:
        Benchmark results dictionary
    """
    returncode, stdout, stderr = run_command(
        [
            "python",
            "tests/benchmarks/run_repoeval_benchmark.py",
            "--repo",
            "huggingface_diffusers",
            "--output",
            str(output_file),
            "--sample-size",
            str(sample_size),
        ],
        cwd=Path("/home/dxta/dev/portable-code-index/pci"),
        timeout=sample_size * 15,  # ~15s per query
    )

    # Load results
    if output_file.exists():
        with open(output_file) as f:
            return json.load(f)

    return {"error": "Benchmark failed", "stderr": stderr}


def compare_configurations(
    repo_path: Path,
    sample_size: int = 20,
    output_dir: Path = Path("results"),
):
    """Compare multiple embedding configurations.

    Configurations to test:
    1. lexical-only (no embeddings, FTS5 only)
    2. bge-small-en-v1.5 (384 dims, balanced)
    3. all-MiniLM-L6-v2 (384 dims, fast)
    4. bge-base-en-v1.5 (768 dims, larger)

    For each config, test hybrid weights: 0.0, 0.3, 0.5, 0.7, 1.0
    """
    output_dir.mkdir(exist_ok=True)

    configs = [
        {
            "name": "lexical_only",
            "embedding_enabled": False,
            "embedding_model": "BAAI/bge-small-en-v1.5",
            "embedding_dims": 384,
            "hybrid_weights": [0.0],  # Only lexical
        },
        {
            "name": "bge_small",
            "embedding_enabled": True,
            "embedding_model": "BAAI/bge-small-en-v1.5",
            "embedding_dims": 384,
            "hybrid_weights": [0.0, 0.3, 0.5, 0.7],
        },
        {
            "name": "minilm",
            "embedding_enabled": True,
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "embedding_dims": 384,
            "hybrid_weights": [0.0, 0.3, 0.5, 0.7],
        },
        {
            "name": "bge_base",
            "embedding_enabled": True,
            "embedding_model": "BAAI/bge-base-en-v1.5",
            "embedding_dims": 768,
            "hybrid_weights": [0.5, 0.7],  # Skip 0.0/0.3 to save time
        },
    ]

    all_results = []

    for config in configs:
        print(f"\n{'=' * 80}")
        print(f"Testing: {config['name']}")
        print(f"  Model: {config['embedding_model']}")
        print(f"  Enabled: {config['embedding_enabled']}")
        print(f"  Dimensions: {config['embedding_dims']}")
        print(f"{'=' * 80}\n")

        # Clean and initialize
        print("1. Cleaning index...")
        clean_index(repo_path)

        print("2. Initializing with config...")
        init_time = init_with_config(
            repo_path,
            config["embedding_enabled"],
            config["embedding_model"],
            config["embedding_dims"],
        )
        print(f"   Init time: {init_time:.2f}s")

        # Index
        print("3. Indexing repository...")
        index_time, index_stats = index_repository(repo_path)
        print(f"   Index time: {index_time:.2f}s")
        print(f"   Chunks: {index_stats['chunks']}")
        print(f"   Throughput: {index_stats['throughput']:.1f} chunks/s")

        # Get index size
        index_size = get_index_size(repo_path)
        print(f"   Index size: {index_size / (1024 * 1024):.1f} MB")

        # For each hybrid weight
        for weight in config["hybrid_weights"]:
            print(f"\n4. Benchmarking (vector_weight={weight})...")

            # Update vector_weight in config
            update_vector_weight(repo_path, weight)

            result_name = f"{config['name']}_w{int(weight * 10)}"
            result_file = output_dir / f"{result_name}.json"

            # Run benchmark
            benchmark_results = run_benchmark(repo_path, sample_size, result_file)

            # Add metadata
            benchmark_results.update(
                {
                    "config_name": config["name"],
                    "embedding_enabled": config["embedding_enabled"],
                    "embedding_model": config["embedding_model"],
                    "embedding_dims": config["embedding_dims"],
                    "vector_weight": weight,
                    "index_time_seconds": index_time,
                    "index_size_mb": index_size / (1024 * 1024),
                    "chunks": index_stats["chunks"],
                }
            )

            all_results.append(benchmark_results)

            # Print results
            print(f"   Recall@5: {benchmark_results.get('recall@5', 0) * 100:.1f}%")
            print(
                f"   Queries processed: {benchmark_results.get('queries_processed', 0)}/{sample_size}"
            )
            print(f"   Failures: {benchmark_results.get('queries_failed', 0)}")

    # Save combined results
    summary_file = output_dir / "embedding_comparison_summary.json"
    with open(summary_file, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}\n")
    print(f"{'Config':<20} {'Weight':<8} {'Size(MB)':<10} {'Recall@5':<10} {'Failures':<10}")
    print("-" * 80)

    for r in all_results:
        print(
            f"{r['config_name']:<20} "
            f"{r.get('vector_weight', 0):<8.1f} "
            f"{r['index_size_mb']:<10.1f} "
            f"{r.get('recall@5', 0) * 100:<10.1f} "
            f"{r.get('queries_failed', 0):<10}"
        )

    print(f"\nResults saved to: {summary_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compare embedding models for sia-code")
    parser.add_argument(
        "--repo",
        default="huggingface_diffusers",
        help="Repository name",
    )
    parser.add_argument(
        "--repo-path",
        type=Path,
        default=Path("/tmp/CodeT/RepoCoder/repositories/huggingface_diffusers"),
        help="Path to repository",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=20,
        help="Number of queries to benchmark (default: 20, use 50 for full)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="Output directory for results",
    )

    args = parser.parse_args()

    print("Sia-code Embedding Model Comparison")
    print(f"Repository: {args.repo}")
    print(f"Sample size: {args.sample_size} queries")
    print(f"Output dir: {args.output_dir}")
    print()

    compare_configurations(
        repo_path=args.repo_path,
        sample_size=args.sample_size,
        output_dir=args.output_dir,
    )
