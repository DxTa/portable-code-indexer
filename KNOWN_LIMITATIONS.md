# Known Limitations

## Current Limitations

### 1. Memvid Append-Only Storage

Memvid uses an append-only architecture that doesn't support direct chunk deletion. This is handled through:

- **Chunk Metadata Sidecar** - Tracks valid vs stale chunks in `chunk_index.json`
- **Query-Time Filtering** - Automatically excludes stale chunks from search results
- **Index Compaction** - `pci compact` rebuilds index with only valid chunks

Run `pci status` to check index health and staleness ratio.

### 2. Embedding API Dependency

Semantic search requires an embedding provider:

- **OpenAI** (default) - Requires `OPENAI_API_KEY` environment variable
- **Local** (bge-small) - Requires `fastembed` which may not be available on all platforms

**Fallback Behavior:** If API key is not set, PCI automatically:
1. Logs a warning
2. Disables embeddings for the session
3. Falls back to lexical (BM25) search

Use `--regex` flag for explicit lexical search without embeddings.

### 3. File Size Limits

- Default maximum file size: **10 MB**
- Files larger than this are skipped during indexing
- Configure via `.pci/config.json`: `indexing.max_file_size_mb`

### 4. Language Support

**Full AST Support (12 languages):**
Python, JavaScript, TypeScript, JSX, TSX, Go, Rust, Java, C, C++, C#, Ruby, PHP

**Recognized but text-only:**
Kotlin, Swift, Haskell, Bash, Vue, Svelte, and others

**Configuration/Markup:**
JSON, YAML, TOML, HCL, Markdown

Languages without Tree-sitter parsers are indexed as plain text chunks.

### 5. No MCP Server Integration

PCI does not yet have an MCP server for LLM agent integration. This is planned for a future release. See [ROADMAP.md](ROADMAP.md).

## Workarounds

### Large Index Size

If your index grows too large:
```bash
pci status          # Check staleness ratio
pci compact         # Remove stale chunks
pci index --clean   # Full rebuild (last resort)
```

### Slow Indexing

For large codebases (100+ files):
```bash
pci index --parallel --workers 4
```

### No Semantic Search

Without API key, use lexical search:
```bash
pci search --regex "function_name"
pci search --regex "class.*Model"
```
