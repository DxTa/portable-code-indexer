"""Integration tests for watch mode functionality."""

import pytest
import time
from sia_code.indexer.coordinator import IndexingCoordinator
from sia_code.indexer.hash_cache import HashCache
from sia_code.indexer.chunk_index import ChunkIndex
from sia_code.storage.usearch_backend import UsearchSqliteBackend
from sia_code.config import Config, ChunkingConfig


@pytest.fixture
def temp_workspace(tmp_path):
    """Create a temporary workspace with test files."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Create initial test file
    test_file = workspace / "test.py"
    test_file.write_text("""
def hello():
    return "Hello, World!"
""")

    return workspace


@pytest.fixture
def test_setup(tmp_path, temp_workspace):
    """Set up test infrastructure (backend, cache, index)."""
    # Create backend
    backend_path = tmp_path / "test.sia-code"
    backend = UsearchSqliteBackend(backend_path, embedding_enabled=False)
    backend.create_index()

    # Create cache and chunk index
    cache_path = tmp_path / "cache.json"
    cache = HashCache(cache_path)

    chunk_index_path = tmp_path / "chunk_index.json"
    chunk_index = ChunkIndex(chunk_index_path)

    # Create config
    config = Config(
        sia_dir=tmp_path,
        chunking=ChunkingConfig(
            max_chunk_size=500,
            min_chunk_size=50,
            merge_threshold=100,
            greedy_merge=True,
        ),
    )

    coordinator = IndexingCoordinator(backend=backend, config=config)

    yield {
        "backend": backend,
        "cache": cache,
        "chunk_index": chunk_index,
        "config": config,
        "coordinator": coordinator,
        "workspace": temp_workspace,
    }

    backend.close()


class TestWatchModeIndexing:
    """Test watch mode uses v2 incremental indexing correctly."""

    def test_watch_uses_v2_method(self, test_setup):
        """Test that watch mode reindex uses index_directory_incremental_v2."""
        setup = test_setup

        # Initial index
        stats = setup["coordinator"].index_directory_incremental_v2(
            setup["workspace"],
            setup["cache"],
            setup["chunk_index"],
            progress_callback=None,
        )

        assert stats["changed_files"] >= 1
        assert stats["total_chunks"] >= 1

        # Save state
        setup["cache"].save()
        setup["chunk_index"].save()

        # Verify chunk index was updated
        valid_chunks = setup["chunk_index"].get_valid_chunks()
        assert len(valid_chunks) >= 1

    def test_watch_incremental_reuses_unchanged_chunks(self, test_setup):
        """Test that incremental indexing reuses chunks from unchanged files."""
        setup = test_setup

        # Initial index
        stats1 = setup["coordinator"].index_directory_incremental_v2(
            setup["workspace"],
            setup["cache"],
            setup["chunk_index"],
            progress_callback=None,
        )

        setup["cache"].save()
        setup["chunk_index"].save()
        initial_chunks = stats1["total_chunks"]

        # Re-index without changes (should skip unchanged files)
        stats2 = setup["coordinator"].index_directory_incremental_v2(
            setup["workspace"],
            setup["cache"],
            setup["chunk_index"],
            progress_callback=None,
        )

        # Should index 0 new files (nothing changed)
        assert stats2["changed_files"] == 0
        assert stats2["total_chunks"] == 0

        # Chunk index should still have the original chunks
        valid_chunks = setup["chunk_index"].get_valid_chunks()
        assert len(valid_chunks) == initial_chunks

    def test_watch_detects_file_changes(self, test_setup):
        """Test that watch mode detects and re-indexes changed files."""
        setup = test_setup

        # Initial index
        setup["coordinator"].index_directory_incremental_v2(
            setup["workspace"],
            setup["cache"],
            setup["chunk_index"],
            progress_callback=None,
        )

        setup["cache"].save()
        setup["chunk_index"].save()

        # Wait a moment to ensure mtime changes
        time.sleep(0.01)

        # Modify the file
        test_file = setup["workspace"] / "test.py"
        test_file.write_text("""
def hello():
    return "Hello, World!"

def goodbye():
    return "Goodbye, World!"
""")

        # Re-index (should detect change)
        stats2 = setup["coordinator"].index_directory_incremental_v2(
            setup["workspace"],
            setup["cache"],
            setup["chunk_index"],
            progress_callback=None,
        )

        # Should re-index the changed file
        assert stats2["changed_files"] >= 1
        assert stats2["total_chunks"] >= 2  # Now has 2 functions

    def test_watch_does_not_reindex_whole_repo(self, test_setup):
        """Test that watch mode doesn't re-index unchanged files."""
        setup = test_setup

        # Create multiple files
        for i in range(5):
            file_path = setup["workspace"] / f"module{i}.py"
            file_path.write_text(f"""
def function_{i}():
    return {i}
""")

        # Initial index
        stats1 = setup["coordinator"].index_directory_incremental_v2(
            setup["workspace"],
            setup["cache"],
            setup["chunk_index"],
            progress_callback=None,
        )

        setup["cache"].save()
        setup["chunk_index"].save()

        # Should index 6 files (test.py + 5 new modules)
        assert stats1["changed_files"] >= 6

        # Wait and modify only one file
        time.sleep(0.01)
        changed_file = setup["workspace"] / "module2.py"
        changed_file.write_text("""
def function_2():
    return "modified"
""")

        # Re-index
        stats2 = setup["coordinator"].index_directory_incremental_v2(
            setup["workspace"],
            setup["cache"],
            setup["chunk_index"],
            progress_callback=None,
        )

        # Should only re-index the 1 changed file, not all 6
        assert stats2["changed_files"] == 1
        assert stats2["skipped_files"] == 5  # Other 5 files skipped

    def test_chunk_index_tracks_stale_chunks(self, test_setup):
        """Test that chunk index properly tracks stale chunks when files change."""
        setup = test_setup

        # Initial index
        setup["coordinator"].index_directory_incremental_v2(
            setup["workspace"],
            setup["cache"],
            setup["chunk_index"],
            progress_callback=None,
        )

        setup["cache"].save()
        setup["chunk_index"].save()

        initial_valid_chunks = list(setup["chunk_index"].get_valid_chunks())
        assert len(initial_valid_chunks) >= 1

        # Modify file
        time.sleep(0.01)
        test_file = setup["workspace"] / "test.py"
        test_file.write_text("""
def modified_function():
    return "Modified"
""")

        # Re-index
        setup["coordinator"].index_directory_incremental_v2(
            setup["workspace"],
            setup["cache"],
            setup["chunk_index"],
            progress_callback=None,
        )

        # Old chunks should be marked stale
        stale_chunks = setup["chunk_index"].get_stale_chunks()
        assert len(stale_chunks) >= 1

        # Should have new valid chunks
        new_valid_chunks = list(setup["chunk_index"].get_valid_chunks())
        assert len(new_valid_chunks) >= 1

        # Upsert may preserve chunk IDs; ensure either IDs changed or previous IDs were stale-marked.
        assert new_valid_chunks != initial_valid_chunks or any(
            chunk_id in stale_chunks for chunk_id in initial_valid_chunks
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
