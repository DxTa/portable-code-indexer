# Sia-Code Roadmap

**Last Updated:** 2026-01-23

This document tracks development progress and remaining work.

## Completed Features

### Core Features
- [x] AST Semantic Chunking via Tree-sitter
- [x] 12-Language Support (Python, JS/TS, Go, Rust, Java, C, C++, C#, Ruby, PHP, JSX, TSX)
- [x] Usearch + SQLite Backend (portable .sia-code/ directory)
- [x] Lexical Search (BM25 via FTS5)
- [x] Semantic Search (HuggingFace/OpenAI embeddings)
- [x] Hybrid Search (RRF fusion)
- [x] Multi-hop Code Research

### Index Management
- [x] Chunk Metadata Sidecar (valid/stale tracking)
- [x] Query-Time Filtering (excludes stale chunks)
- [x] Staleness Detection with health metrics
- [x] Index Compaction (`sia-code compact`)
- [x] Incremental Indexing (`sia-code index --update`)

### CLI Features
- [x] Output Formats: text, json, table, csv
- [x] File Export (`--output`)
- [x] Config Management: show, path, edit
- [x] Interactive Search Mode (`sia-code interactive`)
- [x] Watch Mode (`sia-code index --watch`)
- [x] Parallel Indexing (`--parallel --workers N`)

### Memory & Git Integration
- [x] Memory System (timeline events, changelogs, decisions)
- [x] Git History Sync (`sia-code memory sync-git`)
- [x] AI-Powered Summarization (google/flan-t5-base)
- [x] Memory CLI Commands (`sia-code memory list/search/changelog`)
- [x] Decision Tracking (add/approve/reject workflow)
- [x] Vector Persistence Bug Fix (usearch view mode)

---

## Remaining Work

### Priority 1: MCP Server Integration

**Status:** Not Started  
**Effort:** 4-6 hours

Enable LLM agents to use sia-code via MCP protocol.

- [ ] Create `sia-code-mcp-server/` package
- [ ] Expose tools: `search_semantic`, `search_regex`, `code_research`, `get_stats`
- [ ] Integration with OpenCode/Claude
- [ ] Documentation for MCP configuration

### Priority 2: Performance Optimization

**Status:** Partial  
**Effort:** 8-12 hours

**Completed:**
- [x] Parallel chunking (ProcessPoolExecutor)

**Remaining:**
- [ ] Batch embeddings (group chunks for API efficiency)
- [ ] Parser result caching (memoize unchanged files)
- [ ] Index sharding (split large codebases)
- [ ] Async storage (non-blocking writes)

**Benchmarks:**
| Operation | Current | Target |
|-----------|---------|--------|
| Index 100 files | ~60s | <30s |
| Search (lexical) | ~100ms | <50ms |
| Search (semantic) | ~500ms | <200ms |

### Priority 3: Additional Language Support

**Status:** Optional  
**Effort:** 2-4 hours per language

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

- [ ] Export/import indices (`sia-code export`, `sia-code import`)
- [ ] `sia-code reembed` command (update embeddings for existing chunks)
- [ ] Hybrid search weighting configuration via CLI

---

## Contributing

Contributions welcome! Focus areas:
- MCP server implementation
- Performance optimization
- Additional language parsers

See [README.md](README.md) for development setup.
