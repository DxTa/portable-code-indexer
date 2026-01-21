"""Benchmark suite for sia-code retrieval quality.

Two-tier benchmarking approach:

1. Academic Metrics (Phase 1):
   - Recall@k, Precision@k, nDCG@k, MRR, Hit@k
   - Quantitative comparison with ChunkHound
   - Ground-truth dataset evaluation

2. LLM-as-Judge Evaluation (Phase 2):
   - Architectural analysis quality (ChunkHound K8s style)
   - Multi-judge consensus (GPT-4o, Claude Opus, Gemini Pro)
   - Comprehensive rubrics (file coverage, concept coverage, accuracy, completeness)
   - Side-by-side tool comparison

Enables production-grade evaluation of code search tools.
"""

from .metrics import (
    recall_at_k,
    precision_at_k,
    ndcg_at_k,
    mean_reciprocal_rank,
    hit_at_k,
)
from .harness import RetrievalBenchmark
from .llm_evaluation import (
    LLMJudge,
    create_judge,
    EvaluationResult,
    save_evaluation_results,
    load_evaluation_results,
)
from .tasks.architectural_tasks import (
    ArchitecturalTask,
    get_all_tasks,
    get_tasks_by_codebase,
    get_tasks_by_difficulty,
    get_tasks_by_type,
)
from .retrievers import (
    SiaCodeRetriever,
    GrepRetriever,
    ChunkHoundRetriever,
    create_retriever,
)

__all__ = [
    # Academic metrics
    "recall_at_k",
    "precision_at_k",
    "ndcg_at_k",
    "mean_reciprocal_rank",
    "hit_at_k",
    "RetrievalBenchmark",
    # LLM evaluation
    "LLMJudge",
    "create_judge",
    "EvaluationResult",
    "save_evaluation_results",
    "load_evaluation_results",
    # Tasks
    "ArchitecturalTask",
    "get_all_tasks",
    "get_tasks_by_codebase",
    "get_tasks_by_difficulty",
    "get_tasks_by_type",
    # Retrievers
    "SiaCodeRetriever",
    "GrepRetriever",
    "ChunkHoundRetriever",
    "create_retriever",
]
