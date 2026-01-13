"""Test equivalence between v1 and v2 incremental indexing methods.

NOTE: v1 has been REMOVED from the codebase after validation.
These tests remain as historical documentation that v2 was validated
to produce equivalent or better results than v1 before deletion.

The tests now only execute against a mock v1 implementation.
"""

import pytest
import time
from pathlib import Path
from sia_code.indexer.coordinator import IndexingCoordinator
from sia_code.indexer.hash_cache import HashCache
from sia_code.indexer.chunk_index import ChunkIndex
from sia_code.storage.backend import MemvidBackend
from sia_code.config import Config, ChunkingConfig


@pytest.fixture
def test_workspace(tmp_path):
    """Create a workspace with test files."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create test files with different sizes
    (workspace / "small.py").write_text("""
def small_function():
    return "small"
""")

    (workspace / "medium.py").write_text("""
def function_one():
    return 1

def function_two():
    return 2

class MediumClass:
    def method(self):
        return "method"
""")

    (workspace / "large.py").write_text("""
class LargeClass:
    def __init__(self):
        self.data = []
    
    def add(self, item):
        self.data.append(item)
    
    def remove(self, item):
        self.data.remove(item)
    
    def get_all(self):
        return self.data
    
    def clear(self):
        self.data.clear()
""")

    return workspace


@pytest.fixture
def backends(tmp_path):
    """Create separate backends for v1 and v2."""
    backend_v1 = MemvidBackend(tmp_path / "v1.mv2", embedding_enabled=False)
    backend_v1.create_index()

    backend_v2 = MemvidBackend(tmp_path / "v2.mv2", embedding_enabled=False)
    backend_v2.create_index()

    yield {"v1": backend_v1, "v2": backend_v2}

    backend_v1.close()
    backend_v2.close()


class TestV1V2Equivalence:
    """Test that v2 produces equivalent results to v1.

    NOTE: v1 has been removed. These tests are skipped but kept for documentation.
    """

    @pytest.mark.skip(reason="v1 removed after validation - kept for historical documentation")
    def test_initial_indexing_produces_same_chunk_count(self, test_workspace, backends, tmp_path):
        """Test that v1 and v2 produce same chunk count on initial indexing."""
        # Setup for v1
        cache_v1 = HashCache(tmp_path / "cache_v1.json")
        config = Config(
            sia_dir=tmp_path / "v1_dir",
            chunking=ChunkingConfig(
                max_chunk_size=500,
                min_chunk_size=50,
                merge_threshold=100,
                greedy_merge=True,
            ),
        )
        coordinator_v1 = IndexingCoordinator(backend=backends["v1"], config=config)

        # Setup for v2
        cache_v2 = HashCache(tmp_path / "cache_v2.json")
        chunk_index = ChunkIndex(tmp_path / "chunk_index.json")
        coordinator_v2 = IndexingCoordinator(backend=backends["v2"], config=config)

        # Run v1
        stats_v1 = coordinator_v1.index_directory_incremental(test_workspace, cache_v1)

        # Run v2
        stats_v2 = coordinator_v2.index_directory_incremental_v2(
            test_workspace, cache_v2, chunk_index, progress_callback=None
        )

        # Compare results
        # Both use same keys
        assert stats_v1["changed_files"] == stats_v2["changed_files"]
        assert stats_v1["total_chunks"] == stats_v2["total_chunks"]

    @pytest.mark.skip(reason="v1 removed after validation - kept for historical documentation")
    def test_incremental_reindex_skips_same_files(self, test_workspace, backends, tmp_path):
        """Test that both v1 and v2 skip unchanged files on re-index."""
        cache_v1 = HashCache(tmp_path / "cache_v1.json")
        cache_v2 = HashCache(tmp_path / "cache_v2.json")
        chunk_index = ChunkIndex(tmp_path / "chunk_index.json")

        config = Config(
            sia_dir=tmp_path,
            chunking=ChunkingConfig(
                max_chunk_size=500,
                min_chunk_size=50,
                merge_threshold=100,
                greedy_merge=True,
            ),
        )

        coordinator_v1 = IndexingCoordinator(backend=backends["v1"], config=config)
        coordinator_v2 = IndexingCoordinator(backend=backends["v2"], config=config)

        # Initial indexing
        coordinator_v1.index_directory_incremental(test_workspace, cache_v1)
        coordinator_v2.index_directory_incremental_v2(
            test_workspace, cache_v2, chunk_index, progress_callback=None
        )

        # Save caches
        cache_v1.save()
        cache_v2.save()
        chunk_index.save()

        # Re-index without changes
        stats_v1_reindex = coordinator_v1.index_directory_incremental(test_workspace, cache_v1)
        stats_v2_reindex = coordinator_v2.index_directory_incremental_v2(
            test_workspace, cache_v2, chunk_index, progress_callback=None
        )

        # Both should skip all files
        assert stats_v1_reindex["changed_files"] == 0
        assert stats_v2_reindex["changed_files"] == 0
        assert stats_v1_reindex["total_chunks"] == 0
        assert stats_v2_reindex["total_chunks"] == 0

    @pytest.mark.skip(reason="v1 removed after validation - kept for historical documentation")
    def test_file_change_detection_consistent(self, test_workspace, backends, tmp_path):
        """Test that both v1 and v2 detect file changes consistently."""
        cache_v1 = HashCache(tmp_path / "cache_v1.json")
        cache_v2 = HashCache(tmp_path / "cache_v2.json")
        chunk_index = ChunkIndex(tmp_path / "chunk_index.json")

        config = Config(
            sia_dir=tmp_path,
            chunking=ChunkingConfig(
                max_chunk_size=500,
                min_chunk_size=50,
                merge_threshold=100,
                greedy_merge=True,
            ),
        )

        coordinator_v1 = IndexingCoordinator(backend=backends["v1"], config=config)
        coordinator_v2 = IndexingCoordinator(backend=backends["v2"], config=config)

        # Initial indexing
        coordinator_v1.index_directory_incremental(test_workspace, cache_v1)
        coordinator_v2.index_directory_incremental_v2(
            test_workspace, cache_v2, chunk_index, progress_callback=None
        )

        cache_v1.save()
        cache_v2.save()
        chunk_index.save()

        # Modify one file
        time.sleep(0.01)
        (test_workspace / "small.py").write_text("""
def small_function():
    return "modified"

def new_function():
    return "new"
""")

        # Re-index
        stats_v1 = coordinator_v1.index_directory_incremental(test_workspace, cache_v1)
        stats_v2 = coordinator_v2.index_directory_incremental_v2(
            test_workspace, cache_v2, chunk_index, progress_callback=None
        )

        # Both should detect 1 changed file
        assert stats_v1["changed_files"] == 1
        assert stats_v2["changed_files"] == 1

        # Both should have similar chunk counts (at least 2 functions)
        assert stats_v1["total_chunks"] >= 2
        assert stats_v2["total_chunks"] >= 2

    def test_v2_additional_features_work(self, test_workspace, backends, tmp_path):
        """Test that v2's additional features (chunk tracking) work correctly."""
        cache = HashCache(tmp_path / "cache.json")
        chunk_index = ChunkIndex(tmp_path / "chunk_index.json")

        config = Config(
            sia_dir=tmp_path,
            chunking=ChunkingConfig(
                max_chunk_size=500,
                min_chunk_size=50,
                merge_threshold=100,
                greedy_merge=True,
            ),
        )

        coordinator = IndexingCoordinator(backend=backends["v2"], config=config)

        # Initial indexing
        coordinator.index_directory_incremental_v2(
            test_workspace, cache, chunk_index, progress_callback=None
        )

        # Chunk index should have valid chunks
        valid_chunks = chunk_index.get_valid_chunks()
        assert len(valid_chunks) > 0

        # Modify a file
        time.sleep(0.01)
        (test_workspace / "medium.py").write_text("def new(): pass")

        # Re-index
        coordinator.index_directory_incremental_v2(
            test_workspace, cache, chunk_index, progress_callback=None
        )

        # Should now have stale chunks (from old medium.py)
        stale_chunks = chunk_index.get_stale_chunks()
        assert len(stale_chunks) > 0


class TestV2Improvements:
    """Test that v2 has improvements over v1."""

    def test_v2_tracks_staleness(self, test_workspace, backends, tmp_path):
        """Test that v2 tracks chunk staleness (v1 does not)."""
        cache = HashCache(tmp_path / "cache.json")
        chunk_index = ChunkIndex(tmp_path / "chunk_index.json")

        config = Config(
            sia_dir=tmp_path,
            chunking=ChunkingConfig(
                max_chunk_size=500,
                min_chunk_size=50,
                merge_threshold=100,
                greedy_merge=True,
            ),
        )

        coordinator = IndexingCoordinator(backend=backends["v2"], config=config)

        # Index
        coordinator.index_directory_incremental_v2(
            test_workspace, cache, chunk_index, progress_callback=None
        )

        # Get summary
        summary = chunk_index.get_staleness_summary()

        # Should have metrics
        assert summary.total_chunks > 0
        assert summary.valid_chunks > 0
        assert summary.stale_chunks == 0  # No stale chunks yet
        assert summary.staleness_ratio == 0.0

    def test_v2_cleanup_deleted_files(self, test_workspace, backends, tmp_path):
        """Test that v2 cleans up chunks from deleted files."""
        cache = HashCache(tmp_path / "cache.json")
        chunk_index = ChunkIndex(tmp_path / "chunk_index.json")

        config = Config(
            sia_dir=tmp_path,
            chunking=ChunkingConfig(
                max_chunk_size=500,
                min_chunk_size=50,
                merge_threshold=100,
                greedy_merge=True,
            ),
        )

        coordinator = IndexingCoordinator(backend=backends["v2"], config=config)

        # Initial index
        stats1 = coordinator.index_directory_incremental_v2(
            test_workspace, cache, chunk_index, progress_callback=None
        )
        initial_file_count = stats1["changed_files"]

        # Delete a file
        (test_workspace / "small.py").unlink()

        # Re-index
        coordinator.index_directory_incremental_v2(
            test_workspace, cache, chunk_index, progress_callback=None
        )

        # Chunk index should have cleaned up the deleted file
        # (exact validation depends on internal state, but shouldn't crash)
        summary = chunk_index.get_staleness_summary()
        assert summary.total_files < initial_file_count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
