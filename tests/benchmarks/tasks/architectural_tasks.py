"""Architectural analysis task definitions for LLM-evaluated benchmarks.

These tasks mirror ChunkHound's Kubernetes controller tracing approach:
- Complex code path tracing
- Cross-module dependency analysis
- Architectural understanding verification
"""

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class ArchitecturalTask:
    """Definition of an architectural analysis task for LLM evaluation.

    Attributes:
        task_id: Unique identifier for the task
        question: The architectural question to answer
        codebase: Target codebase name (e.g., 'kubernetes', 'sia-code')
        expected_files: Ground truth files that should be retrieved
        expected_concepts: Key concepts/components that should be found
        difficulty: Task difficulty level (easy/medium/hard/expert)
        task_type: Category of analysis (trace/dependency/architecture/integration)
    """

    task_id: str
    question: str
    codebase: str
    expected_files: List[str]
    expected_concepts: List[str]
    difficulty: str  # easy, medium, hard, expert
    task_type: str  # trace, dependency, architecture, integration

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "question": self.question,
            "codebase": self.codebase,
            "expected_files": self.expected_files,
            "expected_concepts": self.expected_concepts,
            "difficulty": self.difficulty,
            "task_type": self.task_type,
        }


# Sia-code architectural tasks (self-documenting)
SIA_CODE_TASKS = [
    ArchitecturalTask(
        task_id="sia-trace-001",
        question="Trace the complete flow from CLI command 'sia-code research' to the final LLM response generation. What are the key components involved?",
        codebase="sia-code",
        expected_files=[
            "sia_code/cli/main.py",
            "sia_code/commands/research.py",
            "sia_code/search/multi_hop.py",
            "sia_code/llm/prompt_builder.py",
            "sia_code/storage/backend.py",
        ],
        expected_concepts=[
            "CLI argument parsing",
            "Multi-hop search strategy",
            "Virtual graph construction",
            "Memvid backend interaction",
            "LLM prompt construction",
            "Response formatting",
        ],
        difficulty="medium",
        task_type="trace",
    ),
    ArchitecturalTask(
        task_id="sia-arch-001",
        question="How does sia-code implement the 'virtual graph' concept without persisting graph structures? What are the key design decisions?",
        codebase="sia-code",
        expected_files=[
            "sia_code/search/multi_hop.py",
            "sia_code/indexing/entity_extractor.py",
            "sia_code/storage/backend.py",
        ],
        expected_concepts=[
            "Query-time entity extraction",
            "Tree-sitter parsing",
            "Dynamic relationship inference",
            "Embedding-based retrieval",
            "Stateless graph traversal",
        ],
        difficulty="hard",
        task_type="architecture",
    ),
    ArchitecturalTask(
        task_id="sia-dep-001",
        question="What are all the dependencies required for the indexing pipeline, and how do they interact?",
        codebase="sia-code",
        expected_files=[
            "sia_code/indexing/indexer.py",
            "sia_code/indexing/chunker.py",
            "sia_code/indexing/entity_extractor.py",
            "sia_code/storage/backend.py",
            "sia_code/language_support/tree_sitter_manager.py",
        ],
        expected_concepts=[
            "Tree-sitter language parsers",
            "Memvid SDK (PyO3 bindings)",
            "Embedding model (OpenAI API)",
            "File watching/change detection",
            "Tantivy indexing (via memvid)",
        ],
        difficulty="medium",
        task_type="dependency",
    ),
    ArchitecturalTask(
        task_id="sia-integ-001",
        question="How does sia-code integrate with memvid's MV2 storage format? What operations are performed and what are the constraints?",
        codebase="sia-code",
        expected_files=[
            "sia_code/storage/backend.py",
            "sia_code/storage/schema.py",
            "sia_code/indexing/indexer.py",
        ],
        expected_concepts=[
            "MemvidBackend wrapper",
            "Smart Frames serialization",
            "Vector embedding storage",
            "BM25 text search",
            "HNSW vector search",
            "Single-writer constraint",
            "WAL-based persistence",
        ],
        difficulty="hard",
        task_type="integration",
    ),
    ArchitecturalTask(
        task_id="sia-trace-002",
        question="When a user runs 'sia-code index .', trace the complete execution from CLI to final index persistence. What optimizations are applied?",
        codebase="sia-code",
        expected_files=[
            "sia_code/cli/main.py",
            "sia_code/commands/index.py",
            "sia_code/indexing/indexer.py",
            "sia_code/indexing/chunker.py",
            "sia_code/indexing/entity_extractor.py",
            "sia_code/storage/backend.py",
        ],
        expected_concepts=[
            "Gitignore filtering",
            "Parallel file processing",
            "AST-based chunking",
            "Batch embedding",
            "Incremental index updates",
            "Progress tracking",
        ],
        difficulty="medium",
        task_type="trace",
    ),
]


# Flask architectural tasks (popular open-source comparison)
FLASK_TASKS = [
    ArchitecturalTask(
        task_id="flask-trace-001",
        question="Trace the request handling flow from URL routing to response generation in Flask. What middleware and hooks are involved?",
        codebase="flask",
        expected_files=[
            "src/flask/app.py",
            "src/flask/wrappers.py",
            "src/flask/ctx.py",
            "src/flask/helpers.py",
        ],
        expected_concepts=[
            "URL routing",
            "Request context",
            "Application context",
            "Before/after request hooks",
            "Response object creation",
            "WSGI interface",
        ],
        difficulty="medium",
        task_type="trace",
    ),
    ArchitecturalTask(
        task_id="flask-arch-001",
        question="How does Flask implement the application and request context system? Why are there two separate contexts?",
        codebase="flask",
        expected_files=[
            "src/flask/ctx.py",
            "src/flask/globals.py",
            "src/flask/app.py",
        ],
        expected_concepts=[
            "Thread-local storage",
            "Context stack",
            "Application context",
            "Request context",
            "Context preservation",
            "Teardown functions",
        ],
        difficulty="hard",
        task_type="architecture",
    ),
]


# FastAPI architectural tasks (async framework comparison)
FASTAPI_TASKS = [
    ArchitecturalTask(
        task_id="fastapi-trace-001",
        question="Trace how FastAPI handles dependency injection from route definition to endpoint execution. What is the resolution order?",
        codebase="fastapi",
        expected_files=[
            "fastapi/routing.py",
            "fastapi/dependencies/utils.py",
            "fastapi/dependencies/models.py",
        ],
        expected_concepts=[
            "Dependency graph construction",
            "Async dependency resolution",
            "Cache management",
            "Type annotation inspection",
            "Callable execution order",
        ],
        difficulty="hard",
        task_type="trace",
    ),
    ArchitecturalTask(
        task_id="fastapi-integ-001",
        question="How does FastAPI integrate with Pydantic for request validation? What happens when validation fails?",
        codebase="fastapi",
        expected_files=[
            "fastapi/routing.py",
            "fastapi/utils.py",
            "fastapi/exceptions.py",
        ],
        expected_concepts=[
            "Pydantic model parsing",
            "Validation error handling",
            "HTTP 422 responses",
            "Error detail formatting",
            "Type coercion",
        ],
        difficulty="medium",
        task_type="integration",
    ),
]


def get_all_tasks() -> List[ArchitecturalTask]:
    """Get all architectural tasks for benchmarking.

    Returns:
        List of all defined architectural tasks across all codebases.
    """
    return SIA_CODE_TASKS + FLASK_TASKS + FASTAPI_TASKS


def get_tasks_by_codebase(codebase: str) -> List[ArchitecturalTask]:
    """Get tasks for a specific codebase.

    Args:
        codebase: Name of the codebase (e.g., 'sia-code', 'flask', 'fastapi')

    Returns:
        List of tasks for the specified codebase.
    """
    return [task for task in get_all_tasks() if task.codebase == codebase]


def get_tasks_by_difficulty(difficulty: str) -> List[ArchitecturalTask]:
    """Get tasks by difficulty level.

    Args:
        difficulty: Difficulty level (easy/medium/hard/expert)

    Returns:
        List of tasks matching the difficulty level.
    """
    return [task for task in get_all_tasks() if task.difficulty == difficulty]


def get_tasks_by_type(task_type: str) -> List[ArchitecturalTask]:
    """Get tasks by type.

    Args:
        task_type: Type of task (trace/dependency/architecture/integration)

    Returns:
        List of tasks matching the type.
    """
    return [task for task in get_all_tasks() if task.task_type == task_type]
