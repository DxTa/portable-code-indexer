"""Simple dataset loader using existing sia-code test data.

Creates benchmark datasets from sia-code's existing semantic quality tests.
"""

from pathlib import Path
from typing import Dict, List
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from ..harness import BenchmarkDataset, Query


def create_simple_dataset(
    queries: List[Dict[str, any]], corpus: Dict[str, str], name: str = "custom"
) -> BenchmarkDataset:
    """Create a benchmark dataset from query/corpus dicts.

    Args:
        queries: List of dicts with keys: id, query_text, relevant_docs
        corpus: Dict mapping doc_id to content
        name: Dataset name

    Returns:
        BenchmarkDataset instance
    """
    query_objects = [
        Query(
            id=q["id"],
            query_text=q["query_text"],
            relevant_docs=set(q.get("relevant_docs", [])),
            metadata=q.get("metadata", {}),
        )
        for q in queries
    ]

    return BenchmarkDataset(name=name, queries=query_objects, corpus=corpus)


def load_sia_code_test_dataset(repo_name: str = "click") -> BenchmarkDataset:
    """Load ground-truth queries from sia-code's semantic quality tests.

    Args:
        repo_name: Repository name ("click" or "pqueue")

    Returns:
        BenchmarkDataset with ground-truth queries
    """
    if repo_name == "click":
        queries = [
            {
                "id": "click_q1",
                "query_text": "how to create a command line interface",
                "relevant_docs": ["decorators.py:command", "core.py:Command"],
                "metadata": {"expected_symbols": ["command", "Command", "decorator"]},
            },
            {
                "id": "click_q2",
                "query_text": "how to add options to a command",
                "relevant_docs": ["decorators.py:option", "core.py:Option"],
                "metadata": {"expected_symbols": ["option", "Option"]},
            },
            {
                "id": "click_q3",
                "query_text": "how to prompt for user input",
                "relevant_docs": ["termui.py:prompt", "decorators.py:prompt"],
                "metadata": {"expected_symbols": ["prompt", "Prompt"]},
            },
            {
                "id": "click_q4",
                "query_text": "handle command line arguments",
                "relevant_docs": ["core.py:argument", "decorators.py:argument"],
                "metadata": {"expected_symbols": ["argument", "Argument", "parameter"]},
            },
            {
                "id": "click_q5",
                "query_text": "automatic help generation",
                "relevant_docs": ["core.py:format_help", "formatting.py:help"],
                "metadata": {"expected_symbols": ["help", "format_help"]},
            },
        ]
    elif repo_name == "pqueue":
        queries = [
            {
                "id": "pqueue_q1",
                "query_text": "how to limit concurrency in async operations",
                "relevant_docs": ["queue.ts:PQueue", "queue.ts:concurrency"],
                "metadata": {"expected_symbols": ["PQueue", "concurrency"]},
            },
            {
                "id": "pqueue_q2",
                "query_text": "how to pause and resume a queue",
                "relevant_docs": ["queue.ts:pause", "queue.ts:start"],
                "metadata": {"expected_symbols": ["pause", "start"]},
            },
            {
                "id": "pqueue_q3",
                "query_text": "wait for queue to become empty",
                "relevant_docs": ["queue.ts:onEmpty", "queue.ts:empty"],
                "metadata": {"expected_symbols": ["onEmpty", "empty"]},
            },
            {
                "id": "pqueue_q4",
                "query_text": "rate limiting async operations",
                "relevant_docs": ["queue.ts:intervalCap", "queue.ts:interval"],
                "metadata": {"expected_symbols": ["intervalCap", "interval", "rate"]},
            },
        ]
    else:
        raise ValueError(f"Unknown repository: {repo_name}")

    return create_simple_dataset(queries, {}, name=f"sia-code-{repo_name}")
