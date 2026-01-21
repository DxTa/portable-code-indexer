"""Ground-truth dataset for sia-code codebase retrieval evaluation.

This dataset provides queries with manually labeled relevant files for
objective Recall@k and Precision@k measurement, comparable to ChunkHound's
methodology.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class GroundTruthQuery:
    """A query with ground-truth relevant files.

    Attributes:
        query_id: Unique identifier
        query: Natural language query
        relevant_files: List of file paths that should be retrieved
        difficulty: Query difficulty (easy/medium/hard)
        category: Query category (lookup/trace/architecture/integration)
    """

    query_id: str
    query: str
    relevant_files: List[str]
    difficulty: str
    category: str


# Ground-truth dataset for sia-code codebase
# Each query has manually verified relevant files
GROUND_TRUTH_QUERIES = [
    # EASY: Simple symbol lookup
    GroundTruthQuery(
        query_id="gt-lookup-001",
        query="Find the MemvidBackend class implementation",
        relevant_files=[
            "sia_code/storage/backend.py",
        ],
        difficulty="easy",
        category="lookup",
    ),
    GroundTruthQuery(
        query_id="gt-lookup-002",
        query="Where is the Chunk dataclass defined?",
        relevant_files=[
            "sia_code/core/models.py",
        ],
        difficulty="easy",
        category="lookup",
    ),
    GroundTruthQuery(
        query_id="gt-lookup-003",
        query="Find the CLI entry point for sia-code",
        relevant_files=[
            "sia_code/cli/main.py",
        ],
        difficulty="easy",
        category="lookup",
    ),
    # MEDIUM: Multi-file tracing
    GroundTruthQuery(
        query_id="gt-trace-001",
        query="How does the 'research' command work from CLI to execution?",
        relevant_files=[
            "sia_code/cli/main.py",
            "sia_code/commands/research.py",
            "sia_code/search/multi_hop.py",
        ],
        difficulty="medium",
        category="trace",
    ),
    GroundTruthQuery(
        query_id="gt-trace-002",
        query="Trace the indexing pipeline from file discovery to storage",
        relevant_files=[
            "sia_code/commands/index.py",
            "sia_code/indexing/indexer.py",
            "sia_code/indexing/chunker.py",
            "sia_code/storage/backend.py",
        ],
        difficulty="medium",
        category="trace",
    ),
    GroundTruthQuery(
        query_id="gt-trace-003",
        query="How does semantic search work in sia-code?",
        relevant_files=[
            "sia_code/storage/backend.py",
            "sia_code/search/multi_hop.py",
        ],
        difficulty="medium",
        category="trace",
    ),
    # HARD: Architectural understanding
    GroundTruthQuery(
        query_id="gt-arch-001",
        query="What are all the components involved in multi-hop code research?",
        relevant_files=[
            "sia_code/search/multi_hop.py",
            "sia_code/indexing/entity_extractor.py",
            "sia_code/storage/backend.py",
            "sia_code/search/query_preprocessor.py",
        ],
        difficulty="hard",
        category="architecture",
    ),
    GroundTruthQuery(
        query_id="gt-arch-002",
        query="How does sia-code support multiple programming languages?",
        relevant_files=[
            "sia_code/language_support/tree_sitter_manager.py",
            "sia_code/indexing/chunker.py",
            "sia_code/core/types.py",
        ],
        difficulty="hard",
        category="architecture",
    ),
    GroundTruthQuery(
        query_id="gt-arch-003",
        query="What storage and search capabilities does the backend provide?",
        relevant_files=[
            "sia_code/storage/backend.py",
            "sia_code/storage/schema.py",
            "sia_code/core/models.py",
        ],
        difficulty="hard",
        category="architecture",
    ),
    # HARD: Integration/dependency analysis
    GroundTruthQuery(
        query_id="gt-integ-001",
        query="How do tree-sitter parsers integrate with the chunking system?",
        relevant_files=[
            "sia_code/language_support/tree_sitter_manager.py",
            "sia_code/indexing/chunker.py",
            "sia_code/indexing/entity_extractor.py",
        ],
        difficulty="hard",
        category="integration",
    ),
    GroundTruthQuery(
        query_id="gt-integ-002",
        query="What are the dependencies for entity extraction in multi-hop search?",
        relevant_files=[
            "sia_code/search/multi_hop.py",
            "sia_code/indexing/entity_extractor.py",
            "sia_code/storage/backend.py",
        ],
        difficulty="hard",
        category="integration",
    ),
    # Additional queries for better coverage
    GroundTruthQuery(
        query_id="gt-lookup-004",
        query="Where is the SearchResult model defined?",
        relevant_files=[
            "sia_code/core/models.py",
        ],
        difficulty="easy",
        category="lookup",
    ),
    GroundTruthQuery(
        query_id="gt-trace-004",
        query="How does the compact command clean up stale chunks?",
        relevant_files=[
            "sia_code/commands/compact.py",
            "sia_code/storage/backend.py",
        ],
        difficulty="medium",
        category="trace",
    ),
    GroundTruthQuery(
        query_id="gt-arch-004",
        query="What CLI commands are available and how are they registered?",
        relevant_files=[
            "sia_code/cli/main.py",
            "sia_code/commands/index.py",
            "sia_code/commands/research.py",
            "sia_code/commands/search.py",
            "sia_code/commands/compact.py",
        ],
        difficulty="hard",
        category="architecture",
    ),
    GroundTruthQuery(
        query_id="gt-integ-003",
        query="How does the file watcher integrate with incremental indexing?",
        relevant_files=[
            "sia_code/indexing/file_watcher.py",
            "sia_code/indexing/indexer.py",
            "sia_code/storage/backend.py",
        ],
        difficulty="hard",
        category="integration",
    ),
]


def get_ground_truth_queries(
    difficulty: str | None = None,
    category: str | None = None,
) -> List[GroundTruthQuery]:
    """Get ground-truth queries filtered by difficulty and/or category.

    Args:
        difficulty: Filter by difficulty (easy/medium/hard)
        category: Filter by category (lookup/trace/architecture/integration)

    Returns:
        List of matching ground-truth queries
    """
    queries = GROUND_TRUTH_QUERIES

    if difficulty:
        queries = [q for q in queries if q.difficulty == difficulty]

    if category:
        queries = [q for q in queries if q.category == category]

    return queries


def get_query_by_id(query_id: str) -> GroundTruthQuery | None:
    """Get a specific query by ID.

    Args:
        query_id: Query identifier

    Returns:
        GroundTruthQuery or None if not found
    """
    for query in GROUND_TRUTH_QUERIES:
        if query.query_id == query_id:
            return query
    return None


# Dataset statistics
def get_dataset_stats() -> dict:
    """Get statistics about the ground-truth dataset.

    Returns:
        Dictionary with dataset statistics
    """
    total = len(GROUND_TRUTH_QUERIES)

    by_difficulty = {
        "easy": len([q for q in GROUND_TRUTH_QUERIES if q.difficulty == "easy"]),
        "medium": len([q for q in GROUND_TRUTH_QUERIES if q.difficulty == "medium"]),
        "hard": len([q for q in GROUND_TRUTH_QUERIES if q.difficulty == "hard"]),
    }

    by_category = {
        "lookup": len([q for q in GROUND_TRUTH_QUERIES if q.category == "lookup"]),
        "trace": len([q for q in GROUND_TRUTH_QUERIES if q.category == "trace"]),
        "architecture": len([q for q in GROUND_TRUTH_QUERIES if q.category == "architecture"]),
        "integration": len([q for q in GROUND_TRUTH_QUERIES if q.category == "integration"]),
    }

    avg_relevant_files = sum(len(q.relevant_files) for q in GROUND_TRUTH_QUERIES) / total

    return {
        "total_queries": total,
        "by_difficulty": by_difficulty,
        "by_category": by_category,
        "avg_relevant_files_per_query": avg_relevant_files,
    }
