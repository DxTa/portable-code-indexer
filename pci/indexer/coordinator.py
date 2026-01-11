"""Indexing coordinator - orchestrates parse → chunk → store."""

from pathlib import Path
import hashlib
import logging
import time
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
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


def _chunk_file_worker(
    file_path: Path, chunking_config: CASTConfig
) -> tuple[Path, list, str | None, int]:
    """Worker function for parallel file chunking.

    This runs in a separate process, so it must be a module-level function.

    Args:
        file_path: Path to file to chunk
        chunking_config: Chunking configuration

    Returns:
        Tuple of (file_path, chunks, error, file_size)
    """
    try:
        from ..core.types import Language
        from ..parser.chunker import CASTChunker

        language = Language.from_extension(file_path.suffix)
        chunker = CASTChunker(chunking_config)

        if not chunker.engine.is_supported(language):
            return file_path, [], None, 0

        chunks = chunker.chunk_file(file_path, language)
        file_size = file_path.stat().st_size if file_path.exists() else 0

        return file_path, chunks, None, file_size

    except Exception as e:
        return file_path, [], str(e), 0


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

    def index_directory_parallel(self, directory: Path, max_workers: int | None = None) -> dict:
        """Index all files in a directory using parallel processing.

        Args:
            directory: Root directory to index
            max_workers: Number of worker processes (default: CPU count)

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
            "metrics": None,
        }

        # Default to CPU count
        if max_workers is None:
            max_workers = os.cpu_count() or 4

        logger.info(f"Starting parallel indexing with {max_workers} workers")

        # Get chunking config for workers
        chunking_config = CASTConfig(
            max_chunk_size=self.config.chunking.max_chunk_size,
            min_chunk_size=self.config.chunking.min_chunk_size,
            merge_threshold=self.config.chunking.merge_threshold,
            greedy_merge=self.config.chunking.greedy_merge,
        )

        # Process files in parallel
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(_chunk_file_worker, file_path, chunking_config): file_path
                for file_path in files
            }

            # Collect results as they complete
            for future in as_completed(future_to_file):
                try:
                    file_path, chunks, error, file_size = future.result()

                    if error:
                        stats["errors"].append(f"{file_path}: {error}")
                        metrics.errors_count += 1
                        continue

                    if chunks:
                        # Track metrics
                        metrics.bytes_processed += file_size

                        # Store chunks
                        self.backend.store_chunks_batch(chunks)
                        stats["indexed_files"] += 1
                        stats["total_chunks"] += len(chunks)
                        metrics.files_processed += 1
                        metrics.chunks_created += len(chunks)
                        logger.info(f"Indexed {file_path}: {len(chunks)} chunks")

                except Exception as e:
                    file_path = future_to_file[future]
                    error_msg = f"Unexpected error: {str(e)}"
                    stats["errors"].append(f"{file_path}: {error_msg}")
                    metrics.errors_count += 1
                    logger.exception(f"Unexpected error processing {file_path}")

        # Finalize metrics
        metrics.finish()
        stats["metrics"] = metrics.to_dict()
        logger.info(f"Parallel indexing complete: {metrics}")

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

    def compact_index(
        self, directory: Path, chunk_index: ChunkIndex, threshold: float = 0.2
    ) -> dict:
        """Compact index by rebuilding with only valid chunks.

        This removes all stale chunks from the index, reducing size and
        improving search quality.

        Args:
            directory: Root directory containing source files
            chunk_index: Chunk index tracking valid/stale chunks
            threshold: Minimum staleness ratio to trigger compaction

        Returns:
            Statistics dictionary
        """
        # Check if compaction is needed
        summary = chunk_index.get_staleness_summary()

        logger.info(
            f"Staleness check: {summary.stale_chunks}/{summary.total_chunks} "
            f"({summary.staleness_ratio:.1%}) stale"
        )

        if summary.staleness_ratio < threshold:
            return {
                "compaction_needed": False,
                "staleness_ratio": summary.staleness_ratio,
                "threshold": threshold,
                "message": f"Index is healthy ({summary.staleness_ratio:.1%} stale, threshold {threshold:.1%})",
            }

        logger.info(f"Compaction needed: {summary.staleness_ratio:.1%} > {threshold:.1%} threshold")

        # Start performance tracking
        metrics = PerformanceMetrics()

        # Get valid chunk IDs
        valid_chunks = chunk_index.get_valid_chunks()
        stale_chunks = chunk_index.get_stale_chunks()

        logger.info(f"Rebuilding index with {len(valid_chunks)} valid chunks...")
        logger.info(f"Removing {len(stale_chunks)} stale chunks...")

        # Create new index file path
        new_index_path = self.backend.path.parent / "index-new.mv2"
        old_index_path = self.backend.path

        # Create new backend for new index (with same embedding config)
        from ..storage.backend import MemvidBackend

        new_backend = MemvidBackend(
            path=new_index_path,
            embedding_enabled=self.backend.embedding_enabled,
            embedding_model=self.backend.embedding_model,
            api_key_env=self.backend.api_key_env,
        )
        new_backend.create_index()

        stats = {
            "compaction_needed": True,
            "staleness_ratio": summary.staleness_ratio,
            "threshold": threshold,
            "valid_chunks": len(valid_chunks),
            "stale_chunks": len(stale_chunks),
            "files_reindexed": 0,
            "chunks_stored": 0,
            "errors": [],
            "metrics": None,
        }

        # Re-index all files to rebuild index with only valid chunks
        files = self._discover_files(directory)

        for file_path in files:
            try:
                language = Language.from_extension(file_path.suffix)

                if not self.chunker.engine.is_supported(language):
                    continue

                # Chunk the file
                chunks, error = self._index_file_with_retry(file_path, language)

                if error:
                    stats["errors"].append(f"{file_path}: {error}")
                    continue

                if chunks:
                    # Store chunks in new index
                    new_backend.store_chunks_batch(chunks)
                    stats["files_reindexed"] += 1
                    stats["chunks_stored"] += len(chunks)
                    metrics.files_processed += 1
                    metrics.chunks_created += len(chunks)

                    try:
                        metrics.bytes_processed += file_path.stat().st_size
                    except OSError:
                        pass

            except Exception as e:
                error_msg = f"Error during compaction: {str(e)}"
                stats["errors"].append(f"{file_path}: {error_msg}")
                logger.exception(f"Compaction error for {file_path}")

        # Atomic swap: rename new index to replace old
        logger.info("Performing atomic index swap...")

        try:
            # Backup old index
            backup_path = old_index_path.parent / "index-backup.mv2"
            if old_index_path.exists():
                old_index_path.rename(backup_path)

            # Move new index to primary location
            new_index_path.rename(old_index_path)

            # Delete backup after successful swap
            if backup_path.exists():
                backup_path.unlink()

            logger.info("Index compaction complete - swapped to new index")

        except Exception as e:
            logger.error(f"Failed to swap index: {e}")
            # Rollback: restore backup if it exists
            if backup_path.exists():
                backup_path.rename(old_index_path)
            stats["errors"].append(f"Index swap failed: {e}")
            raise

        # Clear stale chunks from chunk index
        chunk_index.clear_stale_chunks()
        chunk_index.save()

        # Finalize metrics
        metrics.finish()
        stats["metrics"] = metrics.to_dict()
        logger.info(f"Compaction complete: {metrics}")

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
