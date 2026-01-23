# Query Processing & Search

**Version:** 2.0  
**Date:** January 22, 2026

---

## Overview

The query pipeline processes user queries through semantic and lexical search, combines results using RRF, and returns ranked matches.

**Query Flow:**
```
User Query → Preprocessing → Semantic Search (Usearch) → RRF Fusion → Ranked Results
                         → Lexical Search (FTS5)    ↗
```

**Performance:** ~60ms per query (with parallel search)

---

## Query Processing

### 1. Query Preprocessing

**FTS5 Sanitization** (for lexical search):
```python
def _sanitize_fts5_query(self, query: str) -> str:
    """Extract FTS5-safe tokens from query."""
    import re
    # Extract identifiers (avoid FTS5 special chars)
    tokens = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b', query)
    # Remove duplicates, limit to top 20
    unique = list(dict.fromkeys(tokens))[:20]
    return ' OR '.join(unique)
```

**Code Query Preprocessing** (optional):
```python
def _preprocess_code_query(self, code: str) -> str:
    """Extract searchable terms from code snippet."""
    # Extract CamelCase, snake_case identifiers
    # Extract API calls (model.from_pretrained)
    # Remove noise, prioritize meaningful terms
    return ' '.join(search_terms[:30])
```

---

## Search Methods

### 1. Semantic Search (Usearch HNSW)

**Purpose:** Find semantically similar code

```python
def search_semantic(self, query: str, k: int = 10) -> list[SearchResult]:
    """Vector similarity search."""
    # 1. Embed query (cached if repeated)
    query_vector = self._embed(query)
    
    # 2. Search HNSW index
    matches = self.vector_index.search(query_vector, k)
    
    # 3. Convert to results
    results = []
    for key, distance in zip(matches.keys, matches.distances):
        chunk = self.get_chunk(str(key))
        score = 1.0 - float(distance)  # Cosine → similarity
        results.append(SearchResult(chunk=chunk, score=score))
    
    return results
```

**Performance:** ~50ms for k=10

### 2. Lexical Search (SQLite FTS5)

**Purpose:** Find exact keyword matches

```python
def search_lexical(self, query: str, k: int = 10) -> list[SearchResult]:
    """BM25 full-text search."""
    # 1. Sanitize query
    sanitized = self._sanitize_fts5_query(query)
    
    # 2. FTS5 search
    cursor.execute("""
        SELECT chunks.id, bm25(chunks_fts) as rank
        FROM chunks_fts
        JOIN chunks ON chunks.id = chunks_fts.rowid
        WHERE chunks_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """, (sanitized, k))
    
    # 3. Convert to results
    results = []
    for row in cursor.fetchall():
        chunk = self.get_chunk(str(row['id']))
        score = abs(float(row['rank'])) / 100.0  # Normalize BM25
        results.append(SearchResult(chunk=chunk, score=score))
    
    return results
```

**Performance:** ~30ms for k=10

### 3. Hybrid Search (RRF Fusion)

**Purpose:** Combine semantic and lexical results

```python
def search_hybrid(
    self, 
    query: str, 
    k: int = 10,
    vector_weight: float = 0.7,
    parallel: bool = True
) -> list[SearchResult]:
    """Hybrid search with Reciprocal Rank Fusion."""
    
    # 1. Run both searches (parallel or sequential)
    fetch_k = k * 3  # Get more candidates for fusion
    
    if parallel:
        # Run simultaneously (2x speedup)
        with ThreadPoolExecutor(max_workers=2) as executor:
            sem_future = executor.submit(self.search_semantic, query, fetch_k)
            lex_future = executor.submit(self.search_lexical, query, fetch_k)
            semantic_results = sem_future.result()
            lexical_results = lex_future.result()
    else:
        semantic_results = self.search_semantic(query, fetch_k)
        lexical_results = self.search_lexical(query, fetch_k)
    
    # 2. Compute RRF scores
    scores = {}
    k_rrf = 60  # RRF constant
    
    # Add semantic scores
    for rank, result in enumerate(semantic_results):
        chunk_id = result.chunk.id
        scores[chunk_id] = scores.get(chunk_id, 0) + vector_weight / (k_rrf + rank)
    
    # Add lexical scores
    lexical_weight = 1.0 - vector_weight
    for rank, result in enumerate(lexical_results):
        chunk_id = result.chunk.id
        scores[chunk_id] = scores.get(chunk_id, 0) + lexical_weight / (k_rrf + rank)
    
    # 3. Sort and return top-k
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]
    return [SearchResult(chunk=get_chunk(cid), score=score) for cid, score in ranked]
```

**Performance:** ~60ms for k=10 (parallel)

---

## Hybrid Weight Tuning

**`vector_weight` parameter:**
- `0.0` = Lexical-only (BM25)
- `0.5` = Balanced (50% semantic, 50% lexical)
- `0.7` = Default (70% semantic, 30% lexical)
- `1.0` = Semantic-only (vector search)

**Benchmark results:**
| Weight | Recall@5 | Use Case |
|--------|----------|----------|
| 0.0 (lexical) | 89.9% | Code with specific identifiers |
| 0.3 | 80.0% | Mixed queries |
| 0.5 | 89.1% | Balanced |
| 0.7 | 85.0% | Semantic emphasis |

**Recommendation:** Use 0.0 (lexical-only) or 0.5 (balanced) for best results.

---

## Advanced Features

### 1. Query Embedding Cache

**Purpose:** Avoid re-embedding repeated queries

```python
@lru_cache(maxsize=1000)
def _embed_cached(self, text: str) -> tuple:
    """Cache query embeddings."""
    embedder = self._get_embedder()
    vector = embedder.encode(text)
    return tuple(vector.tolist())
```

**Benefit:** ~50% speedup for repeated queries

### 2. Result Caching

**Purpose:** Cache full search results

```python
def search_hybrid(self, query: str, k: int = 10, use_cache: bool = False):
    """Search with optional result caching."""
    cache_key = f"{query}:{k}:{vector_weight}"
    
    if use_cache and cache_key in self._search_cache:
        return self._search_cache[cache_key]
    
    # ... perform search ...
    
    if use_cache:
        self._search_cache[cache_key] = results
        # FIFO eviction when cache > 500 entries
        if len(self._search_cache) > 500:
            oldest_keys = list(self._search_cache.keys())[:100]
            for key in oldest_keys:
                del self._search_cache[key]
    
    return results
```

### 3. File-Level Aggregation

**Purpose:** Return ranked files instead of chunks

```python
def search_files(self, query: str, k: int = 10) -> list[tuple[str, float]]:
    """Aggregate chunk results at file level."""
    # Get more chunks
    chunk_results = self.search_hybrid(query, k=k*5)
    
    # Group by file
    file_scores = {}
    for result in chunk_results:
        file_path = str(result.chunk.file_path)
        if file_path not in file_scores:
            file_scores[file_path] = []
        file_scores[file_path].append(result.score)
    
    # Aggregate (sum or max)
    ranked_files = [(f, sum(scores)) for f, scores in file_scores.items()]
    ranked_files.sort(key=lambda x: x[1], reverse=True)
    
    return ranked_files[:k]
```

**Used in:** RepoEval benchmark (file-level Recall@5)

---

## Query Performance

**Single query timing breakdown:**
```
Embedding (GPU, cached):     5ms
Semantic search (Usearch):   50ms
Lexical search (FTS5):       30ms
RRF fusion:                  10ms
---
Total (parallel):            ~60ms
Total (sequential):          ~95ms
```

**Throughput:**
- Single-threaded: ~15 queries/second
- With caching: ~100 queries/second (repeated queries)

---

## Configuration

```python
class SearchConfig:
    default_limit: int = 10
    vector_weight: float = 0.7      # Hybrid weight
    multi_hop_enabled: bool = True  # (Future feature)
    max_hops: int = 2               # (Future feature)
```

**Tuning:**
- Lower `vector_weight` for code queries (0.0-0.5)
- Higher `vector_weight` for natural language (0.7-1.0)
- Increase `default_limit` for broader search

---

**Document Version:** 2.0  
**Last Updated:** January 22, 2026
