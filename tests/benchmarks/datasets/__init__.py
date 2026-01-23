"""Dataset loaders for benchmark evaluation.

Supports loading ground-truth datasets in standard formats:
- RepoEval: Code completion with long contexts
- SWE-bench: Software engineering task patches
- CrossCodeEval: Multi-language cross-file reasoning
- Custom JSON format
"""

from .simple_loader import create_simple_dataset, load_sia_code_test_dataset

__all__ = [
    "create_simple_dataset",
    "load_sia_code_test_dataset",
]
