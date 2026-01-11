# Known Limitations

## Chunk Accumulation Issue

### What Happens
When you modify a file and run incremental indexing (`pci index --update`), new chunks are added to the index but **old chunks from the previous version are not removed**. This is because the underlying Memvid storage engine does not support deletion of individual documents.

### Impact
- Index size grows with each modification (not with codebase size)
- Search results may include outdated code from previous file versions
- Over time, search quality may degrade as stale results accumulate

### Example
```bash
# Initial index: 100 files → 500 chunks
pci index .

# Modify 10 files, run incremental update
pci index --update
# Result: 510 chunks (500 old + 10 new)
# The original 10 chunks for those files still exist

# After 10 modifications to same files
# Result: 600 chunks (500 original + 100 from updates)
# Stale percentage: 100/600 = 16%
```

### When This Matters
- Active development with frequent file modifications
- Long-running projects without periodic cleanup
- When search results seem outdated or duplicated
- If index size grows unexpectedly large

### Recommended Workaround

Periodically perform a clean reindex:

```bash
pci index . --clean
```

This deletes the existing index and cache, then rebuilds from scratch.

**Recommended frequency:**
- **Weekly** for active development (frequent code changes)
- **Monthly** for stable projects (occasional updates)
- **After major refactoring** (many files modified)

### Monitoring Staleness

Use `pci status` to check index age and size:

```bash
pci status
```

The status command will warn you if the index is older than 30 days and recommend running `--clean`.

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
