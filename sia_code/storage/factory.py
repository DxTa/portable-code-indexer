"""Factory for creating storage backends with auto-detection."""

from pathlib import Path
from typing import Any

from .base import StorageBackend


def create_backend(
    path: Path,
    backend_type: str = "auto",
    **kwargs: Any,
) -> StorageBackend:
    """Create storage backend with auto-detection.

    Args:
        path: Path to .sia-code directory
        backend_type: 'auto' or 'usearch' (both use usearch)
        **kwargs: Backend-specific configuration

    Returns:
        StorageBackend instance

    Raises:
        ValueError: If backend_type is unknown
    """
    # Auto-detect backend from existing files
    if backend_type == "auto":
        # Always use usearch backend
        backend_type = "usearch"

    # Create backend
    if backend_type == "usearch":
        from .usearch_backend import UsearchSqliteBackend

        return UsearchSqliteBackend(path, **kwargs)

    else:
        raise ValueError(f"Unknown backend type: {backend_type}. Only 'usearch' is supported.")


def get_backend_type(path: Path) -> str:
    """Detect backend type from existing index.

    Args:
        path: Path to .sia-code directory

    Returns:
        'usearch' or 'none'
    """
    vector_path = path / "vectors.usearch"

    if vector_path.exists():
        return "usearch"
    else:
        return "none"
