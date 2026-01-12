"""Chunk metadata sidecar for tracking valid/stale chunks."""

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Set


logger = logging.getLogger(__name__)


@dataclass
class FileChunkMetadata:
    """Metadata for chunks associated with a file."""

    file_path: str
    hash: str
    mtime: float
    size: int
    valid_chunks: list[str] = field(default_factory=list)
    stale_chunks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "FileChunkMetadata":
        """Create from dictionary."""
        return cls(**data)

    def mark_chunks_stale(self):
        """Move all valid chunks to stale."""
        self.stale_chunks.extend(self.valid_chunks)
        self.valid_chunks = []

    def set_valid_chunks(self, chunk_ids: list[str]):
        """Set new valid chunks (replacing old ones)."""
        self.valid_chunks = chunk_ids


@dataclass
class StalenessSummary:
    """Summary of index staleness."""

    total_chunks: int
    valid_chunks: int
    stale_chunks: int
    staleness_ratio: float
    total_files: int
    files_with_stale: int

    @property
    def status(self) -> str:
        """Get health status based on staleness ratio."""
        if self.staleness_ratio < 0.1:
            return "🟢 Healthy"
        elif self.staleness_ratio < 0.2:
            return "🟡 Acceptable"
        elif self.staleness_ratio < 0.4:
            return "🟠 Degraded"
        else:
            return "🔴 Critical"

    @property
    def recommendation(self) -> str:
        """Get recommendation based on staleness."""
        if self.staleness_ratio < 0.1:
            return "None - index is healthy"
        elif self.staleness_ratio < 0.2:
            return "Monitor - consider compact if performance degrades"
        elif self.staleness_ratio < 0.4:
            return "Recommend running 'pci compact' to clean stale chunks"
        else:
            return "⚠️  Run 'pci compact' immediately - index is critical"


class ChunkIndex:
    """Manages chunk metadata sidecar for tracking valid/stale chunks.

    The sidecar maintains a mapping of files to their associated chunks,
    allowing us to track which chunks are valid (current) vs stale (outdated).
    This solves the chunk accumulation problem where Memvid can't delete chunks.
    """

    VERSION = "1.0"

    def __init__(self, index_path: Path):
        """Initialize chunk index.

        Args:
            index_path: Path to chunk index file (typically .pci/chunk_index.json)
        """
        self.index_path = index_path
        self.files: dict[str, FileChunkMetadata] = {}
        self.dirty = False
        self.load()

    def load(self):
        """Load chunk index from disk."""
        if self.index_path.exists():
            try:
                with open(self.index_path) as f:
                    data = json.load(f)

                    # Verify version
                    if data.get("version") != self.VERSION:
                        logger.warning(
                            f"Chunk index version mismatch: {data.get('version')} != {self.VERSION}"
                        )

                    # Load files
                    self.files = {
                        k: FileChunkMetadata.from_dict(v) for k, v in data.get("files", {}).items()
                    }

                logger.info(f"Loaded chunk index with {len(self.files)} files")
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.error(f"Corrupted chunk index, starting fresh: {e}")
                self.files = {}
                self.dirty = True
        else:
            # New chunk index - mark dirty so it gets created on save
            self.dirty = True
            logger.info("Creating new chunk index")

    def save(self):
        """Save chunk index to disk."""
        if not self.dirty:
            return

        self.index_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": self.VERSION,
            "files": {k: v.to_dict() for k, v in self.files.items()},
        }

        with open(self.index_path, "w") as f:
            json.dump(data, f, indent=2)

        self.dirty = False
        logger.debug(f"Saved chunk index with {len(self.files)} files")

    def update_file(
        self, file_path: Path, file_hash: str, mtime: float, size: int, chunk_ids: list[str]
    ):
        """Update or create file metadata with new chunks.

        Args:
            file_path: Path to file
            file_hash: SHA256 hash of file content
            mtime: File modification time
            size: File size in bytes
            chunk_ids: List of chunk IDs for this file
        """
        path_str = str(file_path.absolute())

        # If file exists, mark old chunks as stale
        if path_str in self.files:
            logger.debug(f"Marking old chunks stale for {file_path}")
            self.files[path_str].mark_chunks_stale()

        # Create or update metadata
        if path_str not in self.files:
            self.files[path_str] = FileChunkMetadata(
                file_path=path_str,
                hash=file_hash,
                mtime=mtime,
                size=size,
                valid_chunks=chunk_ids,
            )
        else:
            metadata = self.files[path_str]
            metadata.hash = file_hash
            metadata.mtime = mtime
            metadata.size = size
            metadata.set_valid_chunks(chunk_ids)

        self.dirty = True
        logger.debug(f"Updated chunk index for {file_path}: {len(chunk_ids)} chunks")

    def get_valid_chunks(self, file_path: Path | None = None) -> Set[str]:
        """Get set of all valid chunk IDs.

        Args:
            file_path: Optional - if provided, only get chunks for this file

        Returns:
            Set of valid chunk IDs
        """
        if file_path:
            path_str = str(file_path.absolute())
            if path_str in self.files:
                return set(self.files[path_str].valid_chunks)
            return set()

        # Get all valid chunks across all files
        valid = set()
        for metadata in self.files.values():
            valid.update(metadata.valid_chunks)
        return valid

    def get_stale_chunks(self) -> Set[str]:
        """Get set of all stale chunk IDs.

        Returns:
            Set of stale chunk IDs
        """
        stale = set()
        for metadata in self.files.values():
            stale.update(metadata.stale_chunks)
        return stale

    def remove_file(self, file_path: Path):
        """Remove file from index (marks all chunks as stale).

        Args:
            file_path: Path to file to remove
        """
        path_str = str(file_path.absolute())
        if path_str in self.files:
            # Mark all chunks as stale before removing
            self.files[path_str].mark_chunks_stale()
            del self.files[path_str]
            self.dirty = True
            logger.debug(f"Removed {file_path} from chunk index")

    def cleanup_deleted_files(self, valid_paths: Set[str]):
        """Remove entries for files that no longer exist.

        Args:
            valid_paths: Set of valid file paths (absolute strings)
        """
        removed = []
        for path_str in list(self.files.keys()):
            if path_str not in valid_paths:
                # Mark chunks as stale before removing
                self.files[path_str].mark_chunks_stale()
                del self.files[path_str]
                removed.append(path_str)
                self.dirty = True

        if removed:
            logger.info(f"Cleaned up {len(removed)} deleted files from chunk index")

    def get_staleness_summary(self) -> StalenessSummary:
        """Calculate staleness statistics.

        Returns:
            Summary of index staleness
        """
        valid_chunks = self.get_valid_chunks()
        stale_chunks = self.get_stale_chunks()
        total_chunks = len(valid_chunks) + len(stale_chunks)

        staleness_ratio = len(stale_chunks) / total_chunks if total_chunks > 0 else 0

        files_with_stale = sum(
            1 for metadata in self.files.values() if len(metadata.stale_chunks) > 0
        )

        return StalenessSummary(
            total_chunks=total_chunks,
            valid_chunks=len(valid_chunks),
            stale_chunks=len(stale_chunks),
            staleness_ratio=staleness_ratio,
            total_files=len(self.files),
            files_with_stale=files_with_stale,
        )

    def clear_stale_chunks(self):
        """Clear all stale chunks from metadata (after compaction).

        This should be called after successfully rebuilding the index
        with only valid chunks.
        """
        for metadata in self.files.values():
            metadata.stale_chunks = []
        self.dirty = True
        logger.info("Cleared all stale chunks from index")

    def validate(self) -> list[str]:
        """Validate chunk index integrity.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check for duplicate chunk IDs
        all_chunks: dict[str, list[str]] = {}
        for path_str, metadata in self.files.items():
            for chunk_id in metadata.valid_chunks + metadata.stale_chunks:
                if chunk_id not in all_chunks:
                    all_chunks[chunk_id] = []
                all_chunks[chunk_id].append(path_str)

        for chunk_id, files in all_chunks.items():
            if len(files) > 1:
                errors.append(f"Duplicate chunk ID {chunk_id} in files: {files}")

        # Check for invalid paths
        for path_str in self.files.keys():
            path = Path(path_str)
            if not path.is_absolute():
                errors.append(f"Non-absolute path in index: {path_str}")

        return errors
