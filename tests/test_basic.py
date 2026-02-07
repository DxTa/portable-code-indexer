"""Basic test of Sia Code functionality (lexical search only)."""

import pytest
from sia_code.core.models import Chunk
from sia_code.core.types import ChunkType, Language, FilePath, LineNumber
from sia_code.storage.backend import UsearchSqliteBackend


@pytest.fixture
def backend(tmp_path):
    """Create a temporary backend for testing."""
    test_path = tmp_path / "test_index.sia-code"
    backend = UsearchSqliteBackend(test_path, embedding_enabled=False)
    backend.create_index()
    yield backend
    backend.close()


@pytest.fixture
def sample_chunks():
    """Create sample chunks for testing."""
    return [
        Chunk(
            symbol="Language",
            start_line=LineNumber(14),
            end_line=LineNumber(104),
            code="""class Language(str, Enum):
    \"\"\"Supported programming languages.\"\"\"
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    # Support for 30+ languages""",
            chunk_type=ChunkType.CLASS,
            language=Language.PYTHON,
            file_path=FilePath("sia_code/core/types.py"),
        ),
        Chunk(
            symbol="UsearchSqliteBackend",
            start_line=LineNumber(12),
            end_line=LineNumber(150),
            code="""class UsearchSqliteBackend:
    \"\"\"Storage backend using Memvid for code search.\"\"\"
    
    def __init__(self, path: Path):
        self.path = path
        self.mem = None
        
    def search_semantic(self, query: str, k: int = 10):
        \"\"\"Perform semantic search on code chunks.\"\"\"
        results = self.mem.find(query, mode="sem", k=k)
        return self._convert_results(results)""",
            chunk_type=ChunkType.CLASS,
            language=Language.PYTHON,
            file_path=FilePath("sia_code/storage/backend.py"),
        ),
        Chunk(
            symbol="Chunk",
            start_line=LineNumber(15),
            end_line=LineNumber(80),
            code="""class Chunk:
    \"\"\"Represents a semantic code chunk with metadata.\"\"\"
    
    symbol: str  # Function or class name
    start_line: LineNumber
    end_line: LineNumber  
    code: str  # Raw code content
    chunk_type: ChunkType
    language: Language
    file_path: FilePath""",
            chunk_type=ChunkType.CLASS,
            language=Language.PYTHON,
            file_path=FilePath("sia_code/core/models.py"),
        ),
    ]


class TestUsearchSqliteBackend:
    """Test UsearchSqliteBackend functionality."""

    def test_create_index(self, tmp_path):
        """Test index creation."""
        test_path = tmp_path / "test.sia-code"
        backend = UsearchSqliteBackend(test_path, embedding_enabled=False)
        backend.create_index()
        assert backend.mem is not None
        backend.close()

    def test_store_chunks(self, backend, sample_chunks):
        """Test storing chunks."""
        chunk_ids = backend.store_chunks_batch(sample_chunks)
        assert len(chunk_ids) == len(sample_chunks)
        for cid in chunk_ids:
            assert cid is not None

    def test_lexical_search(self, backend, sample_chunks):
        """Test lexical search functionality."""
        backend.store_chunks_batch(sample_chunks)

        results = backend.search_lexical("search", k=5)

        # Respect the k parameter
        assert 1 <= len(results) <= 5

        # Check result structure
        for result in results:
            assert result.chunk is not None
            assert result.chunk.symbol is not None
            assert result.score > 0  # BM25 scores are positive

        # Verify results are sorted by score (descending)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True), (
            "Results should be sorted by score (descending)"
        )

    def test_lexical_search_multiple_terms(self, backend, sample_chunks):
        """Test lexical search with multiple terms."""
        backend.store_chunks_batch(sample_chunks)

        results = backend.search_lexical("semantic code chunk", k=5)

        # Respect the k parameter
        assert 1 <= len(results) <= 5

        # Verify results are sorted by relevance
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_lexical_search_language(self, backend, sample_chunks):
        """Test lexical search finds language-related content."""
        backend.store_chunks_batch(sample_chunks)

        results = backend.search_lexical("languages", k=5)

        # Respect the k parameter
        assert 1 <= len(results) <= 5

        # Should find the Language class
        symbols = [r.chunk.symbol for r in results]
        assert "Language" in symbols

        # Verify scores are descending
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)


class TestChunkModel:
    """Test Chunk model validation."""

    def test_chunk_creation(self):
        """Test basic chunk creation."""
        chunk = Chunk(
            symbol="test_function",
            start_line=LineNumber(1),
            end_line=LineNumber(10),
            code="def test_function(): pass",
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("test.py"),
        )
        assert chunk.symbol == "test_function"
        assert chunk.line_count == 10

    def test_chunk_invalid_lines(self):
        """Test chunk validation rejects invalid lines."""
        with pytest.raises(ValueError):
            Chunk(
                symbol="test",
                start_line=LineNumber(0),  # Invalid: must be >= 1
                end_line=LineNumber(10),
                code="test",
                chunk_type=ChunkType.FUNCTION,
                language=Language.PYTHON,
                file_path=FilePath("test.py"),
            )

    def test_chunk_end_before_start(self):
        """Test chunk validation rejects end_line < start_line."""
        with pytest.raises(ValueError):
            Chunk(
                symbol="test",
                start_line=LineNumber(10),
                end_line=LineNumber(5),  # Invalid: end < start
                code="test",
                chunk_type=ChunkType.FUNCTION,
                language=Language.PYTHON,
                file_path=FilePath("test.py"),
            )

    def test_chunk_empty_code(self):
        """Test chunk validation rejects empty code."""
        with pytest.raises(ValueError):
            Chunk(
                symbol="test",
                start_line=LineNumber(1),
                end_line=LineNumber(1),
                code="",  # Invalid: empty
                chunk_type=ChunkType.FUNCTION,
                language=Language.PYTHON,
                file_path=FilePath("test.py"),
            )


class TestURIParsing:
    """Test URI parsing functionality."""

    def test_parse_valid_uri(self, tmp_path):
        """Test parsing valid pci:// URI."""
        test_path = tmp_path / "test.sia-code"
        backend = UsearchSqliteBackend(test_path, embedding_enabled=False)
        backend.create_index()

        file_path, start, end = backend._parse_uri("pci:///home/user/file.py#42")
        assert file_path == "/home/user/file.py"
        assert start == 42
        assert end == 42
        backend.close()

    def test_parse_uri_no_line(self, tmp_path):
        """Test parsing URI without line number."""
        test_path = tmp_path / "test.sia-code"
        backend = UsearchSqliteBackend(test_path, embedding_enabled=False)
        backend.create_index()

        file_path, start, end = backend._parse_uri("pci:///home/user/file.py")
        assert file_path == "/home/user/file.py"
        assert start == 1
        assert end == 1
        backend.close()

    def test_parse_invalid_uri(self, tmp_path):
        """Test parsing invalid URI returns defaults."""
        test_path = tmp_path / "test.sia-code"
        backend = UsearchSqliteBackend(test_path, embedding_enabled=False)
        backend.create_index()

        file_path, start, end = backend._parse_uri("invalid://something")
        assert file_path == "unknown"
        assert start == 1
        assert end == 1
        backend.close()


class TestLanguageDetection:
    """Test language detection from file extensions."""

    def test_python_detection(self):
        """Test Python file detection."""
        assert Language.from_extension(".py") == Language.PYTHON

    def test_javascript_detection(self):
        """Test JavaScript file detection."""
        assert Language.from_extension(".js") == Language.JAVASCRIPT

    def test_typescript_detection(self):
        """Test TypeScript file detection."""
        assert Language.from_extension(".ts") == Language.TYPESCRIPT

    def test_go_detection(self):
        """Test Go file detection."""
        assert Language.from_extension(".go") == Language.GO

    def test_rust_detection(self):
        """Test Rust file detection."""
        assert Language.from_extension(".rs") == Language.RUST

    def test_unknown_extension(self):
        """Test unknown extension returns UNKNOWN."""
        assert Language.from_extension(".xyz") == Language.UNKNOWN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
