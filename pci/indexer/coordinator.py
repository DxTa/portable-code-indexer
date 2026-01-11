"""Indexing coordinator - orchestrates parse → chunk → store."""

from pathlib import Path
import hashlib

import pathspec

from ..config import Config
from ..core.types import Language
from ..parser.chunker import CASTChunker, CASTConfig
from ..storage.backend import MemvidBackend
from .hash_cache import HashCache


class IndexingCoordinator:
    """Coordinates the indexing process."""

    def __init__(self, config: Config, backend: MemvidBackend):
        """Initialize coordinator.

        Args:
            config: PCI configuration
            backend: Storage backend
        """
        self.config = config
        self.backend = backend
        self.chunker = CASTChunker(
            CASTConfig(
                max_chunk_size=config.chunking.max_chunk_size,
                min_chunk_size=config.chunking.min_chunk_size,
                merge_threshold=config.chunking.merge_threshold,
                greedy_merge=config.chunking.greedy_merge,
            )
        )

    def index_directory(self, directory: Path) -> dict:
        """Index all files in a directory.

        Args:
            directory: Root directory to index

        Returns:
            Statistics dictionary
        """
        # Discover files
        files = self._discover_files(directory)

        stats = {
            "total_files": len(files),
            "indexed_files": 0,
            "total_chunks": 0,
            "errors": [],
        }

        # Process each file
        for file_path in files:
            try:
                language = Language.from_extension(file_path.suffix)

                if not self.chunker.engine.is_supported(language):
                    continue

                # Chunk the file
                chunks = self.chunker.chunk_file(file_path, language)

                if chunks:
                    # Store chunks
                    self.backend.store_chunks_batch(chunks)
                    stats["indexed_files"] += 1
                    stats["total_chunks"] += len(chunks)

            except Exception as e:
                stats["errors"].append(f"{file_path}: {str(e)}")

        return stats

    def _discover_files(self, directory: Path) -> list[Path]:
        """Discover source files to index.

        Args:
            directory: Root directory

        Returns:
            List of file paths to index
        """
        # Build gitignore-style spec
        spec = pathspec.PathSpec.from_lines(
            "gitwildmatch",
            self.config.indexing.exclude_patterns,
        )

        files = []
        for pattern in self.config.indexing.include_patterns:
            for file_path in directory.rglob(pattern if "*" in pattern else f"**/*{pattern}"):
                if file_path.is_file():
                    # Check exclusions
                    rel_path = file_path.relative_to(directory)
                    if not spec.match_file(str(rel_path)):
                        # Check file size
                        if (
                            file_path.stat().st_size
                            <= self.config.indexing.max_file_size_mb * 1024 * 1024
                        ):
                            files.append(file_path)

        return files

    def index_directory_incremental(self, directory: Path, cache: HashCache) -> dict:
        """Index only changed files using hash cache.

        Args:
            directory: Root directory to index
            cache: Hash cache for change detection

        Returns:
            Statistics dictionary
        """
        files = self._discover_files(directory)

        stats = {
            "total_files": len(files),
            "changed_files": 0,
            "skipped_files": 0,
            "indexed_files": 0,
            "total_chunks": 0,
            "errors": [],
        }

        for file_path in files:
            # Check if file changed
            if not cache.has_changed(file_path):
                stats["skipped_files"] += 1
                continue

            stats["changed_files"] += 1

            try:
                language = Language.from_extension(file_path.suffix)

                if not self.chunker.engine.is_supported(language):
                    continue

                # Get old chunk IDs for this file
                old_chunk_ids = cache.get_chunks(file_path)

                # Delete old chunks (placeholder - Memvid doesn't support direct delete)
                if old_chunk_ids:
                    # In production, would delete old chunks here
                    pass

                # Chunk the file
                chunks = self.chunker.chunk_file(file_path, language)

                if chunks:
                    # Store new chunks
                    chunk_ids = self.backend.store_chunks_batch(chunks)

                    # Update cache with new chunk IDs
                    cache.update(file_path, chunk_ids)

                    stats["indexed_files"] += 1
                    stats["total_chunks"] += len(chunks)

            except Exception as e:
                stats["errors"].append(f"{file_path}: {str(e)}")

        # Save updated cache
        cache.save()

        return stats

    def get_file_hash(self, file_path: Path) -> str:
        """Calculate file hash for change detection.

        Args:
            file_path: Path to file

        Returns:
            MD5 hash of file
        """
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
