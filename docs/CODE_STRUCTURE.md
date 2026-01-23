# Code Structure

This document describes the organization of the sia-code codebase, including module hierarchy, key classes, and architectural patterns.

## Table of Contents

- [Module Overview](#module-overview)
- [Core Modules](#core-modules)
- [Storage Layer](#storage-layer)
- [Parser & Indexer](#parser--indexer)
- [CLI & Configuration](#cli--configuration)
- [Testing Infrastructure](#testing-infrastructure)
- [Entry Points](#entry-points)
- [Dependency Graph](#dependency-graph)

---

## Module Overview

```
sia_code/
├── cli.py                      # CLI entry point and command handlers
├── config.py                   # Configuration management (Pydantic models)
├── core/                       # Core data models and types
│   ├── models.py              # Chunk, SearchResult, IndexStats, etc.
│   └── types.py               # Enums: Language, ChunkType, etc.
├── storage/                    # Storage backend abstraction
│   ├── base.py                # Abstract StorageBackend interface
│   ├── usearch_backend.py     # Usearch + SQLite implementation ⭐
│   ├── backend.py             # Legacy memvid backend (deprecated)
│   └── factory.py             # Backend detection and creation
├── parser/                     # Code parsing and chunking
│   ├── concepts.py            # AST parsing with tree-sitter
│   ├── chunker.py             # Code chunking logic
│   ├── engine.py              # Parser orchestration
│   └── languages/             # Language-specific tree-sitter grammars
├── indexer/                    # Indexing pipeline
│   ├── coordinator.py         # Main indexing orchestration
│   ├── embedder.py            # Embedding generation
│   ├── chunk_index.py         # Chunk deduplication and tracking
│   ├── dependency_discovery.py # Dependency detection (Python, TypeScript)
│   ├── doc_linker.py          # Documentation-to-code linking
│   ├── project_analyzer.py    # Project-level analysis
│   ├── hash_cache.py          # File hash caching for incremental indexing
│   └── metrics.py             # Indexing metrics and statistics
└── __init__.py                 # Package initialization
```

---

## Core Modules

### `core/models.py`

Defines core data structures using Pydantic for validation and serialization:

**Key Classes:**

- **`Chunk`** - Represents a code chunk with metadata
  - `id`: Unique chunk identifier
  - `file_path`: Source file path
  - `content`: Code content
  - `start_line`, `end_line`: Line range
  - `chunk_type`: Function, class, file-level, etc.
  - `language`: Programming language
  - `embedding`: Optional vector embedding

- **`SearchResult`** - Search result with scoring
  - `chunk`: The matched chunk
  - `score`: Relevance score (0-1)
  - `rank`: Position in results
  - `method`: Search method (semantic, lexical, hybrid)

- **`IndexStats`** - Index statistics
  - `total_files`: Number of indexed files
  - `total_chunks`: Number of chunks
  - `index_size_mb`: Storage size
  - `last_updated`: Timestamp
  - `embedding_model`: Model used for embeddings

- **`Decision`** - Decision workflow entry (FIFO queue)
  - `id`: Decision ID
  - `question`: Decision question
  - `options`: List of options
  - `chosen`: Selected option
  - `reasoning`: Rationale

- **`TimelineEvent`** - Git timeline event
  - `id`: Event ID
  - `timestamp`: Commit timestamp
  - `author`: Commit author
  - `message`: Commit message
  - `files_changed`: Affected files

- **`ChangelogEntry`** - Changelog entry
  - `version`: Release version
  - `date`: Release date
  - `changes`: List of changes

### `core/types.py`

Defines enums and type aliases:

**Key Enums:**

- **`Language`** - Supported programming languages
  - `PYTHON`, `TYPESCRIPT`, `JAVASCRIPT`, `GO`, `RUST`, `CPP`, `JAVA`, etc.

- **`ChunkType`** - Chunk classification
  - `FUNCTION`, `CLASS`, `METHOD`, `FILE_LEVEL`, `IMPORT`, `DOCUMENTATION`

---

## Storage Layer

### `storage/base.py` (Abstract Interface)

Defines the `StorageBackend` abstract base class that all backends must implement:

**Core Methods:**

```python
class StorageBackend(ABC):
    @abstractmethod
    def create_index(self) -> None:
        """Create a new index."""
    
    @abstractmethod
    def add_chunks(self, chunks: list[Chunk]) -> None:
        """Add chunks to the index."""
    
    @abstractmethod
    def search(
        self, 
        query: str, 
        limit: int = 10,
        vector_weight: float = 0.7
    ) -> list[SearchResult]:
        """Search the index (hybrid: semantic + lexical)."""
    
    @abstractmethod
    def get_stats(self) -> IndexStats:
        """Get index statistics."""
    
    @abstractmethod
    def delete_chunks_by_file(self, file_path: str) -> int:
        """Delete all chunks from a file."""
```

### `storage/usearch_backend.py` (Main Implementation)

**Class:** `UsearchSqliteBackend`

The primary storage backend combining:
- **Usearch HNSW** - Fast vector similarity search
- **SQLite FTS5** - Full-text search with BM25 ranking
- **Reciprocal Rank Fusion (RRF)** - Hybrid result merging

**Key Features:**

1. **Unified Index Structure**
   - Vectors: `.sia-code/vectors.usearch` (f16 quantization)
   - Metadata + FTS5: `.sia-code/index.db` (SQLite)
   - Cache: `.sia-code/cache/` (embedding cache)

2. **Performance Optimizations**
   - GPU auto-detection for embeddings (5-10x speedup)
   - Parallel search (semantic + lexical run concurrently)
   - Query embedding cache (LRU, 1000 entries)
   - Thread-safe SQLite connections

3. **Search Methods**
   - `search()` - Hybrid search with RRF fusion
   - `search_files()` - File-level aggregation (for benchmarks)
   - `semantic_search()` - Vector search only
   - `lexical_search()` - FTS5 BM25 only

**Key Methods:**

```python
class UsearchSqliteBackend(StorageBackend):
    def __init__(
        self,
        path: Path,
        embedding_enabled: bool = True,
        embedding_model: str = "BAAI/bge-small-en-v1.5",
        ndim: int = 384,
        dtype: str = "f16",
        metric: str = "cos",
    ):
        """Initialize with Usearch HNSW + SQLite FTS5."""
    
    def _get_embedder(self):
        """Lazy-load embedding model with GPU support."""
        # Auto-detects CUDA, falls back to CPU
        device = "cuda" if torch.cuda.is_available() else "cpu"
        return SentenceTransformer(self.embedding_model, device=device)
    
    def _preprocess_code_query(self, query: str) -> str:
        """Extract searchable tokens from code queries."""
        # Removes special chars, focuses on identifiers
        # Critical for FTS5 BM25 performance
    
    def search(
        self, 
        query: str, 
        limit: int = 10,
        vector_weight: float = 0.7
    ) -> list[SearchResult]:
        """Hybrid search with parallel execution."""
        # Runs semantic + lexical in parallel
        # Merges with RRF (k=60)
        # Returns top-k results
    
    def search_files(
        self,
        query: str,
        top_k: int = 5,
        vector_weight: float = 0.7
    ) -> list[tuple[str, float]]:
        """File-level search for benchmarks."""
        # Aggregates chunk scores by file
        # Returns (file_path, score) tuples
```

**Performance Characteristics:**
- Indexing: 60-127 chunks/second (GPU/CPU)
- Query: ~60ms per query
- Index size: 17-25 MB per repo (8,000-10,000 chunks)

### `storage/factory.py`

**Function:** `create_backend(path: Path, config: Config) -> StorageBackend`

- Auto-detects backend type based on file extensions
- `.mv2` files → `MemvidBackend` (legacy)
- `.sia-code/` directory → `UsearchSqliteBackend` (current)
- Creates appropriate backend instance with config

---

## Parser & Indexer

### `parser/concepts.py` - AST Parsing

**Class:** `ConceptExtractor`

Uses tree-sitter for language-agnostic AST parsing:

```python
class ConceptExtractor:
    def extract_concepts(
        self, 
        code: str, 
        language: Language
    ) -> list[Concept]:
        """Extract functions, classes, methods from code."""
        # Uses tree-sitter queries
        # Language-specific parsing rules
        # Error-tolerant (handles partial/broken code)
```

**Supported Languages:**
- Python, TypeScript, JavaScript, Go, Rust, C++, Java, C#, Ruby, PHP

### `parser/chunker.py` - Code Chunking

**Class:** `Chunker`

Implements AST-aware code chunking:

```python
class Chunker:
    def chunk_file(
        self,
        file_path: str,
        content: str,
        language: Language,
        max_chunk_size: int = 1200,
        min_chunk_size: int = 50
    ) -> list[Chunk]:
        """Chunk code preserving logical boundaries."""
        # 1. Extract concepts (functions, classes)
        # 2. Create chunks respecting boundaries
        # 3. Merge small chunks (greedy algorithm)
        # 4. Add context (surrounding code)
```

**Chunking Strategy:**
1. Parse AST to find concept boundaries
2. Split at function/class boundaries
3. Keep related code together (no mid-function splits)
4. Merge small chunks below `min_chunk_size`
5. Add context from parent scopes

### `indexer/coordinator.py` - Indexing Orchestration

**Class:** `IndexingCoordinator`

Main orchestrator for the indexing pipeline:

```python
class IndexingCoordinator:
    def index_repository(
        self,
        repo_path: Path,
        backend: StorageBackend,
        config: Config
    ) -> IndexStats:
        """Index a repository with all files."""
        # 1. Discover files (respect .gitignore)
        # 2. Filter by language and size
        # 3. Parse and chunk each file
        # 4. Generate embeddings (batched)
        # 5. Add to storage backend
        # 6. Track metrics
```

**Pipeline Stages:**

1. **File Discovery**
   - Walks directory tree
   - Applies exclude patterns (`.gitignore`, config)
   - Filters by file size (`max_file_size_mb`)

2. **Parsing**
   - Detects language from file extension
   - Parses AST with tree-sitter
   - Extracts concepts (functions, classes)

3. **Chunking**
   - Splits code at logical boundaries
   - Merges small chunks
   - Adds context from parent scopes

4. **Embedding**
   - Batches chunks (batch size: 32)
   - Generates embeddings with GPU acceleration
   - Caches embeddings by content hash

5. **Storage**
   - Adds chunks to backend (batched inserts)
   - Updates FTS5 index
   - Tracks statistics

### `indexer/embedder.py` - Embedding Generation

**Class:** `Embedder`

Handles embedding generation with GPU support:

```python
class Embedder:
    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en-v1.5",
        device: str = "auto"
    ):
        """Initialize with GPU auto-detection."""
        self.device = device if device != "auto" else self._detect_device()
    
    def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 32
    ) -> np.ndarray:
        """Generate embeddings in batches."""
        # GPU-accelerated if available
        # Returns (N, ndim) array
```

### `indexer/dependency_discovery.py` - Dependency Detection

Analyzes project dependencies for indexing:

- Python: `requirements.txt`, `pyproject.toml`, `setup.py`
- TypeScript/JavaScript: `package.json`, `yarn.lock`
- Go: `go.mod`
- Rust: `Cargo.toml`

Extracts dependency names and versions for selective indexing.

---

## CLI & Configuration

### `cli.py` - Command-Line Interface

**Main Commands:**

```bash
# Initialize index
sia-code init [--model MODEL] [--no-embeddings]

# Index repository
sia-code index PATH [--incremental] [--verbose]

# Search index
sia-code search QUERY [--limit N] [--vector-weight W]

# Show statistics
sia-code stats

# Configuration management
sia-code config get KEY
sia-code config set KEY VALUE
```

**Implementation:**
- Uses `click` for CLI parsing
- Uses `rich` for formatted output
- Supports progress bars and colored output

### `config.py` - Configuration Management

**Class:** `Config`

Pydantic-based configuration with nested models:

```python
class Config(BaseModel):
    embedding: EmbeddingConfig       # Embedding settings
    indexing: IndexingConfig         # File filtering, exclusions
    chunking: ChunkingConfig         # Chunk size, merge strategy
    search: SearchConfig             # Search weights, limits
    dependencies: DependencyConfig   # Dependency indexing
    documentation: DocumentationConfig # Doc linking
    adaptive: AdaptiveConfig         # Auto-detection
```

**Configuration File:** `.sia-code/config.json`

**Key Settings:**

```json
{
  "embedding": {
    "enabled": true,
    "model": "BAAI/bge-small-en-v1.5",
    "dimensions": 384
  },
  "search": {
    "vector_weight": 0.0,  // 0.0 = lexical-only (best!)
    "default_limit": 10
  },
  "chunking": {
    "max_chunk_size": 1200,
    "min_chunk_size": 50
  }
}
```

---

## Testing Infrastructure

### Directory Structure

```
tests/
├── unit/                       # Unit tests
│   ├── test_parser.py
│   ├── test_chunker.py
│   ├── test_storage.py
│   └── test_search.py
├── integration/                # Integration tests
│   ├── test_indexing.py
│   └── test_e2e.py
├── benchmarks/                 # Benchmark scripts
│   ├── run_repoeval_benchmark.py      # Single-repo benchmark
│   ├── run_full_repoeval_benchmark.py # Full 1,600-query benchmark
│   ├── compare_embeddings.py          # Multi-config comparison
│   └── datasets/
│       └── repoeval_loader.py         # RepoEval dataset loader
└── fixtures/                   # Test data
    └── sample_repos/
```

### Benchmark Infrastructure

**Key Scripts:**

1. **`run_repoeval_benchmark.py`**
   - Single repository benchmark
   - Usage: `python run_repoeval_benchmark.py REPO_NAME`
   - Outputs: `results/repoeval/{repo_name}.json`

2. **`run_full_repoeval_benchmark.py`**
   - Full 1,600-query benchmark (all 8 repos)
   - Usage: `python run_full_repoeval_benchmark.py`
   - Outputs: `results/repoeval_full/benchmark_summary.json`

3. **`compare_embeddings.py`**
   - Multi-configuration comparison
   - Tests different embedding models and weights
   - Outputs: `results/comparison/embedding_comparison.json`

**Dataset:** RepoEval (from cAST paper)
- 8 Python repositories
- 200 queries per repository
- 1,600 total queries
- File-level ground truth labels

---

## Entry Points

### Package Entry Point

**`sia_code/__init__.py`:**

```python
__version__ = "0.3.0"

from .config import Config
from .storage import StorageBackend
from .core.models import Chunk, SearchResult
```

### CLI Entry Point

**`pyproject.toml`:**

```toml
[project.scripts]
sia-code = "sia_code.cli:cli"
```

**Execution:**
```bash
sia-code --help
```

### Programmatic API

```python
from sia_code import Config
from sia_code.storage import create_backend
from pathlib import Path

# Load config
config = Config.load(Path(".sia-code/config.json"))

# Create backend
backend = create_backend(Path(".sia-code"), config)

# Search
results = backend.search("authentication middleware", limit=10)
```

---

## Dependency Graph

### External Dependencies

**Core:**
- `usearch` - HNSW vector index (f16 quantization)
- `sqlite3` - Metadata + FTS5 lexical search
- `sentence-transformers` - Embedding models
- `torch` - GPU acceleration
- `tree-sitter` - Multi-language AST parsing
- `pydantic` - Configuration validation

**CLI:**
- `click` - Command-line parsing
- `rich` - Formatted output

**Testing:**
- `pytest` - Test framework
- `pytest-cov` - Coverage reporting

### Internal Dependencies

```
cli.py
  └─> config.py
  └─> indexer/coordinator.py
      └─> parser/concepts.py
      └─> parser/chunker.py
      └─> indexer/embedder.py
      └─> storage/factory.py
          └─> storage/usearch_backend.py
              └─> core/models.py
              └─> core/types.py
```

**Key Dependency Flows:**

1. **Indexing Pipeline:**
   ```
   CLI → IndexingCoordinator → ConceptExtractor → Chunker → Embedder → UsearchSqliteBackend
   ```

2. **Search Pipeline:**
   ```
   CLI → Config → UsearchSqliteBackend → [Semantic + Lexical] → RRF → Results
   ```

3. **Configuration:**
   ```
   CLI → Config.load() → Pydantic validation → Backend initialization
   ```

---

## Design Patterns

### 1. **Abstract Backend Pattern**

All storage backends implement the `StorageBackend` interface, allowing:
- Easy backend swapping
- Testing with mock backends
- Future backend additions (e.g., Elasticsearch, Milvus)

### 2. **Strategy Pattern - Search Methods**

The `UsearchSqliteBackend` supports multiple search strategies:
- Semantic-only (`vector_weight=1.0`)
- Lexical-only (`vector_weight=0.0`)
- Hybrid RRF (`vector_weight=0.5`)

### 3. **Factory Pattern - Backend Creation**

`storage/factory.py` auto-detects and creates appropriate backends based on file structure.

### 4. **Builder Pattern - Configuration**

`Config` uses nested Pydantic models for composable, validated configuration.

### 5. **Lazy Initialization - Embedder**

Embedding model loaded only when needed to reduce startup time and memory usage.

---

## Code Quality & Standards

### Type Hints

All public APIs use Python type hints:
```python
def search(
    self, 
    query: str, 
    limit: int = 10,
    vector_weight: float = 0.7
) -> list[SearchResult]:
    ...
```

### Documentation

- Docstrings for all public classes and methods
- Type hints for all function signatures
- Architecture docs in `docs/` directory

### Testing

- Unit tests for core logic
- Integration tests for end-to-end flows
- Benchmarks for performance validation

---

## File Size Breakdown

**Key Files (Lines of Code):**

| File | Lines | Description |
|------|-------|-------------|
| `storage/usearch_backend.py` | ~1,500 | Main storage implementation |
| `storage/base.py` | ~370 | Abstract interface |
| `parser/concepts.py` | ~800 | AST parsing |
| `parser/chunker.py` | ~600 | Code chunking |
| `indexer/coordinator.py` | ~500 | Indexing orchestration |
| `cli.py` | ~800 | CLI commands |
| `config.py` | ~133 | Configuration models |

**Total codebase:** ~8,000 lines of Python (excluding tests)

---

## Next Steps

For more details on specific components:

- **Architecture:** See [ARCHITECTURE.md](ARCHITECTURE.md)
- **Indexing:** See [INDEXING.md](INDEXING.md)
- **Querying:** See [QUERYING.md](QUERYING.md)
- **CLI Usage:** See [CLI_FEATURES.md](CLI_FEATURES.md)
- **Benchmarks:** See [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md)
