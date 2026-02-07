"""Indexing coordinator - orchestrates parse → chunk → store."""

from pathlib import Path
import logging
import time
import os
import shutil
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Callable

import pathspec

from ..config import Config
from ..core.types import Language
from ..parser.chunker import CASTChunker, CASTConfig
from ..storage.base import StorageBackend
from .hash_cache import HashCache
from .chunk_index import ChunkIndex
from .metrics import PerformanceMetrics

logger = logging.getLogger(__name__)


def _get_git_commit_context(directory: Path) -> dict[str, str]:
    try:
        commit_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=directory,
            check=True,
            capture_output=True,
            text=True,
        )
        time_result = subprocess.run(
            ["git", "show", "-s", "--format=%cI", "HEAD"],
            cwd=directory,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return {}

    commit_hash = commit_result.stdout.strip()
    commit_time = time_result.stdout.strip()
    if not commit_hash:
        return {}

    context = {"commit_hash": commit_hash}
    if commit_time:
        context["commit_time"] = commit_time
    return context


def _attach_git_context(chunks: list, context: dict[str, str]) -> list:
    if not context:
        return chunks
    return [chunk.with_metadata(context) for chunk in chunks]


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

    def __init__(self, config: Config, backend: StorageBackend):
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

    def _create_index_stats(self, total_files: int = 0) -> dict:
        """Create initial stats dictionary for indexing operations.

        Args:
            total_files: Total number of files discovered

        Returns:
            Dictionary with initial stats structure
        """
        return {
            "total_files": total_files,
            "indexed_files": 0,
            "skipped": {
                "unsupported_language": [],
                "empty_content": [],
                "parse_errors": [],
                "too_large": [],
            },
            "total_chunks": 0,
            "errors": [],
            "metrics": None,
        }

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

    def index_directory(
        self, directory: Path, progress_callback: Callable[[str, int, int, str], None] | None = None
    ) -> dict:
        """Index all files in a directory.

        Args:
            directory: Root directory to index
            progress_callback: Optional callback for progress updates

        Returns:
            Statistics dictionary
        """
        # Start performance tracking
        metrics = PerformanceMetrics()

        # Notify discovery phase
        if progress_callback:
            progress_callback("discovering", 0, 0, "Scanning directory...")

        # Discover files
        files = self._discover_files(directory)

        # Notify indexing phase start
        if progress_callback:
            progress_callback("indexing", 0, len(files), f"Found {len(files)} files")

        stats = self._create_index_stats(len(files))

        git_context = _get_git_commit_context(directory)

        # Buffer chunks to reduce write overhead
        pending_chunks: list = []
        batch_size = max(1, self.config.indexing.chunk_batch_size)
        if self.backend.embedding_enabled and hasattr(self.backend, "_get_embed_batch_size"):
            embed_batch = self.backend._get_embed_batch_size()
            batch_size = min(batch_size, max(1, embed_batch * 8))

        def flush_chunks() -> None:
            if pending_chunks:
                self.backend.store_chunks_batch(pending_chunks)
                pending_chunks.clear()

        # Process each file
        for idx, file_path in enumerate(files, 1):
            # Update progress
            if progress_callback:
                progress_callback("indexing", idx, len(files), file_path.name)

            try:
                language = Language.from_extension(file_path.suffix)

                if not self.chunker.engine.is_supported(language):
                    stats["skipped"]["unsupported_language"].append(str(file_path))
                    logger.debug(f"Skipping unsupported language: {file_path}")
                    continue

                # Chunk the file with retry
                chunks, error = self._index_file_with_retry(file_path, language)

                if error:
                    stats["skipped"]["parse_errors"].append((str(file_path), error))
                    stats["errors"].append(f"{file_path}: {error}")
                    metrics.errors_count += 1
                    continue

                if chunks:
                    # Track file size
                    try:
                        metrics.bytes_processed += file_path.stat().st_size
                    except OSError:
                        pass

                    # Buffer chunks and flush when threshold reached
                    pending_chunks.extend(_attach_git_context(chunks, git_context))
                    if len(pending_chunks) >= batch_size:
                        flush_chunks()
                    stats["indexed_files"] += 1
                    stats["total_chunks"] += len(chunks)
                    metrics.files_processed += 1
                    metrics.chunks_created += len(chunks)
                    logger.info(f"Indexed {file_path}: {len(chunks)} chunks")
                else:
                    # Empty content - no chunks produced
                    stats["skipped"]["empty_content"].append(str(file_path))

            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                stats["skipped"]["parse_errors"].append((str(file_path), error_msg))
                stats["errors"].append(f"{file_path}: {error_msg}")
                metrics.errors_count += 1
                logger.exception(f"Unexpected error indexing {file_path}")

        # Flush any remaining chunks
        try:
            flush_chunks()
        except Exception as e:
            error_msg = f"Error flushing final chunk batch: {str(e)}"
            stats["errors"].append(error_msg)
            metrics.errors_count += 1
            logger.exception("Error flushing final chunk batch")

        # Finalize metrics
        metrics.finish()
        stats["metrics"] = metrics.to_dict()
        logger.info(f"Indexing complete: {metrics}")

        # Final seal to compact WAL and reduce index size
        try:
            self.backend.seal()
            logger.info("Index sealed successfully")
        except Exception as e:
            logger.warning(f"Failed to seal index: {e}")

        return stats

    def index_directory_parallel(
        self,
        directory: Path,
        max_workers: int | None = None,
        progress_callback: Callable[[str, int, int, str], None] | None = None,
    ) -> dict:
        """Index all files in a directory using parallel processing.

        Args:
            directory: Root directory to index
            max_workers: Number of worker processes (default: CPU count)
            progress_callback: Optional callback for progress updates

        Returns:
            Statistics dictionary
        """
        # Start performance tracking
        metrics = PerformanceMetrics()

        # Notify discovery phase
        if progress_callback:
            progress_callback("discovering", 0, 0, "Scanning directory...")

        # Discover files
        files = self._discover_files(directory)

        # Notify indexing phase start
        if progress_callback:
            progress_callback("indexing", 0, len(files), f"Found {len(files)} files")

        stats = self._create_index_stats(len(files))

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

        # Buffer chunks to reduce write overhead
        pending_chunks: list = []
        batch_size = max(1, self.config.indexing.chunk_batch_size)
        if self.backend.embedding_enabled and hasattr(self.backend, "_get_embed_batch_size"):
            embed_batch = self.backend._get_embed_batch_size()
            batch_size = min(batch_size, max(1, embed_batch * 8))

        git_context = _get_git_commit_context(directory)

        def flush_chunks() -> None:
            if pending_chunks:
                self.backend.store_chunks_batch(pending_chunks)
                pending_chunks.clear()

        # Process files in parallel
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_file = {
                executor.submit(_chunk_file_worker, file_path, chunking_config): file_path
                for file_path in files
            }

            # Collect results as they complete
            completed_count = 0
            for future in as_completed(future_to_file):
                try:
                    file_path, chunks, error, file_size = future.result()
                    completed_count += 1

                    # Update progress
                    if progress_callback:
                        progress_callback("indexing", completed_count, len(files), file_path.name)

                    if error:
                        stats["skipped"]["parse_errors"].append((str(file_path), error))
                        stats["errors"].append(f"{file_path}: {error}")
                        metrics.errors_count += 1
                        continue

                    if chunks:
                        # Track metrics
                        metrics.bytes_processed += file_size

                        # Buffer chunks and flush when threshold reached
                        pending_chunks.extend(_attach_git_context(chunks, git_context))
                        if len(pending_chunks) >= batch_size:
                            flush_chunks()
                        stats["indexed_files"] += 1
                        stats["total_chunks"] += len(chunks)
                        metrics.files_processed += 1
                        metrics.chunks_created += len(chunks)
                        logger.info(f"Indexed {file_path}: {len(chunks)} chunks")
                    else:
                        # Empty content - no chunks produced (unsupported language or truly empty)
                        stats["skipped"]["empty_content"].append(str(file_path))

                except Exception as e:
                    file_path = future_to_file[future]
                    error_msg = f"Unexpected error: {str(e)}"
                    stats["skipped"]["parse_errors"].append((str(file_path), error_msg))
                    stats["errors"].append(f"{file_path}: {error_msg}")
                    metrics.errors_count += 1
                    logger.exception(f"Unexpected error processing {file_path}")

        # Flush any remaining chunks
        try:
            flush_chunks()
        except Exception as e:
            error_msg = f"Error flushing final chunk batch: {str(e)}"
            stats["errors"].append(error_msg)
            metrics.errors_count += 1
            logger.exception("Error flushing final chunk batch")

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
        # Build gitignore-style spec (includes .gitignore patterns)
        effective_patterns = self.config.indexing.get_effective_exclude_patterns(directory)
        spec = pathspec.PathSpec.from_lines(
            "gitwildmatch",
            effective_patterns,
        )

        files = []
        for pattern in self.config.indexing.include_patterns:
            for file_path in directory.rglob(pattern if "*" in pattern else f"**/*{pattern}"):
                if file_path.is_file():
                    # Check exclusions
                    rel_path = file_path.relative_to(directory)
                    if not spec.match_file(str(rel_path)):
                        # Check file size
                        file_size = file_path.stat().st_size
                        # Skip empty files (0 bytes)
                        if file_size == 0:
                            continue
                        if file_size <= self.config.indexing.max_file_size_mb * 1024 * 1024:
                            files.append(file_path)

        return files

    def index_directory_incremental_v2(
        self,
        directory: Path,
        cache: HashCache,
        chunk_index: ChunkIndex,
        progress_callback: Callable[[str, int, int, str], None] | None = None,
    ) -> dict:
        """Index only changed files using hash cache and chunk index (v2.0).

        Args:
            directory: Root directory to index
            cache: Hash cache for change detection
            chunk_index: Chunk index for tracking valid/stale chunks
            progress_callback: Optional callback for progress updates

        Returns:
            Statistics dictionary
        """
        # Start performance tracking
        metrics = PerformanceMetrics()

        # Notify discovery phase
        if progress_callback:
            progress_callback("discovering", 0, 0, "Scanning directory...")

        files = self._discover_files(directory)

        # Notify checking phase
        if progress_callback:
            progress_callback(
                "checking", 0, len(files), f"Checking {len(files)} files for changes..."
            )

        stats = self._create_index_stats(len(files))
        # Add incremental-specific fields
        stats["changed_files"] = 0
        stats["skipped_files"] = 0
        git_context = _get_git_commit_context(directory)

        for idx, file_path in enumerate(files, 1):
            # Update progress for checking phase
            if progress_callback:
                progress_callback("checking", idx, len(files), file_path.name)

            # Check if file changed
            if not cache.has_changed(file_path):
                stats["skipped_files"] += 1
                continue

            stats["changed_files"] += 1

            # Update progress for indexing phase
            if progress_callback:
                progress_callback("indexing", stats["changed_files"], len(files), file_path.name)

            try:
                language = Language.from_extension(file_path.suffix)

                if not self.chunker.engine.is_supported(language):
                    stats["skipped"]["unsupported_language"].append(str(file_path))
                    logger.debug(f"Skipping unsupported language: {file_path}")
                    continue

                # Chunk the file with retry
                chunks, error = self._index_file_with_retry(file_path, language)

                if error:
                    stats["skipped"]["parse_errors"].append((str(file_path), error))
                    stats["errors"].append(f"{file_path}: {error}")
                    metrics.errors_count += 1
                    continue

                if chunks:
                    # Track file size
                    file_stat = file_path.stat()
                    metrics.bytes_processed += file_stat.st_size

                    # Store new chunks
                    chunks = _attach_git_context(chunks, git_context)
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
                else:
                    # Empty content - no chunks produced
                    stats["skipped"]["empty_content"].append(str(file_path))

            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                stats["skipped"]["parse_errors"].append((str(file_path), error_msg))
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

        # Create new index directory path
        new_index_path = self.backend.path.parent / ".sia-code-new"
        old_index_path = self.backend.path

        # Create new backend for new index (with same embedding config)
        backend_cls = type(self.backend)
        new_backend = backend_cls(
            path=new_index_path,
            embedding_enabled=self.backend.embedding_enabled,
            embedding_model=self.backend.embedding_model,
            ndim=self.backend.ndim if hasattr(self.backend, "ndim") else 768,
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

        # Define backup path before try block
        backup_path = old_index_path.parent / "index-backup.db"

        try:
            # Backup old index
            if old_index_path.exists():
                old_index_path.rename(backup_path)

            # Move new index to primary location
            new_index_path.rename(old_index_path)

            # Delete backup after successful swap
            if backup_path.exists():
                shutil.rmtree(backup_path)

            logger.info("Index compaction complete - swapped to new index")

        except Exception as e:
            logger.error(f"Failed to swap index: {e}")
            # Rollback: restore backup if it exists
            if backup_path.exists():
                if old_index_path.exists():
                    shutil.rmtree(old_index_path)
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
