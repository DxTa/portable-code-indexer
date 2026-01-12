# PCI - Portable Code Index

**v2.4** - Production-grade local-first codebase intelligence with interactive search and watch mode.

## Features

- **cAST Algorithm** - Semantic code chunking via Abstract Syntax Tree
- **Multi-Hop Code Research** - Automatically discovers interconnected code relationships
- **12 Language Support** - Python, JS/TS, Go, Rust, Java, C/C++, C#, Ruby, PHP
- **Interactive Search** (v2.4) - Live search with result navigation and export
- **Watch Mode** (v2.4) - Auto-reindex on file changes with debouncing
- **4 Output Formats** (v2.3) - Text, JSON, table, CSV for any workflow
- **Chunk Metadata Sidecar** - Tracks valid/stale chunks, filters outdated code from results
- **Index Compaction** - `pci compact` removes stale chunks, keeps index healthy
- **Semantic Search** - Natural language queries (requires OpenAI API key)
- **Lexical Search** - Pattern matching without API keys
- **Local-First** - All code stays on your machine
- **Portable** - Single .mv2 file storage (no database required)
- **Performance Metrics** - Real-time indexing throughput tracking

## Installation

### From Wheel File (Recommended)

```bash
# Download the wheel file, then:
pip install portable_code_index-2.4.0-py3-none-any.whl

# Run via module
python -m pci.cli --help
```

### From Source (Development)

```bash
git clone https://github.com/pci-project/portable-code-index.git
cd portable-code-index/pci
pip install -e .
```

### Build Wheel Locally

```bash
pip install build
python -m build --wheel
# Output: dist/portable_code_index-2.4.0-py3-none-any.whl
```

## Quick Start

```bash
# Initialize index in current directory
pci init

# Index your codebase
pci index .

# Incremental re-index (only changed files)
pci index --update

# Clean rebuild (removes everything and rebuilds)
pci index --clean

# Check index health (v2.0)
pci status

# Compact index to remove stale chunks (v2.0)
pci compact

# Search semantically
pci search "find authentication logic"

# Search with regex/lexical
pci search --regex "def.*auth"

# Multi-hop code research
pci research "how does the API handle errors?"

# Output Formats (v2.3)
pci search "query" --format json          # JSON format
pci search "query" --format table         # Rich table format
pci search "query" --format csv           # CSV format (Excel/spreadsheet)
pci search "query" --format text          # Default text format

# Save Results to File (v2.3)
pci search "query" --output results.json --format json
pci search "query" --output results.txt

# Configuration Management (v2.3)
pci config show                           # Display configuration
pci config path                           # Show config file path
pci config edit                           # Open in $EDITOR

# Interactive Search (v2.4)
pci interactive                           # Live search with result navigation
pci interactive --regex                   # Interactive lexical search

# Watch Mode (v2.4)
pci index . --watch                       # Auto-reindex on file changes
pci index . --watch --debounce 5.0        # Custom debounce time (seconds)
```

For comprehensive usage examples, see [EXAMPLES.md](EXAMPLES.md).

## Configuration

Configuration is stored in `.pci/config.json`:

```json
{
  "embedding": {
    "enabled": true,
    "provider": "openai",
    "model": "openai-small",
    "api_key_env": "OPENAI_API_KEY",
    "dimensions": 1536
  },
  "indexing": {
    "exclude_patterns": ["node_modules/", "__pycache__/"],
    "max_file_size_mb": 5
  },
  "chunking": {
    "max_chunk_size": 1200,
    "min_chunk_size": 50
  }
}
```

### Embedding Models

PCI supports multiple embedding providers for semantic search:

| Model | Dimensions | Use Case |
|-------|-----------|----------|
| `openai-small` | 1536 | Default, balanced quality/cost |
| `openai-large` | 3072 | Higher quality, more expensive |
| `bge-small` | 384 | Local/offline, no API key needed |

**Setup for OpenAI models:**
```bash
export OPENAI_API_KEY=sk-your-key-here
pci init
pci index .
```

**For local/offline usage:**
Edit `.pci/config.json`:
```json
{
  "embedding": {
    "enabled": true,
    "provider": "local",
    "model": "bge-small"
  }
}
```

**Automatic Fallback:**
- If `OPENAI_API_KEY` is not set, embeddings are automatically disabled with a warning
- Semantic search (`pci search "query"`) automatically falls back to lexical search
- Explicit lexical search always available: `pci search --regex "pattern"`
- No crashes or failures - just works with reduced functionality

## Supported Languages

### Programming Languages (Full AST Support)
**Actively Parsed:** Python, JavaScript, TypeScript, JSX, TSX, Go, Rust, Java, C, C++, C#, Ruby, PHP

**Recognized:** Kotlin, Groovy, Haskell, Swift, Bash, MATLAB, Makefile, Objective-C, Vue, Svelte, Zig

### Configuration & Markup
JSON, YAML, TOML, HCL, Markdown

### Other
Text files, PDF

**Note:** Languages with "Full AST Support" use Tree-sitter for semantic chunking (functions, classes, methods). Other recognized languages are indexed as text.

## How It Works

1. **Parse** - Tree-sitter generates AST for each file
2. **Extract** - Semantic concepts identified (functions, classes, blocks)
3. **Chunk** - cAST algorithm splits and merges intelligently
4. **Store** - Chunks saved in Memvid .mv2 file with embeddings
5. **Search** - Hybrid semantic + lexical search

## Architecture

- **Storage**: Memvid (single .mv2 file)
- **Parsing**: Tree-sitter
- **Embeddings**: Local (bge-small) or OpenAI/Voyage
- **Search**: Hybrid (BM25 + vector similarity)

## v2.0 - Solved Chunk Accumulation Problem!

PCI v2.0 introduces **Chunk Metadata Sidecar** which solves the chunk accumulation problem:

- ✅ **Automatic Stale Filtering** - Searches automatically exclude outdated chunks
- ✅ **Index Compaction** - `pci compact` removes stale chunks and reduces index size
- ✅ **Health Monitoring** - `pci status` shows staleness metrics and recommendations
- ✅ **Production Ready** - No more unbounded index growth!

See [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) for migration details from v1.0.

## Future Enhancements

See [FUTURE_WORK.md](FUTURE_WORK.md) for planned v2.0 features including:
- Automatic stale chunk detection
- Chunk metadata sidecar
- Index compaction
- Multi-language expansion

## License

MIT
