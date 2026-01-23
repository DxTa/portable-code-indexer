# sia-code Examples & Test Results

This directory contains comprehensive test results, usage examples, and demonstrations of sia-code features.

## Test Results

### [CLI_TEST_RESULTS.md](./CLI_TEST_RESULTS.md)
Complete CLI feature testing on Pyramid Web Framework repository:
- **Vector Persistence Bug Fix** - Verified 7,378 vectors persist correctly (12MB)
- **Search Features** - Hybrid, regex, and semantic search tests
- **Research (Multi-Hop)** - 2-hop and 3-hop architectural analysis
- **Memory Features** - Timeline events and changelogs
- **Output Formats** - JSON, table, CSV, and text formats
- **Performance Metrics** - Indexing and search speed benchmarks

**Test Repository:** Pyramid (514 files, 7,378 chunks)  
**Test Date:** 2026-01-23

---

## Quick Command Reference

### Search
```bash
# Hybrid search (BM25 + semantic)
sia-code search "authentication"

# Regex search
sia-code search "class.*View" --regex

# Semantic-only search
sia-code search "route configuration" --semantic-only

# Output formats
sia-code search "query" --format json
sia-code search "query" --format table
```

### Research (Multi-Hop)
```bash
# 2-hop architectural research
sia-code research "how does request routing work?" --hops 2

# Deep 3-hop analysis
sia-code research "how does view registration work?" --hops 3 --limit 8
```

### Memory
```bash
# List timeline events
sia-code memory list --type timeline

# List changelogs
sia-code memory list --type changelog

# Generate markdown changelog
sia-code memory changelog --format markdown
```

### Status
```bash
# Check index health
sia-code status

# Show configuration
sia-code config show
```

---

## Test Summary

| Feature | Status | Performance |
|---------|--------|-------------|
| Vector Persistence | ✅ PASS | 7,378 vectors, 12MB |
| Hybrid Search | ✅ PASS | < 1 second |
| Regex Search | ✅ PASS | < 1 second |
| Semantic Search | ✅ PASS | < 1 second |
| Research (2-hop) | ✅ PASS | ~2-3 seconds |
| Research (3-hop) | ✅ PASS | ~3-4 seconds |
| Memory Timeline | ✅ PASS | Git events extracted |
| Memory Changelog | ✅ PASS | Tag-based changelogs |
| JSON Output | ✅ PASS | Valid JSON |
| Table Output | ✅ PASS | Formatted tables |

---

## Bug Fixes Verified

### Critical: Vector Index Persistence
**Issue:** Vector indexes were being wiped to 0 bytes after git sync operations.

**Root Cause:** `close()` method called `save()` on read-only memory-mapped views.

**Solution:** Added `_is_viewed` and `_modified_after_view` flags to prevent saving unmodified view-mode indexes.

**Verification:**
```bash
$ ls -lh .sia-code/vectors.usearch
-rw-rw-r-- 1 dxta dxta 12M Jan 23 00:04 vectors.usearch  ✅

$ python3 -c "import usearch.index as us; idx = us.Index.restore('.sia-code/vectors.usearch', view=True); print(len(idx))"
7378  ✅
```

**Status:** ✅ FIXED - All vectors persist correctly

---

## Contributing Examples

To add new examples:
1. Create a test directory with a sample repository
2. Run comprehensive tests covering all features
3. Document results in markdown format
4. Include command examples and output samples
5. Add performance metrics
6. Submit PR with test results

---

## License

Same as sia-code project (MIT License)
