# Indexing Pipeline

**Version:** 2.0  
**Date:** January 22, 2026

---

## Overview

The indexing pipeline transforms source code files into a searchable index combining vector embeddings and full-text search. The process involves parsing, chunking, embedding, and storage.

**Pipeline Stages:**
```
Source Files → Parser → Chunker → Embedder → Backend → Index Files
```

**Performance:** ~60 chunks/second (with GPU) or ~127 chunks/second (lexical-only)

---

## Pipeline Stages

### Stage 1: File Discovery

**Purpose:** Find all source code files in the repository

**Implementation:** `sia_code/indexer/coordinator.py`

```python
def discover_files(self, root_path: Path) -> list[Path]:
    """Discover files matching include patterns, excluding exclude patterns."""
    files = []
    for pattern in config.indexing.include_patterns:  # Default: ["**/*"]
        for file_path in root_path.glob(pattern):
            if self._should_index(file_path):
                files.append(file_path)
    return files

def _should_index(self, file_path: Path) -> bool:
    """Check if file should be indexed."""
    # Skip if matches exclude patterns
    for pattern in config.indexing.exclude_patterns:
        if file_path.match(pattern):
            return False
    
    # Skip if too large
    if file_path.stat().st_size > config.indexing.max_file_size_mb * 1024 * 1024:
        return False
    
    # Skip binary files
    if self._is_binary(file_path):
        return False
    
    return True
```

**Default Exclude Patterns:**
- `node_modules/`, `__pycache__/`, `.git/`
- `venv/`, `.venv/`
- `*.pyc`, `*.pyo`, `*.so`, `*.dylib`

**Gitignore Integration (v0.3.0+):**
Sia-code automatically loads patterns from `.gitignore` files and merges them with configured exclude patterns:
- Supports root `.gitignore` and nested `.gitignore` files in subdirectories
- Nested patterns are automatically prefixed with their relative directory path
- Handles comments, negation patterns (`!`), and empty lines
- Deduplicates patterns to avoid redundancy
- No configuration required - works automatically if `.gitignore` exists

Example:
```
# Root .gitignore
*.log

# src/.gitignore  
*.tmp
```
Results in effective patterns: `*.log`, `src/*.tmp`

**Default Include Patterns:**
- `**/*` (all files, filtered by language detection)

### Stage 2: Language Detection & Parsing

**Purpose:** Detect language and parse file into AST

**Implementation:** `sia_code/parser/concepts.py`

**Supported Languages:**
- Python
- TypeScript/JavaScript
- (Extensible via tree-sitter grammars)

**Parser Flow:**
```python
def parse_file(file_path: Path) -> list[Concept]:
    """Parse file and extract concepts."""
    # 1. Detect language
    language = detect_language(file_path)
    
    # 2. Load tree-sitter parser
    parser = get_parser(language)
    
    # 3. Parse to AST
    tree = parser.parse(file_path.read_bytes())
    
    # 4. Extract concepts (functions, classes, etc.)
    concepts = extract_concepts(tree, language)
    
    return concepts
```

**Tree-sitter Benefits:**
- **Multi-language:** Single API for all languages
- **Error-tolerant:** Handles incomplete/invalid code
- **Fast:** Incremental parsing
- **Accurate:** Language-specific grammars

### Stage 3: Concept Extraction

**Purpose:** Extract semantic units (functions, classes, etc.) from AST

**Implementation:** `sia_code/parser/concepts.py`

**Extraction Strategy:**

**Python Example:**
```python
def _extract_python_concepts(self, root: Node, source_code: bytes) -> list[Concept]:
    """Extract Python functions and classes."""
    concepts = []
    
    def traverse(node: Node):
        if node.type == 'function_definition':
            # Extract function
            func_name = get_function_name(node)
            start_line = node.start_point[0]
            end_line = node.end_point[0]
            code = source_code[node.start_byte:node.end_byte].decode()
            
            concepts.append(Concept(
                type='FUNCTION',
                name=func_name,
                start_line=start_line,
                end_line=end_line,
                code=code
            ))
        
        elif node.type == 'class_definition':
            # Extract class
            # ... similar logic
        
        # Recurse
        for child in node.children:
            traverse(child)
    
    traverse(root)
    return concepts
```

**Extracted Concept Types:**
- `FUNCTION`: Function definitions
- `CLASS`: Class definitions
- `METHOD`: Methods within classes
- `COMMENT`: Docstrings and comments
- `FILE`: Whole-file fallback for small files

### Stage 4: Chunking

**Purpose:** Convert concepts into indexable chunks

**Implementation:** `sia_code/parser/chunker.py`

**Chunking Strategy:**

**1. Direct Mapping (Most Common)**
```python
def chunk_concept(concept: Concept) -> Chunk:
    """Convert concept to chunk (1:1 mapping)."""
    return Chunk(
        id=generate_id(),
        symbol=concept.name,
        chunk_type=concept.type,
        file_path=concept.file_path,
        start_line=concept.start_line,
        end_line=concept.end_line,
        code=concept.code,
        metadata={
            'language': detect_language(concept.file_path),
            'size': len(concept.code)
        }
    )
```

**2. Splitting Large Concepts**
```python
if len(concept.code) > config.chunking.max_chunk_size:
    # Split large function/class into smaller chunks
    sub_chunks = split_by_lines(
        concept,
        max_lines=config.chunking.max_chunk_size // 80  # ~80 chars/line
    )
```

**3. Merging Small Concepts**
```python
if len(concept.code) < config.chunking.min_chunk_size:
    # Merge with neighboring concepts
    merged = merge_concepts([prev_concept, concept, next_concept])
```

**Configuration:**
```python
class ChunkingConfig:
    max_chunk_size: int = 1200  # ~15-20 lines
    min_chunk_size: int = 50    # ~1-2 lines
    merge_threshold: float = 0.8
    greedy_merge: bool = True
```

### Stage 5: Embedding Generation

**Purpose:** Convert chunk text into vector embeddings

**Implementation:** `sia_code/storage/usearch_backend.py`

**Embedding Flow:**
```python
def _embed(self, text: str) -> np.ndarray:
    """Generate embedding for text."""
    # 1. Check cache
    cached = self._embed_cached(text)
    if cached:
        return cached
    
    # 2. Load model (lazy, GPU if available)
    embedder = self._get_embedder()
    
    # 3. Generate embedding
    vector = embedder.encode(text, convert_to_numpy=True)
    
    # 4. Cache result
    self._cache_embedding(text, vector)
    
    return vector
```

**Model Loading (GPU-accelerated):**
```python
def _get_embedder(self):
    """Load embedding model with GPU support."""
    if self._embedder is None:
        from sentence_transformers import SentenceTransformer
        import torch
        
        # Auto-detect device
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        
        # Load model
        self._embedder = SentenceTransformer(
            self.embedding_model,  # BAAI/bge-small-en-v1.5
            device=device
        )
        
        logger.info(f"Loaded {self.embedding_model} on {device.upper()}")
    
    return self._embedder
```

**Embedding Cache:**
```python
@lru_cache(maxsize=1000)
def _embed_cached(self, text: str) -> tuple:
    """Cache embeddings to avoid recomputation."""
    embedder = self._get_embedder()
    vector = embedder.encode(text, convert_to_numpy=True)
    return tuple(vector.tolist())  # Convert to tuple for hashing
```

**Performance:**
- **GPU:** ~100 tokens/second (~10ms per chunk)
- **CPU:** ~20 tokens/second (~50ms per chunk)
- **Model load time:** ~2 seconds (one-time)

### Stage 6: Index Storage

**Purpose:** Store chunks in dual indexes (vector + lexical)

**Implementation:** `sia_code/storage/usearch_backend.py`

**Storage Flow:**
```python
def store_chunks_batch(self, chunks: list[Chunk]) -> list[ChunkId]:
    """Store chunks in both vector and lexical indexes."""
    
    chunk_ids = []
    
    for chunk in chunks:
        # 1. Store in SQLite (metadata + full-text)
        chunk_id = self._store_chunk_metadata(chunk)
        
        # 2. Store in FTS5 (for lexical search)
        self._store_chunk_fts(chunk_id, chunk.code)
        
        # 3. Store in Usearch (vector embedding)
        if self.embedding_enabled:
            vector = self._embed(chunk.code)
            self._store_chunk_vector(chunk_id, vector)
        
        chunk_ids.append(chunk_id)
    
    return chunk_ids
```

**SQLite Storage:**
```sql
-- Chunk metadata
INSERT INTO chunks (
    id, symbol, chunk_type, file_path, 
    start_line, end_line, language, code, metadata
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);

-- Full-text index
INSERT INTO chunks_fts (rowid, code) VALUES (?, ?);
```

**Usearch Storage:**
```python
def _store_chunk_vector(self, chunk_id: int, vector: np.ndarray):
    """Add vector to HNSW index."""
    self.vector_index.add(
        key=chunk_id,           # Numeric ID
        vector=vector,          # 384-dim f16 array
        copy=False              # Zero-copy for performance
    )
```

**Batch Optimization:**
- SQLite uses transactions (commit after batch)
- Usearch adds vectors incrementally
- Memory usage: ~10MB per 1000 chunks

---

## Index File Structure

### Directory Layout

```
.sia-code/
├── vectors.usearch          # Usearch HNSW index
│   ├── Header (metadata)
│   ├── HNSW graph structure
│   └── Vector data (f16 quantized)
│
├── index.db                 # SQLite database
│   ├── chunks               # Metadata table
│   ├── chunks_fts           # FTS5 virtual table
│   └── sqlite_master        # Schema
│
├── cache/                   # Embedding cache
│   └── embeddings.pkl       # Cached embeddings (optional)
│
└── config.json              # Index configuration
    ├── embedding settings
    ├── chunking settings
    └── search settings
```

### Index File Sizes

**huggingface_diffusers (303 files, 8,676 chunks):**

| Component | Hybrid | Lexical-only |
|-----------|--------|--------------|
| vectors.usearch | 7.6 MB | 0 MB |
| index.db | 17.3 MB | 17.3 MB |
| **Total** | **24.9 MB** | **17.3 MB** |

**Size Breakdown:**
- **Vectors:** 8,676 chunks × 384 dims × 2 bytes/dim = ~6.6 MB (+ overhead)
- **SQLite:** Metadata + FTS5 index + overhead = ~17 MB
- **Compression:** f16 quantization saves 50% vs f32

---

## Indexing Performance

### Benchmark: huggingface_diffusers

**Configuration:**
- Files: 303
- Chunks: 8,676
- Lines of code: ~50,000

**Performance:**

| Configuration | Time | Throughput | Index Size |
|--------------|------|------------|------------|
| **Hybrid (GPU)** | 146s | 60 chunks/s | 24.9 MB |
| **Lexical-only** | 69s | 127 chunks/s | 17.3 MB |

**Time Breakdown (Hybrid):**
```
File discovery:     2s   (1%)
Parsing/chunking:   10s  (7%)
Embedding (GPU):    120s (82%)
Storage:            14s  (10%)
---
Total:              146s (100%)
```

**Bottleneck:** Embedding generation on GPU (82% of time)

### Scaling Analysis

**Time complexity:**
- File discovery: O(N files)
- Parsing: O(N files × avg file size)
- Chunking: O(N chunks)
- Embedding: O(N chunks × embedding time)
- Storage: O(N chunks × log N)

**Linear scaling:**
- 2x files → ~2x indexing time
- 2x chunks → ~2x indexing time

**Tested repos (indexing time):**

| Repository | Files | Chunks | Hybrid Time | Lexical Time |
|-----------|-------|--------|-------------|--------------|
| huggingface_evaluate | 178 | 1,573 | 6.9s | 3.5s |
| google_vizier | 227 | 3,743 | 1.5s | 0.8s |
| opendilab_ACE | 415 | 6,382 | 32.0s | 16.0s |
| huggingface_diffusers | 303 | 8,676 | 146.0s | 69.0s |

**Observation:** Indexing time strongly correlates with chunk count.

---

## Configuration Options

### Embedding Configuration

```python
class EmbeddingConfig:
    enabled: bool = True                    # Enable vector embeddings
    model: str = "BAAI/bge-small-en-v1.5"  # Embedding model
    dimensions: int = 384                   # Vector dimensions
```

**Models tested:**
- `BAAI/bge-small-en-v1.5` (384d) - **Recommended**
- `BAAI/bge-base-en-v1.5` (768d) - Better quality, slower
- `sentence-transformers/all-MiniLM-L6-v2` (384d) - Similar performance

### Chunking Configuration

```python
class ChunkingConfig:
    max_chunk_size: int = 1200   # Max characters per chunk
    min_chunk_size: int = 50     # Min characters per chunk
    merge_threshold: float = 0.8 # Merge similarity threshold
    greedy_merge: bool = True    # Use greedy merging
```

**Tuning guidance:**
- **Larger chunks:** Better context, fewer chunks, slower search
- **Smaller chunks:** More granular, more chunks, faster search
- **Sweet spot:** 1200-2000 characters (~15-25 lines)

### Indexing Configuration

```python
class IndexingConfig:
    exclude_patterns: list[str] = [
        "node_modules/", "__pycache__/", ".git/",
        "venv/", ".venv/", "*.pyc"
    ]
    include_patterns: list[str] = ["**/*"]
    max_file_size_mb: int = 5
```

---

## Incremental Indexing

**Current Status:** Full reindex required

**Planned:** Incremental updates based on file modification times

**Future Implementation:**
```python
def update_index(self, changed_files: list[Path]):
    """Update index for changed files only."""
    for file_path in changed_files:
        # 1. Remove old chunks for this file
        old_chunk_ids = self.get_chunks_by_file(file_path)
        self.delete_chunks(old_chunk_ids)
        
        # 2. Reindex file
        new_chunks = self.parse_and_chunk(file_path)
        self.store_chunks(new_chunks)
```

---

## Troubleshooting

### Issue: Indexing Stuck

**Symptom:** Indexing hangs on specific file

**Causes:**
- Large file exceeding memory
- Parser timeout on malformed code
- GPU out of memory

**Solutions:**
```bash
# Skip large files
sia-code config set indexing.max_file_size_mb 2

# Disable embeddings temporarily
sia-code config set embedding.enabled false

# Check logs
sia-code index . --verbose
```

### Issue: Slow Indexing

**Symptom:** Indexing takes >5 minutes for small repo

**Causes:**
- Running on CPU (no GPU)
- Large chunks (embedding time)
- Slow disk I/O

**Solutions:**
```bash
# Check if GPU is being used
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"

# Use lexical-only for speed
sia-code config set embedding.enabled false

# Reduce chunk size
sia-code config set chunking.max_chunk_size 800
```

### Issue: Index Too Large

**Symptom:** Index exceeds 100MB

**Causes:**
- Too many small chunks
- Large codebase
- Duplicate content

**Solutions:**
```bash
# Increase min chunk size (merge more)
sia-code config set chunking.min_chunk_size 100

# Increase merge threshold
sia-code config set chunking.merge_threshold 0.9

# Use lexical-only (smaller)
sia-code config set embedding.enabled false
```

---

## Best Practices

### 1. Use GPU When Available
- 5-10x faster indexing
- Auto-detected by default
- Check with `torch.cuda.is_available()`

### 2. Tune Chunk Size for Your Code
- **Small functions:** Lower max_chunk_size (800-1000)
- **Large classes:** Higher max_chunk_size (1500-2000)
- **Mixed:** Default (1200) works well

### 3. Exclude Non-Code Files
- Add patterns to `exclude_patterns`
- Reduces index size and improves quality
- Examples: `*.min.js`, `dist/`, `build/`

### 4. Reindex After Major Changes
- Large refactors
- Dependency updates
- Language version changes

---

**Document Version:** 2.0  
**Last Updated:** January 22, 2026  
**Status:** Production
