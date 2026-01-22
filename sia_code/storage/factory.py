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
        backend_type: 'auto', 'usearch', or 'memvid'
        **kwargs: Backend-specific configuration

    Returns:
        StorageBackend instance

    Raises:
        ValueError: If backend_type is unknown
        FileNotFoundError: If auto-detection fails
    """
    # Auto-detect backend from existing files
    if backend_type == "auto":
        vector_path = path / "vectors.usearch"
        memvid_path = path / "index.mv2"

        if vector_path.exists():
            backend_type = "usearch"
        elif memvid_path.exists():
            backend_type = "memvid"
        else:
            # Default to usearch for new indexes
            backend_type = "usearch"

    # Create backend
    if backend_type == "usearch":
        from .usearch_backend import UsearchSqliteBackend

        return UsearchSqliteBackend(path, **kwargs)

    elif backend_type == "memvid":
        from .backend import MemvidBackend

        # Note: MemvidBackend expects .mv2 file path, not directory
        memvid_path = path / "index.mv2"
        return MemvidBackend(memvid_path, **kwargs)

    else:
        raise ValueError(f"Unknown backend type: {backend_type}")


def get_backend_type(path: Path) -> str:
    """Detect backend type from existing index.

    Args:
        path: Path to .sia-code directory

    Returns:
        'usearch', 'memvid', or 'none'
    """
    vector_path = path / "vectors.usearch"
    memvid_path = path / "index.mv2"

    if vector_path.exists():
        return "usearch"
    elif memvid_path.exists():
        return "memvid"
    else:
        return "none"
