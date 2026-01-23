"""Architectural analysis tasks for LLM evaluation.

This module provides task definitions for evaluating code retrieval quality
using LLM-as-judge methodology, inspired by ChunkHound's Kubernetes benchmarks.
"""

from .architectural_tasks import ArchitecturalTask, get_all_tasks

__all__ = ["ArchitecturalTask", "get_all_tasks"]
