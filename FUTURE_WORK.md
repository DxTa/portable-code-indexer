# Future Work - PCI v2.0

This document outlines planned enhancements to address current limitations and expand PCI's capabilities.

## Priority 1: Chunk Metadata Sidecar

### Problem
Memvid doesn't support deletion, so stale chunks accumulate when files are modified during incremental indexing.

### Solution
Maintain a separate JSON sidecar file tracking which chunks are currently valid:

```json
{
  "chunk_index_version": "1.0",
  "files": {
    "src/api.py": {
      "hash": "abc123...",
      "mtime": 1704067200,
      "valid_chunks": ["chunk-1a2b", "chunk-3c4d"],
      "stale_chunks": ["chunk-old1", "chunk-old2"]
    },
    "src/main.py": {
      "hash": "def456...",
      "mtime": 1704067200,
      "valid_chunks": ["chunk-5e6f"],
      "stale_chunks": []
    }
  }
}
```

### Implementation Plan

1. **Create `ChunkIndex` class** (`pci/indexer/chunk_index.py`):
   - Load/save chunk metadata sidecar
   - Track valid/stale chunks per file
   - Compute staleness metrics

2. **Update `IndexingCoordinator`**:
   - On file change: mark old chunks as stale in sidecar
   - Add new chunks to Memvid and mark valid in sidecar
   - Maintain bidirectional mapping: file ↔ chunks

3. **Add query-time filtering**:
   - `MemvidBackend.search_*()` methods filter results
   - Only return chunks in the "valid" set
   - Transparent to callers - search API unchanged

4. **Add compaction command**:
   ```bash
   pci compact --threshold 0.2
   ```
   - Rebuild index excluding stale chunks when ratio > threshold
   - Atomic swap to new index
   - Update sidecar to clear stale tracking

### Benefits
- Bounded index size (grows with codebase, not edit count)
- No search quality degradation
- Automatic staleness handling
- User control via explicit compaction

### Risks
- Sidecar can drift from reality if corrupted
- Need validation/repair mechanism
- Adds complexity to every index operation

## Priority 2: Automatic Staleness Detection

### Metrics to Track

Add to `pci status`:

```bash
PCI Index Health
┌─────────────────────┬──────────────┐
│ Total Chunks        │ 5,000        │
│ Valid Chunks        │ 3,500        │
│ Stale Chunks        │ 1,500        │
│ Staleness Ratio     │ 30% ⚠️       │
│ Recommendation      │ Run compact  │
└─────────────────────┴──────────────┘
```

### Thresholds

| Staleness | Status | Action |
|-----------|--------|--------|
| 0-10% | 🟢 Healthy | None |
| 10-20% | 🟡 Acceptable | Monitor |
| 20-40% | 🟠 Degraded | Recommend compact |
| 40%+ | 🔴 Critical | Warn + automatic compact offer |

### Automatic Compaction Triggers

```bash
pci index --update --auto-compact
```

- Monitor staleness after each incremental index
- If ratio > 30%, offer to compact
- User can enable automatic background compaction

## Priority 3: Enhanced Query-Time Filtering

### Current Approach (Phase 1)
Simple filter at result return:
```python
def search_lexical(query, k):
    results = memvid.find(query, k=k*2)  # Fetch extra
    valid_results = [r for r in results if r.chunk_id in valid_set]
    return valid_results[:k]
```

**Pros:** Simple, works immediately
**Cons:** Wasteful (fetches 2x results), limited k precision

### Advanced Approach (Phase 2)
Pre-filter at indexing time:
```python
# Store validity bit in metadata
memvid.put(chunk, metadata={"valid": True, ...})

# Query with filter
results = memvid.find(query, k=k, filter="metadata.valid == true")
```

**Pros:** Efficient, precise
**Cons:** Requires Memvid filter support, metadata updates

### Trade-offs

| Approach | Latency | Accuracy | Complexity |
|----------|---------|----------|------------|
| No filter | Fast | Low (returns stale) | Low |
| Post-filter | Medium | High | Low |
| Pre-filter | Fast | High | Medium |
| Compaction | N/A | Perfect | High |

**Recommendation:** Start with post-filter, migrate to pre-filter when Memvid supports it.

## Priority 4: Index Compaction

### Automatic Background Compaction

```bash
# Config option
pci config set compaction.enabled true
pci config set compaction.threshold 0.25
pci config set compaction.schedule "weekly"
```

### Implementation

1. **Detect compaction need:**
   - On `pci index --update`, check staleness ratio
   - If ratio > threshold, schedule compaction

2. **Background compaction process:**
   - Create new index: `.pci/index-new.mv2`
   - Copy only valid chunks (exclude stale)
   - Verify new index integrity
   - Atomic swap: `index.mv2` ← `index-new.mv2`
   - Delete old index

3. **Safety mechanisms:**
   - Lock file prevents concurrent operations
   - Backup old index before deletion
   - Rollback on failure

### Challenges

- **Concurrent access:** Must not interrupt active searches
- **Storage overhead:** Needs 2x space during compaction
- **Time cost:** Full reindex is expensive
- **Atomicity:** Swap must be instant

### Solutions

- Use file rename for atomic swap (POSIX guarantees)
- Check available disk space before starting
- Stream-based compaction to reduce peak memory
- Progress reporting for long operations

## Priority 5: Embedding Provider Support

### Current State
Embeddings disabled due to OpenAI quota limits.

### Planned Support

```json
// config.json
{
  "embedding": {
    "provider": "openai|ollama|local",
    "model": "text-embedding-3-large",
    "api_key_env": "OPENAI_API_KEY",
    "local_model_path": null
  }
}
```

### Providers

1. **OpenAI** (cloud, high quality)
   - text-embedding-3-small (1536 dims)
   - text-embedding-3-large (3072 dims)

2. **Ollama** (local, privacy-focused)
   - nomic-embed-text
   - mxbai-embed-large

3. **Local transformers** (offline)
   - sentence-transformers/all-MiniLM-L6-v2
   - Runs entirely offline

### Migration Path

1. Re-enable embeddings with provider selection
2. Add `pci reembed` command to update existing chunks
3. Support hybrid search (embeddings + BM25)

## Priority 6: Multi-Language Support

### Expand Tree-sitter Parsers

Currently supported:
- ✅ Python
- ✅ JavaScript/TypeScript/JSX/TSX

Planned additions:
- Go
- Rust
- Java
- C/C++
- C#
- Ruby
- PHP

### Implementation

Add language-specific parser configurations in `parser/engine.py`:

```python
# Add to TreeSitterEngine
self.parsers = {
    Language.GO: (ts_go.language(), ts_go.language_go()),
    Language.RUST: (ts_rust.language(), ts_rust.language_rust()),
    # ...
}
```

### Chunking Strategy Customization

Different languages may need different chunking strategies:
- **Python/Ruby:** Class/function-based
- **Go:** Package/function-based
- **C/C++:** Header/implementation separation
- **Java:** Class hierarchy aware

## Priority 7: Integration & Tooling

### MCP Server (Deferred from Roadmap)

Expose PCI via Model Context Protocol for LLM integration:

```bash
pci serve --mcp
# Exposes: code_search, code_research, index_status tools
```

### IDE Plugins

- **VSCode Extension:** Inline search, hover definitions
- **Neovim Plugin:** Telescope integration
- **JetBrains Plugin:** Quick documentation lookup

### CLI Enhancements

```bash
# Interactive search
pci search --interactive

# Watch mode for auto-indexing
pci index --watch

# Export/import indices
pci export archive.tar.gz
pci import archive.tar.gz
```

## Priority 8: Performance Optimization

### Benchmark Targets

| Operation | Current | Target | Notes |
|-----------|---------|--------|-------|
| Index 1k files | ~10s | <5s | Parallel chunking |
| Search (lexical) | ~100ms | <50ms | Optimize BM25 |
| Search (semantic) | ~500ms | <200ms | Batch embeddings |
| Incremental update | ~1s | <500ms | Hash cache only |

### Optimization Strategies

1. **Parallel Chunking:** Use process pool for file parsing
2. **Batch Embeddings:** Group chunks for API efficiency
3. **Caching:** Memoize parser results for unchanged files
4. **Index Sharding:** Split large codebases across indices

## Timeline

| Quarter | Focus | Deliverables |
|---------|-------|--------------|
| Q1 2024 | Chunk Sidecar | ChunkIndex, query filtering |
| Q2 2024 | Compaction | Auto-compact, background jobs |
| Q3 2024 | Embeddings | Provider support, re-embed |
| Q4 2024 | Scaling | Multi-language, performance |

## Contributing

See specific implementation plans in GitHub issues tagged with `v2.0` milestone.

Discussions and proposals welcome in the [Discussions](https://github.com/your-org/pci/discussions) section.
