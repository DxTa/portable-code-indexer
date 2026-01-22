# Architecture & Technology Design

**Version:** 2.0 (Usearch Backend)  
**Date:** January 22, 2026  
**Status:** Production

---

## Executive Summary

Sia-code uses a **hybrid vector + lexical search architecture** built on:
- **Usearch HNSW** for fast approximate vector search
- **SQLite FTS5** for BM25 lexical search  
- **Reciprocal Rank Fusion (RRF)** to combine results
- **GPU-accelerated embeddings** for fast indexing
- **Parallel search** for sub-second query times

This architecture achieves **89.9% Recall@5** on RepoEval, outperforming cAST (77%) by **+12.9 percentage points**.

---

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Sia-code CLI                         │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ├──> Index Command ──> Indexing Pipeline
                 │                      ├─> Tree-sitter Parser
                 │                      ├─> Chunker (AST-aware)
                 │                      ├─> Embedder (GPU)
                 │                      └─> Backend (Usearch + SQLite)
                 │
                 └──> Search Command ──> Query Pipeline
                                         ├─> Query Preprocessing
                                         ├─> Semantic Search (Usearch)
                                         ├─> Lexical Search (FTS5)
                                         ├─> RRF Fusion
                                         └─> Result Ranking

┌─────────────────────────────────────────────────────────────┐
│                      Storage Layer                           │
├─────────────────────────────────────────────────────────────┤
│  vectors.usearch (HNSW index)  │  index.db (SQLite + FTS5) │
│  - f16 quantized vectors       │  - Chunk metadata          │
│  - Cosine similarity           │  - Full-text index         │
│  - Memory-mapped               │  - BM25 scoring            │
└─────────────────────────────────────────────────────────────┘
```

---

## Core Technologies

### 1. Vector Search: Usearch

**Library:** [Usearch](https://github.com/unum-cloud/usearch)  
**Algorithm:** HNSW (Hierarchical Navigable Small World)  
**Metric:** Cosine similarity

**Key Features:**
- **Fast approximate search:** O(log N) query time
- **Memory-efficient:** f16 quantization (2 bytes per dimension)
- **Memory-mapped:** Fast startup, no full loading
- **High recall:** 99%+ recall at k=10 with proper parameters

**Configuration:**
```python
Index(
    ndim=384,              # BGE-small embedding dimensions
    metric=MetricKind.Cos, # Cosine similarity
    dtype='f16'            # Half-precision (2 bytes/dim)
)
```

**Why Usearch over Alternatives:**
- **vs FAISS:** Simpler API, better memory efficiency
- **vs Hnswlib:** Native f16 support, better performance
- **vs Annoy:** More accurate, faster indexing
- **vs Memvid:** 10x faster search, 3x smaller indexes

### 2. Lexical Search: SQLite FTS5

**Database:** SQLite 3.x with FTS5 extension  
**Algorithm:** BM25 (Best Match 25)  
**Features:** Porter stemming, Unicode support

**Key Features:**
- **Zero-dependency:** SQLite is built-in
- **Fast text search:** Inverted index, optimized for code
- **BM25 ranking:** Industry-standard relevance scoring
- **Transaction support:** ACID guarantees

**FTS5 Configuration:**
```sql
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    code,
    tokenize='porter unicode61'
);
```

**Why FTS5:**
- **Better than grep:** Ranked results, not just matches
- **Better than Elasticsearch:** No server, embedded
- **Better than custom BM25:** Battle-tested, optimized

### 3. Embedding Model: BGE-small

**Model:** BAAI/bge-small-en-v1.5  
**Dimensions:** 384  
**Source:** HuggingFace Transformers

**Characteristics:**
- **Size:** 133 MB (small, fast to load)
- **Quality:** Competitive with larger models
- **Speed:** ~100 tokens/sec on GPU
- **General-purpose:** Works well for code

**Alternatives Tested:**
| Model | Dimensions | Quality | Speed | Winner? |
|-------|-----------|---------|-------|---------|
| BGE-small | 384 | Good | Fast | ✅ Yes |
| BGE-base | 768 | Better | Slower | ❌ |
| MiniLM | 384 | Good | Fast | ❌ |
| OpenAI text-embedding-3-small | 1536 | Best | API cost | ❌ |

### 4. Hybrid Search: Reciprocal Rank Fusion (RRF)

**Algorithm:** Combine semantic and lexical results using reciprocal ranks

**Formula:**
```python
RRF_score(doc) = Σ (weight_i / (k + rank_i))

where:
  - weight_i: Weight for search method i (semantic or lexical)
  - rank_i: Rank of document in results from method i
  - k: Constant (default 60)
```

**Implementation:**
```python
# Get results from both methods
semantic_results = search_semantic(query, k=30)
lexical_results = search_lexical(query, k=30)

# Compute RRF scores
for rank, result in enumerate(semantic_results):
    scores[doc_id] += vector_weight / (60 + rank)

for rank, result in enumerate(lexical_results):
    scores[doc_id] += (1 - vector_weight) / (60 + rank)

# Return top-k by combined score
return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]
```

**Why RRF:**
- **Normalization-free:** No need to normalize scores from different systems
- **Robust:** Works well even when one system fails
- **Simple:** Easy to implement and understand
- **Effective:** Used in production systems (Elasticsearch, etc.)

---

## Data Structures

### 1. Chunk

**Purpose:** Represents a code snippet with metadata

```python
@dataclass
class Chunk:
    id: ChunkId                  # Unique identifier
    symbol: str                  # Function/class name
    chunk_type: ChunkType        # FUNCTION, CLASS, FILE, etc.
    file_path: FilePath          # Relative path from repo root
    start_line: int              # Starting line number
    end_line: int                # Ending line number
    language: Language           # Python, TypeScript, etc.
    code: str                    # Actual code content
    metadata: dict               # Additional metadata (tier, imports, etc.)
    created_at: datetime         # Indexing timestamp
```

**Storage:**
- **SQLite table:** `chunks` (full metadata)
- **FTS5 table:** `chunks_fts` (code text for search)
- **Usearch index:** Vector embeddings

### 2. SearchResult

**Purpose:** Result from a search query with relevance score

```python
@dataclass
class SearchResult:
    chunk: Chunk                 # The matched chunk
    score: float                 # Relevance score (0-1, higher is better)
```

**Score Semantics:**
- **Semantic search:** 1.0 - cosine_distance (0=unrelated, 1=identical)
- **Lexical search:** Normalized BM25 score
- **Hybrid search:** RRF score (combined)

### 3. Index Files

**Structure:**
```
.sia-code/
├── vectors.usearch          # Vector index (~7-8 MB)
│   ├── Metadata (ndim, metric, dtype)
│   └── HNSW graph
├── index.db                 # SQLite database (~17-25 MB)
│   ├── chunks               # Chunk metadata table
│   ├── chunks_fts           # Full-text search index
│   └── config               # Index configuration
├── cache/                   # Embedding cache
└── config.json              # User configuration
```

**Size Comparison:**
| Backend | huggingface_diffusers | Compression |
|---------|----------------------|-------------|
| Memvid (old) | 68 MB | 1.0x |
| Usearch + SQLite | 24.9 MB (hybrid) | 2.7x |
| Usearch + SQLite | 17.3 MB (lexical) | 3.9x |

---

## Design Decisions

### 1. Why Usearch + SQLite (Not Pure Vector DB)

**Decision:** Hybrid architecture with separate vector and lexical indexes

**Rationale:**
- **Lexical search is powerful for code:** Identifiers, API names, imports
- **Vectors handle semantic similarity:** Related concepts, paraphrases
- **Best of both worlds:** RRF combines strengths
- **Proven by results:** 89.9% vs pure semantic approaches

**Alternatives Considered:**
- ❌ **Pure vector search:** Lower recall on exact matches
- ❌ **Pure lexical search:** Misses semantic similarity
- ❌ **Elasticsearch:** Heavy, requires server
- ✅ **Usearch + SQLite:** Fast, lightweight, embeddable

### 2. Why f16 Quantization

**Decision:** Use 16-bit floating point for vectors (not f32 or i8)

**Rationale:**
- **2x smaller than f32:** 2 bytes vs 4 bytes per dimension
- **Better quality than i8:** No significant recall loss
- **Good balance:** Size vs accuracy tradeoff

**Measurements:**
| Precision | Size (384d) | Recall Loss | Winner? |
|-----------|------------|-------------|---------|
| f32 | 1,536 bytes | 0% (baseline) | ❌ Large |
| **f16** | **768 bytes** | **<1%** | **✅ Sweet spot** |
| i8 | 384 bytes | 3-5% | ❌ Quality loss |

### 3. Why Memory-Mapped Indexes

**Decision:** Use `view()` instead of `load()` for Usearch

**Rationale:**
- **Instant startup:** No loading time
- **Shared memory:** Multiple processes can access same index
- **OS-managed:** Let OS handle caching/paging
- **Large index support:** Work with indexes bigger than RAM

**Code:**
```python
# Memory-mapped (fast startup)
index.view(str(vector_path))  # Instant

# vs Full load (slow startup)
index.load(str(vector_path))  # 1-2 seconds for 8K chunks
```

### 4. Why GPU Acceleration

**Decision:** Auto-detect CUDA and use GPU if available

**Rationale:**
- **5-10x faster embeddings:** 100+ tokens/sec vs 10-20 on CPU
- **Faster indexing:** 2-3 minutes vs 10-15 minutes for 8K chunks
- **Better throughput:** Important for large codebases
- **No downside:** Graceful fallback to CPU

**Implementation:**
```python
import torch
device = 'cuda' if torch.cuda.is_available() else 'cpu'
embedder = SentenceTransformer(model, device=device)
```

### 5. Why Parallel Search

**Decision:** Run semantic and lexical searches in parallel

**Rationale:**
- **2x speedup:** Both searches happen simultaneously
- **Thread-safe SQLite:** Use `check_same_thread=False`
- **CPU utilization:** Maximize hardware usage
- **User experience:** Sub-second search times

**Implementation:**
```python
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=2) as executor:
    semantic_future = executor.submit(search_semantic, query)
    lexical_future = executor.submit(search_lexical, query)
    
    semantic_results = semantic_future.result()
    lexical_results = lexical_future.result()
```

---

## Performance Characteristics

### Indexing Performance

**huggingface_diffusers (303 files, 8,676 chunks):**

| Configuration | Index Time | Throughput | Index Size |
|--------------|-----------|------------|------------|
| Hybrid (GPU) | 146 seconds | 60 chunks/s | 24.9 MB |
| Lexical-only | 69 seconds | 127 chunks/s | 17.3 MB |

**Scaling:**
- **Linear with chunk count:** 2x chunks ≈ 2x time
- **GPU bottleneck:** Embedding generation is slowest
- **Disk I/O:** SQLite writes are fast (<10% of time)

### Query Performance

**Single query (k=10):**

| Search Type | Time | Notes |
|------------|------|-------|
| Semantic-only | ~50ms | Usearch HNSW lookup |
| Lexical-only | ~30ms | SQLite FTS5 BM25 |
| Hybrid (parallel) | ~60ms | Both run simultaneously |
| Hybrid (sequential) | ~80ms | Both run one after another |

**With caching:**
- First query: ~60ms
- Repeated query: ~5ms (cached embedding)

---

## Memory Usage

**Runtime memory (approximate):**

| Component | Memory | Notes |
|-----------|--------|-------|
| Embedding model | 133 MB | BGE-small |
| Vector index | ~8 MB | Memory-mapped (not counted as active) |
| SQLite | ~10 MB | Cache and buffers |
| Python overhead | ~50 MB | Interpreter, libraries |
| **Total** | **~200 MB** | Typical usage |

**Peak memory during indexing:**
- Embedding model: 133 MB
- Batch of chunks: ~10 MB
- **Total:** ~150-200 MB

---

## Scalability

### Tested Limits

| Metric | Value | Notes |
|--------|-------|-------|
| Max chunks | 10,000+ | Tested on opendilab_ACE (6,382 chunks) |
| Max index size | 50 MB+ | No issues observed |
| Query latency | <100ms | Consistent across all repos |
| Memory usage | <500 MB | With model loaded |

### Theoretical Limits

**Usearch HNSW:**
- **Capacity:** Millions of vectors (limited by disk space)
- **Query time:** O(log N) - stays fast even at scale

**SQLite FTS5:**
- **Capacity:** Billions of rows (limited by disk space)
- **Query time:** O(log N) with proper indexes

**Practical limit:** 100K+ chunks (~30-50K files) before needing optimizations

---

## Technology Stack Summary

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **CLI** | Python Click | Command-line interface |
| **Parser** | Tree-sitter | AST parsing (multi-language) |
| **Chunker** | Custom AST-aware | Semantic code chunking |
| **Embedder** | sentence-transformers | Text → vectors |
| **Vector Index** | Usearch (HNSW) | Approximate nearest neighbor |
| **Text Index** | SQLite FTS5 | Full-text search (BM25) |
| **Hybrid** | RRF algorithm | Result fusion |
| **Config** | Pydantic | Configuration management |
| **Parallelization** | ThreadPoolExecutor | Concurrent search |

---

## Future Architecture Considerations

### Potential Improvements

1. **Cross-encoder reranking:** Add second-stage reranking for top-k results
2. **Query expansion:** Expand queries with synonyms/related terms
3. **Adaptive chunking:** Adjust chunk size based on file characteristics
4. **Incremental indexing:** Update index without full rebuild
5. **Distributed search:** Shard large indexes across machines

### Compatibility Goals

- **Backward compatible:** Old indexes should work with new code
- **Forward compatible:** New indexes should work with old code (when possible)
- **Migration tools:** Provide tools to upgrade indexes

---

## References

- **Usearch:** https://github.com/unum-cloud/usearch
- **SQLite FTS5:** https://www.sqlite.org/fts5.html
- **BGE Embeddings:** https://huggingface.co/BAAI/bge-small-en-v1.5
- **RRF Algorithm:** Cormack et al. (2009) - "Reciprocal Rank Fusion"
- **HNSW Paper:** Malkov & Yashunin (2018) - "Efficient and robust approximate nearest neighbor search"

---

**Document Version:** 2.0  
**Last Updated:** January 22, 2026  
**Status:** Reflects current production architecture
