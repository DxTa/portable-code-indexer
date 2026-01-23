"""RepoEval dataset loader for code retrieval benchmarking.

Based on the RepoCoder paper: https://github.com/microsoft/CodeT/tree/main/RepoCoder
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class RepoEvalQuery:
    """A single RepoEval query for code completion."""

    task_id: str
    repo_name: str
    file_path: str  # Relative path within repo
    line_no: int
    context_start_lineno: int
    prompt: str  # Code context before completion point
    ground_truth: str  # Expected code completion

    @property
    def full_file_path(self) -> str:
        """Get the full file path for matching."""
        return self.file_path

    @property
    def query_text(self) -> str:
        """Get the query text for retrieval (last 500 chars of prompt)."""
        # Use the end of the prompt as the query (most relevant context)
        return self.prompt[-500:] if len(self.prompt) > 500 else self.prompt


def load_repoeval(
    dataset_path: Path, repo_filter: Optional[str] = None, max_queries: Optional[int] = None
) -> list[RepoEvalQuery]:
    """Load RepoEval dataset from JSONL file.

    Args:
        dataset_path: Path to .jsonl file
        repo_filter: Only load queries for this repo (e.g., "huggingface_diffusers")
        max_queries: Maximum number of queries to load

    Returns:
        List of RepoEval queries
    """
    queries = []

    with open(dataset_path, "r") as f:
        for line in f:
            data = json.loads(line)
            metadata = data["metadata"]

            # Extract repo and file path
            fpath_tuple = metadata["fpath_tuple"]
            repo_name = fpath_tuple[0]
            file_path = "/".join(fpath_tuple[1:])  # Join remaining parts

            # Apply repo filter
            if repo_filter and repo_name != repo_filter:
                continue

            query = RepoEvalQuery(
                task_id=metadata["task_id"],
                repo_name=repo_name,
                file_path=file_path,
                line_no=metadata["line_no"],
                context_start_lineno=metadata["context_start_lineno"],
                prompt=data["prompt"],
                ground_truth=metadata["ground_truth"],
            )

            queries.append(query)

            if max_queries and len(queries) >= max_queries:
                break

    return queries


def get_ground_truth_files(query: RepoEvalQuery) -> list[str]:
    """Get ground truth file paths for a query.

    For RepoEval, the ground truth is the file containing the completion.

    Returns:
        List of ground truth file paths (usually 1 file)
    """
    return [query.file_path]


if __name__ == "__main__":
    # Test the loader
    dataset_path = Path(
        "/tmp/CodeT/RepoCoder/datasets/api_level_completion_2k_context_codex.test.jsonl"
    )

    if dataset_path.exists():
        # Load first 10 queries for huggingface_diffusers
        queries = load_repoeval(dataset_path, repo_filter="huggingface_diffusers", max_queries=10)

        print(f"Loaded {len(queries)} queries")
        print(f"\nExample query:")
        q = queries[0]
        print(f"  Task ID: {q.task_id}")
        print(f"  Repo: {q.repo_name}")
        print(f"  File: {q.file_path}")
        print(f"  Line: {q.line_no}")
        print(f"  Query text (first 200 chars): {q.query_text[:200]}...")
        print(f"  Ground truth: {q.ground_truth[:100]}...")
    else:
        print(f"Dataset not found at {dataset_path}")
        print("Please extract RepoEval dataset first")
