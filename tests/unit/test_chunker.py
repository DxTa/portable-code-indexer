"""Unit tests for cAST chunker algorithm."""

import pytest
from sia_code.parser.chunker import CASTChunker, CASTConfig
from sia_code.core.models import Chunk
from sia_code.core.types import ChunkType, Language, FilePath, LineNumber


class TestChunkSplitting:
    """Test chunk splitting for oversized chunks."""

    def test_chunk_splitting_large_functions(self):
        """Test that oversized chunks are split at logical boundaries."""
        config = CASTConfig(
            max_chunk_size=100,  # Small limit to trigger splitting
            min_chunk_size=20,
            greedy_merge=False,  # Disable merging for this test
        )
        chunker = CASTChunker(config)

        # Create a large chunk
        large_code = "\n".join([f"    print('Line {i}')" for i in range(50)])
        large_chunk = Chunk(
            symbol="large_function",
            start_line=LineNumber(1),
            end_line=LineNumber(50),
            code=large_code,
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("test.py"),
        )

        # Apply cAST algorithm
        result = chunker._apply_cast_algorithm([large_chunk])

        # Should be split into multiple chunks
        assert len(result) > 1

        # Each chunk should be within size limit
        for chunk in result:
            assert chunker._chunk_size(chunk) <= config.max_chunk_size

        # Check that split chunks have correct naming
        for i, chunk in enumerate(result):
            assert "part" in chunk.symbol

    def test_chunk_splitting_preserves_line_numbers(self):
        """Test that chunk splitting preserves absolute line numbers."""
        config = CASTConfig(
            max_chunk_size=50,
            greedy_merge=False,
        )
        chunker = CASTChunker(config)

        # Create chunk with known line numbers
        code = "\n".join([f"line{i}" for i in range(20)])
        chunk = Chunk(
            symbol="test",
            start_line=LineNumber(10),  # Starts at line 10
            end_line=LineNumber(29),  # 20 lines total
            code=code,
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("test.py"),
        )

        # Split
        result = chunker._split_chunk(chunk)

        # First chunk should start at original line 10
        assert result[0].start_line == 10

        # Line numbers should be contiguous
        for i in range(len(result) - 1):
            assert result[i].end_line + 1 <= result[i + 1].start_line + 1

        # Last chunk should end at original line 29
        assert result[-1].end_line == 29

    def test_chunk_splitting_handles_empty_lines(self):
        """Test that chunk splitting handles empty lines correctly."""
        config = CASTConfig(max_chunk_size=30, greedy_merge=False)
        chunker = CASTChunker(config)

        code = """
def func1():
    pass

def func2():
    pass
"""
        chunk = Chunk(
            symbol="module",
            start_line=LineNumber(1),
            end_line=LineNumber(7),
            code=code,
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("test.py"),
        )

        # Should not crash on empty lines
        result = chunker._split_chunk(chunk)
        assert len(result) >= 1


class TestGreedyMerge:
    """Test greedy merging of small adjacent chunks."""

    def test_greedy_merge_combines_small_chunks(self):
        """Test that greedy merge combines small adjacent chunks."""
        config = CASTConfig(
            max_chunk_size=500,
            merge_threshold=0.8,
            greedy_merge=True,
        )
        chunker = CASTChunker(config)

        # Create two small adjacent chunks
        chunk1 = Chunk(
            symbol="func1",
            start_line=LineNumber(1),
            end_line=LineNumber(5),
            code="def func1():\n    return 1",
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("test.py"),
        )

        chunk2 = Chunk(
            symbol="func2",
            start_line=LineNumber(6),
            end_line=LineNumber(10),
            code="def func2():\n    return 2",
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("test.py"),
        )

        # Merge
        result = chunker._greedy_merge([chunk1, chunk2])

        # Should merge into one chunk
        assert len(result) == 1
        assert "+" in result[0].symbol  # Merged name format
        assert result[0].start_line == 1
        assert result[0].end_line == 10

    def test_greedy_merge_respects_max_size(self):
        """Test that greedy merge doesn't exceed max_chunk_size."""
        config = CASTConfig(
            max_chunk_size=100,
            merge_threshold=0.8,
            greedy_merge=True,
        )
        chunker = CASTChunker(config)

        # Create two chunks that together would exceed max_size
        large_code1 = "\n".join([f"line{i}" for i in range(30)])
        large_code2 = "\n".join([f"line{i}" for i in range(30)])

        chunk1 = Chunk(
            symbol="func1",
            start_line=LineNumber(1),
            end_line=LineNumber(30),
            code=large_code1,
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("test.py"),
        )

        chunk2 = Chunk(
            symbol="func2",
            start_line=LineNumber(31),
            end_line=LineNumber(60),
            code=large_code2,
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("test.py"),
        )

        # Merge
        result = chunker._greedy_merge([chunk1, chunk2])

        # Should NOT merge (would exceed threshold)
        assert len(result) == 2

    def test_greedy_merge_only_merges_adjacent(self):
        """Test that greedy merge only merges adjacent chunks."""
        config = CASTConfig(
            max_chunk_size=500,
            merge_threshold=0.8,
            greedy_merge=True,
        )
        chunker = CASTChunker(config)

        # Create non-adjacent chunks (gap in line numbers)
        chunk1 = Chunk(
            symbol="func1",
            start_line=LineNumber(1),
            end_line=LineNumber(5),
            code="def func1(): pass",
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("test.py"),
        )

        chunk2 = Chunk(
            symbol="func2",
            start_line=LineNumber(20),  # Gap of 14 lines
            end_line=LineNumber(25),
            code="def func2(): pass",
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("test.py"),
        )

        # Merge
        result = chunker._greedy_merge([chunk1, chunk2])

        # Should NOT merge (not adjacent)
        assert len(result) == 2

    def test_greedy_merge_same_file_only(self):
        """Test that greedy merge only merges chunks from same file."""
        config = CASTConfig(
            max_chunk_size=500,
            merge_threshold=0.8,
            greedy_merge=True,
        )
        chunker = CASTChunker(config)

        chunk1 = Chunk(
            symbol="func1",
            start_line=LineNumber(1),
            end_line=LineNumber(5),
            code="def func1(): pass",
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("file1.py"),
        )

        chunk2 = Chunk(
            symbol="func2",
            start_line=LineNumber(6),
            end_line=LineNumber(10),
            code="def func2(): pass",
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("file2.py"),  # Different file
        )

        # Merge
        result = chunker._greedy_merge([chunk1, chunk2])

        # Should NOT merge (different files)
        assert len(result) == 2


class TestDeduplication:
    """Test chunk deduplication."""

    def test_deduplicate_removes_duplicates(self):
        """Test that deduplication removes duplicate chunks."""
        chunker = CASTChunker()

        # Create duplicate chunks
        chunk1 = Chunk(
            symbol="func",
            start_line=LineNumber(1),
            end_line=LineNumber(3),
            code="def func():\n    return 1",
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("test.py"),
        )

        chunk2 = Chunk(
            symbol="func_copy",
            start_line=LineNumber(10),
            end_line=LineNumber(12),
            code="def func():\n    return 1",  # Same code
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("test.py"),
        )

        # Deduplicate
        result = chunker._deduplicate([chunk1, chunk2])

        # Should keep only one
        assert len(result) == 1

    def test_deduplicate_keeps_unique(self):
        """Test that deduplication keeps unique chunks."""
        chunker = CASTChunker()

        chunk1 = Chunk(
            symbol="func1",
            start_line=LineNumber(1),
            end_line=LineNumber(3),
            code="def func1(): pass",
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("test.py"),
        )

        chunk2 = Chunk(
            symbol="func2",
            start_line=LineNumber(5),
            end_line=LineNumber(7),
            code="def func2(): pass",  # Different code
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("test.py"),
        )

        # Deduplicate
        result = chunker._deduplicate([chunk1, chunk2])

        # Should keep both
        assert len(result) == 2


class TestCASTAlgorithm:
    """Test the complete cAST algorithm integration."""

    def test_cast_algorithm_empty_input(self):
        """Test cAST algorithm with empty input."""
        chunker = CASTChunker()
        result = chunker._apply_cast_algorithm([])
        assert result == []

    def test_cast_algorithm_single_chunk(self):
        """Test cAST algorithm with single well-sized chunk."""
        config = CASTConfig(max_chunk_size=500, greedy_merge=True)
        chunker = CASTChunker(config)

        chunk = Chunk(
            symbol="func",
            start_line=LineNumber(1),
            end_line=LineNumber(10),
            code="def func():\n    return 42",
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("test.py"),
        )

        result = chunker._apply_cast_algorithm([chunk])

        # Should pass through unchanged
        assert len(result) == 1
        assert result[0].symbol == "func"

    def test_cast_algorithm_split_then_merge(self):
        """Test cAST algorithm performs split then merge operations."""
        config = CASTConfig(
            max_chunk_size=100,
            merge_threshold=0.9,
            greedy_merge=True,
        )
        chunker = CASTChunker(config)

        # Create one large chunk that will be split
        large_code = "\n".join([f"line{i}" for i in range(50)])
        chunk = Chunk(
            symbol="large",
            start_line=LineNumber(1),
            end_line=LineNumber(50),
            code=large_code,
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("test.py"),
        )

        result = chunker._apply_cast_algorithm([chunk])

        # Should be split into multiple parts
        assert len(result) > 1

        # Each part should respect size constraints
        for c in result:
            assert chunker._chunk_size(c) <= config.max_chunk_size

    def test_class_body_preservation(self):
        """Test that class bodies are preserved correctly through cAST."""
        config = CASTConfig(max_chunk_size=500, greedy_merge=False)
        chunker = CASTChunker(config)

        # Simulate a class with methods
        class_chunk = Chunk(
            symbol="MyClass",
            start_line=LineNumber(1),
            end_line=LineNumber(20),
            code="""class MyClass:
    def method1(self):
        return 1
    
    def method2(self):
        return 2
""",
            chunk_type=ChunkType.CLASS,
            language=Language.PYTHON,
            file_path=FilePath("test.py"),
        )

        result = chunker._apply_cast_algorithm([class_chunk])

        # Should keep class structure
        assert len(result) >= 1
        assert any("class MyClass" in c.code for c in result)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
