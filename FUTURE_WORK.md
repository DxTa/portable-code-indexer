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

## ~~Priority 5: Embedding Provider Support~~ ✅ COMPLETED (v2.1)

### Implementation Status
✅ **Completed** - OpenAI embeddings re-enabled with automatic fallback.

### Features Delivered

**Configuration:**
```json
{
  "embedding": {
    "enabled": true,
    "provider": "openai",
    "model": "openai-small",
    "api_key_env": "OPENAI_API_KEY",
    "dimensions": 1536
  }
}
```

**Supported Models:**
1. ✅ **OpenAI openai-small** (1536 dims) - Default, balanced
2. ✅ **OpenAI openai-large** (3072 dims) - Higher quality
3. ✅ **bge-small** (384 dims) - Local/offline

**Smart Fallback:**
- Automatically disables embeddings if API key not found
- Logs warning but continues with lexical search
- No crashes or failures

### Future Extensions (Not Required for v2.1)

1. **Ollama** (local, privacy-focused)
   - nomic-embed-text
   - mxbai-embed-large

2. **Local transformers** (offline)
   - sentence-transformers/all-MiniLM-L6-v2
   - Runs entirely offline

3. **Additional features:**
   - `pci reembed` command to update existing chunks
   - Hybrid search weighting configuration

## ~~Priority 6: Multi-Language Support~~ ✅ COMPLETED (v2.2)

### Implementation Status
✅ **Completed** - 8 new languages with full Tree-sitter AST support

### Languages Added (v2.2)
- ✅ **Go** - Functions, methods, structs
- ✅ **Rust** - Functions, structs, impl blocks
- ✅ **Java** - Classes, methods
- ✅ **C** - Functions, structs
- ✅ **C++** - Functions, classes (C++ specific parser)
- ✅ **C#** - Classes, methods
- ✅ **Ruby** - Classes, methods
- ✅ **PHP** - Classes, functions

### Total Supported Languages (v2.2)
**Full AST Support (12):** Python, JavaScript, TypeScript, JSX, TSX, Go, Rust, Java, C, C++, C#, Ruby, PHP

**Generic Concept Extractor:** Handles function/class extraction across C-like languages with common node types (function_declaration, class_declaration, method_definition, etc.)

### Future Language Additions (Not Required)
- Kotlin (already recognized, needs AST extractor)
- Swift (already recognized, needs AST extractor)
- Haskell (already recognized, needs AST extractor)

## ~~Priority 7: CLI Enhancements & Tooling~~ ✅ COMPLETED (v2.3-v2.4)

### Implementation Status

✅ **v2.3.0 - Output Formatting & Config Management**
- 4 output formats: text, json, table, csv
- File export with `--output` flag
- Enhanced config commands: show, path, edit

✅ **v2.4.0 - Interactive Search & Watch Mode**
- Interactive search mode with result navigation
- Watch mode for auto-indexing with debounce
- Live query and export capabilities

### CLI Enhancements (Completed)

```bash
# Interactive search (v2.4)
pci interactive
pci interactive --regex

# Watch mode for auto-indexing (v2.4)
pci index --watch
pci index --watch --debounce 5.0

# Output formats (v2.3)
pci search "query" --format json
pci search "query" --format csv --output results.csv

# Config management (v2.3)
pci config show
pci config edit
```

### Future CLI Enhancements (Not Required)

```bash
# Export/import indices
pci export archive.tar.gz
pci import archive.tar.gz
```

### IDE Plugins (Future Consideration)

- **VSCode Extension:** Inline search, hover definitions
- **Neovim Plugin:** Telescope integration
- **JetBrains Plugin:** Quick documentation lookup

## Priority 8: Performance Optimization

### Benchmark Results (v2.3)

| Operation | Baseline | Optimized | Notes |
|-----------|----------|-----------|-------|
| Index 14 files | 15.2s (0.9 files/s) | 15.2s | Parallel has overhead for small sets |
| Index 100+ files | ~100s | TBD | Parallel should help here |
| Search (lexical) | ~100ms | <50ms | TODO: Optimize BM25 |
| Search (semantic) | ~500ms | <200ms | TODO: Batch embeddings |

### Completed Optimizations (v2.3)

1. ✅ **Parallel Chunking:** ProcessPoolExecutor for file parsing
   - Added `--parallel` flag with `--workers` option
   - Default: disabled (overhead dominates for <100 files)
   - Recommended: Enable for large codebases (100+ files)
   - Bottleneck: Memvid storage serializes in main process

### Remaining Optimization Opportunities

2. **Batch Embeddings:** Group chunks for API efficiency
3. **Caching:** Memoize parser results for unchanged files
4. **Index Sharding:** Split large codebases across indices
5. **Async Storage:** Non-blocking writes to Memvid

## Timeline

| Phase | Focus | Deliverables |
|-------|-------|--------------|
| Phase 1 | Chunk Sidecar | ChunkIndex, query filtering |
| Phase 2 | Compaction | Auto-compact, background jobs |
| Phase 3 | Embeddings | Provider support, re-embed |
| Phase 4 | Scaling | Multi-language, performance |

## Contributing

Contributions welcome! Focus areas:
- Tree-sitter parser additions for new languages
- Embedding provider integrations
- Performance optimizations
