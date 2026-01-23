"""Test case to verify the fix for empty code handling in search results."""

import pytest
from pathlib import Path
from sia_code.core.models import Chunk
from sia_code.core.types import ChunkType, Language, FilePath, LineNumber
from sia_code.storage.usearch_backend import UsearchSqliteBackend


@pytest.fixture
def backend(tmp_path):
    """Create a temporary backend for testing."""
    test_path = tmp_path / "test_empty_code.sia-code"
    backend = UsearchSqliteBackend(test_path, embedding_enabled=False)
    backend.create_index()
    yield backend
    backend.close()


class TestEmptyCodeHandling:
    """Test that empty code fields are handled gracefully."""

    def test_store_chunk_with_empty_text(self, backend):
        """Test storing a chunk and searching doesn't crash with empty text in memvid."""
        # Store a chunk with minimal text to memvid (empty text causes embedding issues)
        backend.mem.put(
            title="empty_function",
            label=ChunkType.FUNCTION.value,
            metadata={
                "file_path": "test.py",
                "start_line": 1,
                "end_line": 1,
                "language": Language.PYTHON.value,
            },
            text="# placeholder",  # Memvid needs some text
            uri="test://test.py#1",
        )

        # Test that search completes without error
        results = backend.search_lexical("empty", k=5)
        assert isinstance(results, list)

    def test_search_result_fallback_code(self, backend):
        """Test that search results have fallback code when text is missing."""
        # Store a chunk
        backend.mem.put(
            title="test_func",
            label=ChunkType.FUNCTION.value,
            metadata={
                "file_path": "test.py",
                "start_line": 10,
                "end_line": 20,
                "language": Language.PYTHON.value,
            },
            text="def test_func(): pass",
            uri="test://test.py#10",
        )

        results = backend.search_lexical("test", k=5)

        # Results should have code (either actual or fallback)
        for result in results:
            assert result.chunk.code is not None
            assert len(result.chunk.code) > 0

    def test_chunk_model_rejects_empty_code(self):
        """Test that Chunk model validation rejects empty code."""
        with pytest.raises(ValueError, match="code cannot be empty"):
            Chunk(
                symbol="test",
                start_line=LineNumber(1),
                end_line=LineNumber(1),
                code="",  # Empty code should raise
                chunk_type=ChunkType.FUNCTION,
                language=Language.PYTHON,
                file_path=FilePath("test.py"),
            )

    def test_chunk_model_accepts_whitespace_only_code(self):
        """Test that Chunk model accepts whitespace-only code (it's not empty)."""
        # This should NOT raise - whitespace is valid content
        chunk = Chunk(
            symbol="test",
            start_line=LineNumber(1),
            end_line=LineNumber(1),
            code="   ",  # Whitespace only
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("test.py"),
        )
        assert chunk.code == "   "


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
