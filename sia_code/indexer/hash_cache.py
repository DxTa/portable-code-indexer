"""File hash cache for incremental indexing."""

import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class FileHash:
    """File hash entry for change detection."""

    path: str
    hash: str
    mtime: float
    size: int
    chunks: list[str]  # ChunkIds stored for this file

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FileHash":
        """Create from dictionary."""
        return cls(**data)


class HashCache:
    """Manages file hash cache for incremental indexing.

    The cache stores file hashes and metadata to detect changes
    without re-indexing unchanged files.
    """

    def __init__(self, cache_path: Path):
        """Initialize hash cache.

        Args:
            cache_path: Path to cache file (typically .pci/cache/file_hashes.json)
        """
        self.cache_path = cache_path
        self.hashes: dict[str, FileHash] = {}
        self.dirty = False
        self.load()

    def load(self) -> None:
        """Load cache from disk."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path) as f:
                    data = json.load(f)
                    self.hashes = {k: FileHash.from_dict(v) for k, v in data.items()}
            except (json.JSONDecodeError, KeyError):
                # Corrupted cache, start fresh
                self.hashes = {}
                self.dirty = True

    def save(self) -> None:
        """Save cache to disk."""
        if not self.dirty:
            return

        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w") as f:
            json.dump({k: v.to_dict() for k, v in self.hashes.items()}, f, indent=2)
        self.dirty = False

    def compute_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file contents.

        Args:
            file_path: Path to file

        Returns:
            Hex digest of file hash
        """
        hasher = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                # Read in chunks to handle large files
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""

    def has_changed(self, file_path: Path) -> bool:
        """Check if file has changed since last index.

        Uses a two-stage check:
        1. Quick check: modification time and size
        2. Thorough check: SHA256 hash if mtime/size differ

        Args:
            file_path: Path to file to check

        Returns:
            True if file is new or has changed, False if unchanged
        """
        path_str = str(file_path.absolute())

        # New file - definitely changed
        if path_str not in self.hashes:
            return True

        cached = self.hashes[path_str]

        try:
            stat = file_path.stat()
            current_mtime = stat.st_mtime
            current_size = stat.st_size

            # Quick check: mtime and size
            if current_mtime == cached.mtime and current_size == cached.size:
                # Likely unchanged (mtime and size match)
                return False

            # Mtime or size changed - verify with hash
            current_hash = self.compute_hash(file_path)
            return current_hash != cached.hash

        except (OSError, FileNotFoundError):
            # File disappeared or inaccessible
            return True

    def update(self, file_path: Path, chunk_ids: list[str]) -> None:
        """Update cache entry for a file.

        Args:
            file_path: Path to file
            chunk_ids: List of chunk IDs stored for this file
        """
        try:
            path_str = str(file_path.absolute())
            stat = file_path.stat()

            self.hashes[path_str] = FileHash(
                path=path_str,
                hash=self.compute_hash(file_path),
                mtime=stat.st_mtime,
                size=stat.st_size,
                chunks=chunk_ids,
            )
            self.dirty = True

        except (OSError, FileNotFoundError):
            # Couldn't update, skip
            pass

    def get_chunks(self, file_path: Path) -> list[str]:
        """Get chunk IDs for a file.

        Args:
            file_path: Path to file

        Returns:
            List of chunk IDs, or empty list if not cached
        """
        path_str = str(file_path.absolute())
        if path_str in self.hashes:
            return self.hashes[path_str].chunks
        return []

    def remove(self, file_path: Path) -> None:
        """Remove file from cache.

        Args:
            file_path: Path to file to remove
        """
        path_str = str(file_path.absolute())
        if path_str in self.hashes:
            del self.hashes[path_str]
            self.dirty = True

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        total_chunks = sum(len(h.chunks) for h in self.hashes.values())
        return {
            "total_files": len(self.hashes),
            "total_chunks": total_chunks,
            "cache_size_bytes": self.cache_path.stat().st_size if self.cache_path.exists() else 0,
        }

    def clear(self) -> None:
        """Clear entire cache."""
        self.hashes = {}
        self.dirty = True
        if self.cache_path.exists():
            self.cache_path.unlink()
