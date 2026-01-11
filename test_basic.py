"""Basic test of PCI functionality (lexical search only)."""

from pathlib import Path
from pci.core.models import Chunk
from pci.core.types import ChunkType, Language, FilePath, LineNumber
from pci.storage.backend import MemvidBackend

# Create a test index
test_path = Path("test_index.mv2")
backend = MemvidBackend(test_path)
backend.create_index()

print("✓ Created Memvid index")

# Create some test chunks from our own codebase
chunks = [
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
        file_path=FilePath("pci/core/types.py"),
    ),
    Chunk(
        symbol="MemvidBackend",
        start_line=LineNumber(12),
        end_line=LineNumber(150),
        code="""class MemvidBackend:
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
        file_path=FilePath("pci/storage/backend.py"),
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
        file_path=FilePath("pci/core/models.py"),
    ),
]

# Store chunks WITHOUT embeddings (lexical search only)
print(f"\nStoring {len(chunks)} chunks (lexical search only)...")
for i, chunk in enumerate(chunks, 1):
    backend.mem.put(
        title=chunk.symbol,
        label=chunk.chunk_type.value,
        metadata={
            "file_path": str(chunk.file_path),
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "language": chunk.language.value,
        },
        text=chunk.code,
        uri=f"pci://{chunk.file_path}#{chunk.start_line}",
        # No embeddings
    )
    print(f"  {i}. Stored {chunk.symbol}")

print(f"✓ Stored {len(chunks)} chunks")

# Test lexical search
print("\n--- Lexical Search Test 1: 'search' ---")
results = backend.search_lexical("search", k=5)
print(f"Found {len(results)} results:")
for i, result in enumerate(results, 1):
    print(f"  {i}. {result.chunk.symbol} (score: {result.score:.3f})")
    print(f"     {result.chunk.file_path}:{result.chunk.start_line}")

print("\n--- Lexical Search Test 2: 'semantic code chunk' ---")
results = backend.search_lexical("semantic code chunk", k=5)
print(f"Found {len(results)} results:")
for i, result in enumerate(results, 1):
    print(f"  {i}. {result.chunk.symbol} (score: {result.score:.3f})")
    print(f"     {result.chunk.file_path}:{result.chunk.start_line}")
    if result.snippet:
        snippet = result.snippet.replace('\n', ' ')[:80]
        print(f"     Snippet: {snippet}...")

print("\n--- Lexical Search Test 3: 'languages' ---")
results = backend.search_lexical("languages", k=5)
print(f"Found {len(results)} results:")
for i, result in enumerate(results, 1):
    print(f"  {i}. {result.chunk.symbol} (score: {result.score:.3f})")
    print(f"     {result.chunk.file_path}:{result.chunk.start_line}")

# Clean up
backend.close()
test_path.unlink()
print("\n✓ Test completed successfully!")
print("\nNote: Semantic search requires OpenAI API key on this platform.")
print("Lexical (BM25) search works without any API keys.")
