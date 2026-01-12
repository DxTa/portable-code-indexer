# PCI Roadmap

**Current Version:** 2.4  
**Last Updated:** 2026-01-12

This document tracks remaining development work for PCI.

## Completed Features (v2.0-v2.4)

The following features are fully implemented and working:

### Core Features
- ✅ cAST Semantic Chunking via Tree-sitter
- ✅ 12-Language Support (Python, JS/TS, Go, Rust, Java, C, C++, C#, Ruby, PHP, JSX, TSX)
- ✅ Memvid Storage Backend (.mv2 portable files)
- ✅ Lexical Search (BM25)
- ✅ Semantic Search (OpenAI embeddings with automatic fallback)
- ✅ Multi-hop Code Research

### Index Management (v2.0)
- ✅ Chunk Metadata Sidecar (valid/stale tracking)
- ✅ Query-Time Filtering (excludes stale chunks)
- ✅ Staleness Detection with health metrics
- ✅ Index Compaction (`pci compact`)
- ✅ Incremental Indexing (`pci index --update`)

### CLI Enhancements (v2.3-v2.4)
- ✅ Output Formats: text, json, table, csv
- ✅ File Export (`--output`)
- ✅ Config Management: show, path, edit
- ✅ Interactive Search Mode (`pci interactive`)
- ✅ Watch Mode (`pci index --watch`)
- ✅ Parallel Indexing (`--parallel --workers N`)

---

## Remaining Work

### Priority 1: MCP Server Integration

**Status:** Not Started  
**Effort:** 4-6 hours

Enable LLM agents to use PCI via MCP protocol.

**Deliverables:**
- [ ] Create `pci-mcp-server/` package
- [ ] Expose tools: `search_semantic`, `search_regex`, `code_research`, `get_stats`
- [ ] Integration with OpenCode/Claude
- [ ] Documentation for MCP configuration

### Priority 2: Performance Optimization

**Status:** Partial  
**Effort:** 8-12 hours

Improve indexing and search performance for large codebases.

**Completed:**
- ✅ Parallel chunking (ProcessPoolExecutor)

**Remaining:**
- [ ] Batch embeddings (group chunks for API efficiency)
- [ ] Parser result caching (memoize unchanged files)
- [ ] Index sharding (split large codebases)
- [ ] Async storage (non-blocking Memvid writes)

**Benchmarks:**
| Operation | Current | Target |
|-----------|---------|--------|
| Index 100 files | ~60s | <30s |
| Search (lexical) | ~100ms | <50ms |
| Search (semantic) | ~500ms | <200ms |

### Priority 3: Additional Language Support

**Status:** Optional  
**Effort:** 2-4 hours per language

Languages with enum definitions but no AST extractor yet:
- [ ] Kotlin
- [ ] Swift  
- [ ] Haskell

### Priority 4: IDE Plugins (Future)

**Status:** Not Started  
**Effort:** 20+ hours

- [ ] VSCode Extension
- [ ] Neovim Plugin (Telescope integration)
- [ ] JetBrains Plugin

### Priority 5: Additional CLI Features (Low Priority)

- [ ] Export/import indices (`pci export`, `pci import`)
- [ ] `pci reembed` command (update embeddings for existing chunks)
- [ ] Hybrid search weighting configuration

---

## Contributing

Contributions welcome! Focus areas:
- MCP server implementation
- Performance optimization
- Additional language parsers

See [README.md](README.md) for development setup.
