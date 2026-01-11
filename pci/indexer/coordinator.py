"""Indexing coordinator - orchestrates parse → chunk → store."""

from pathlib import Path
import hashlib
import logging
import time
from typing import cast

import pathspec

from ..config import Config
from ..core.types import Language
from ..parser.chunker import CASTChunker, CASTConfig
from ..storage.backend import MemvidBackend
from .hash_cache import HashCache
from .chunk_index import ChunkIndex
from .metrics import PerformanceMetrics

logger = logging.getLogger(__name__)


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

    def _index_file_with_retry(
        self, file_path: Path, language: Language, max_retries: int = 3
    ) -> tuple[list, str | None]:
        """Index a single file with exponential backoff retry.

        Args:
            file_path: Path to file to index
            language: Programming language
            max_retries: Maximum retry attempts

        Returns:
            Tuple of (chunks, error_message)
        """
        for attempt in range(max_retries):
            try:
                chunks = self.chunker.chunk_file(file_path, language)
                return chunks, None
            except MemoryError as e:
                # Don't retry memory errors
                error_msg = f"Memory error (file too large): {e}"
                logger.error(f"{file_path}: {error_msg}")
                return [], error_msg
            except Exception as e:
                if attempt == max_retries - 1:
                    # Final attempt failed
                    error_msg = f"Failed after {max_retries} attempts: {e}"
                    logger.error(f"{file_path}: {error_msg}")
                    return [], error_msg

                # Exponential backoff
                wait_time = 2**attempt
                logger.warning(f"{file_path}: Retry {attempt + 1}/{max_retries} after {wait_time}s")
                time.sleep(wait_time)

        return [], f"Failed after {max_retries} retries"

    def index_directory(self, directory: Path) -> dict:
        """Index all files in a directory.

        Args:
            directory: Root directory to index

        Returns:
            Statistics dictionary
        """
        # Start performance tracking
        metrics = PerformanceMetrics()

        # Discover files
        files = self._discover_files(directory)

        stats = {
            "total_files": len(files),
            "indexed_files": 0,
            "total_chunks": 0,
            "errors": [],
            "metrics": None,  # Will be filled at end
        }

        # Process each file
        for file_path in files:
            try:
                language = Language.from_extension(file_path.suffix)

                if not self.chunker.engine.is_supported(language):
                    logger.debug(f"Skipping unsupported language: {file_path}")
                    continue

                # Chunk the file with retry
                chunks, error = self._index_file_with_retry(file_path, language)

                if error:
                    stats["errors"].append(f"{file_path}: {error}")
                    metrics.errors_count += 1
                    continue

                if chunks:
                    # Track file size
                    try:
                        metrics.bytes_processed += file_path.stat().st_size
                    except OSError:
                        pass

                    # Store chunks
                    self.backend.store_chunks_batch(chunks)
                    stats["indexed_files"] += 1
                    stats["total_chunks"] += len(chunks)
                    metrics.files_processed += 1
                    metrics.chunks_created += len(chunks)
                    logger.info(f"Indexed {file_path}: {len(chunks)} chunks")

            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                stats["errors"].append(f"{file_path}: {error_msg}")
                metrics.errors_count += 1
                logger.exception(f"Unexpected error indexing {file_path}")

        # Finalize metrics
        metrics.finish()
        stats["metrics"] = metrics.to_dict()
        logger.info(f"Indexing complete: {metrics}")

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

    def index_directory_incremental_v2(
        self, directory: Path, cache: HashCache, chunk_index: ChunkIndex
    ) -> dict:
        """Index only changed files using hash cache and chunk index (v2.0).

        Args:
            directory: Root directory to index
            cache: Hash cache for change detection
            chunk_index: Chunk index for tracking valid/stale chunks

        Returns:
            Statistics dictionary
        """
        # Start performance tracking
        metrics = PerformanceMetrics()

        files = self._discover_files(directory)

        stats = {
            "total_files": len(files),
            "changed_files": 0,
            "skipped_files": 0,
            "indexed_files": 0,
            "total_chunks": 0,
            "errors": [],
            "metrics": None,  # Will be filled at end
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
                    logger.debug(f"Skipping unsupported language: {file_path}")
                    continue

                # Chunk the file with retry
                chunks, error = self._index_file_with_retry(file_path, language)

                if error:
                    stats["errors"].append(f"{file_path}: {error}")
                    metrics.errors_count += 1
                    continue

                if chunks:
                    # Track file size
                    file_stat = file_path.stat()
                    metrics.bytes_processed += file_stat.st_size

                    # Store new chunks
                    chunk_ids = self.backend.store_chunks_batch(chunks)
                    chunk_id_strs = [str(cid) for cid in chunk_ids]

                    # Update hash cache
                    cache.update(file_path, chunk_id_strs)

                    # Update chunk index (marks old chunks stale, adds new as valid)
                    file_hash = cache.compute_hash(file_path)
                    chunk_index.update_file(
                        file_path,
                        file_hash,
                        file_stat.st_mtime,
                        file_stat.st_size,
                        chunk_id_strs,
                    )

                    stats["indexed_files"] += 1
                    stats["total_chunks"] += len(chunks)
                    metrics.files_processed += 1
                    metrics.chunks_created += len(chunks)
                    logger.info(f"Re-indexed {file_path}: {len(chunks)} chunks")

            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                stats["errors"].append(f"{file_path}: {error_msg}")
                metrics.errors_count += 1
                logger.exception(f"Unexpected error indexing {file_path}")

        # Cleanup deleted files from chunk index
        valid_paths = {str(f.absolute()) for f in files}
        chunk_index.cleanup_deleted_files(valid_paths)

        # Save updated caches
        cache.save()
        chunk_index.save()

        # Finalize metrics
        metrics.finish()
        stats["metrics"] = metrics.to_dict()
        logger.info(f"Incremental indexing complete: {metrics}")

        return stats

    def index_directory_incremental(self, directory: Path, cache: HashCache) -> dict:
        """Index only changed files using hash cache.

        Args:
            directory: Root directory to index
            cache: Hash cache for change detection

        Returns:
            Statistics dictionary
        """
        # Start performance tracking
        metrics = PerformanceMetrics()

        files = self._discover_files(directory)

        stats = {
            "total_files": len(files),
            "changed_files": 0,
            "skipped_files": 0,
            "indexed_files": 0,
            "total_chunks": 0,
            "errors": [],
            "metrics": None,  # Will be filled at end
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
                    logger.debug(f"Skipping unsupported language: {file_path}")
                    continue

                # Get old chunk IDs for this file
                old_chunk_ids = cache.get_chunks(file_path)

                # Delete old chunks (placeholder - Memvid doesn't support direct delete)
                if old_chunk_ids:
                    logger.debug(
                        f"Old chunks exist for {file_path} ({len(old_chunk_ids)}), "
                        "but cannot delete (Memvid limitation)"
                    )

                # Chunk the file with retry
                chunks, error = self._index_file_with_retry(file_path, language)

                if error:
                    stats["errors"].append(f"{file_path}: {error}")
                    metrics.errors_count += 1
                    continue

                if chunks:
                    # Track file size
                    try:
                        metrics.bytes_processed += file_path.stat().st_size
                    except OSError:
                        pass

                    # Store new chunks
                    chunk_ids = self.backend.store_chunks_batch(chunks)

                    # Update cache with new chunk IDs
                    cache.update(file_path, cast(list[str], chunk_ids))

                    stats["indexed_files"] += 1
                    stats["total_chunks"] += len(chunks)
                    metrics.files_processed += 1
                    metrics.chunks_created += len(chunks)
                    logger.info(f"Re-indexed {file_path}: {len(chunks)} chunks")

            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                stats["errors"].append(f"{file_path}: {error_msg}")
                metrics.errors_count += 1
                logger.exception(f"Unexpected error indexing {file_path}")

        # Save updated cache
        cache.save()

        # Finalize metrics
        metrics.finish()
        stats["metrics"] = metrics.to_dict()
        logger.info(f"Incremental indexing complete: {metrics}")

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
