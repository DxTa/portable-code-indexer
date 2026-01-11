# Known Limitations

## ✅ Chunk Accumulation Issue - SOLVED in v2.0!

### Problem (v1.0)
In v1.0, when you modified a file and ran incremental indexing, new chunks were added but old chunks couldn't be removed due to Memvid's append-only architecture. This caused index bloat and stale search results.

### Solution (v2.0)
**v2.0 introduces Chunk Metadata Sidecar** which solves this problem through:

1. **Chunk Tracking** - Maintains `chunk_index.json` tracking which chunks are valid vs stale
2. **Query-Time Filtering** - Automatically filters stale chunks from search results
3. **Index Compaction** - `pci compact` command removes stale chunks from index

### How It Works (v2.0)

```bash
# Initial index: 100 files → 500 chunks
pci index .

# Modify 10 files, run incremental update
pci index --update
# Result: Chunk index tracks:
#   - 490 valid chunks (from 90 unchanged files)
#   - 10 new valid chunks (from modified files)
#   - 10 stale chunks (old versions of modified files)
# Searches automatically filter out the 10 stale chunks!

# Check index health
pci status
# Shows: 500 valid, 10 stale (2% staleness) 🟢 Healthy

# After many modifications
pci status
# Shows: 500 valid, 150 stale (23% staleness) 🟠 Degraded
# Recommendation: Run 'pci compact'

# Compact to remove stale chunks
pci compact
# Rebuilds index with only valid chunks
# Result: 500 total chunks (150 stale removed)
```

### Monitoring Staleness (v2.0)

```bash
pci status
```

Output includes:
- **Total Chunks**: All chunks in index
- **Valid Chunks**: Current, active chunks
- **Stale Chunks**: Outdated chunks from modified files
- **Staleness Ratio**: Percentage of stale chunks
- **Health Status**: 🟢 Healthy / 🟡 Acceptable / 🟠 Degraded / 🔴 Critical

### Managing Staleness (v2.0)

**Option 1: Compaction (Recommended)**
```bash
pci compact  # Compact if >20% stale
pci compact --threshold 0.1  # Compact if >10% stale
pci compact --force  # Force compaction now
```

**Option 2: Clean Rebuild**
```bash
pci index . --clean  # Delete everything and rebuild
```

**When to compact:**
- When `pci status` shows 🟠 Degraded or 🔴 Critical
- When staleness ratio > 20%
- After major refactoring with many file changes

### Technical Details

**Why can't chunks be deleted automatically?**

The Memvid storage backend uses an append-only architecture optimized for fast writes and vector search. It doesn't expose a deletion API for individual documents. This is a common design choice in vector databases to maintain index integrity and performance.

**Future solutions:**

See [FUTURE_WORK.md](FUTURE_WORK.md) for planned enhancements including:
- Chunk metadata sidecar for tracking valid chunks
- Automatic stale chunk detection and warnings
- Query-time filtering of outdated results
- Periodic automatic compaction

## Embedding Limitations

Currently, embeddings are disabled in the storage backend due to OpenAI API quota constraints. This means:

- **Semantic search** falls back to lexical (BM25) search
- **Multi-hop research** uses lexical search only
- Vector similarity features are not available

This limitation will be resolved once embedding providers are configured with appropriate API keys.

## File Size Limits

- Default maximum file size: **10 MB**
- Files larger than this are skipped during indexing
- Configure via `config.json`: `indexing.max_file_size_mb`

## Supported Languages

Tree-sitter parsing is currently configured for:
- Python
- JavaScript/TypeScript
- JSX/TSX

Other languages in the `Language` enum are defined but may not have full parser support yet.
