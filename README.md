# PCI - Portable Code Index

**v2.0** - Production-grade local-first codebase intelligence with automatic stale chunk management.

## Features

- **cAST Algorithm** - Semantic code chunking via Abstract Syntax Tree
- **Multi-Hop Code Research** - Automatically discovers interconnected code relationships
- **Chunk Metadata Sidecar (v2.0)** - Tracks valid/stale chunks, filters outdated code from results
- **Index Compaction (v2.0)** - `pci compact` removes stale chunks, keeps index healthy
- **Semantic Search** - Natural language queries like "find authentication code"
- **Regex/Lexical Search** - Pattern matching without API keys
- **Local-First** - All code stays on your machine
- **30 Languages** - Comprehensive language support via Tree-sitter
- **Portable** - Single .mv2 file storage (no database required)
- **Performance Metrics** - Real-time indexing throughput tracking

## Installation

```bash
pip install -e .
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

If `OPENAI_API_KEY` is not set and OpenAI models are configured, embeddings will automatically fall back to disabled mode. You can still use lexical search with `pci search --regex`.

## Supported Languages

### Programming
Python, JavaScript, TypeScript, JSX, TSX, Java, Kotlin, Groovy, C, C++, C#, Go, Rust, Haskell, Swift, Bash, MATLAB, Makefile, Objective-C, PHP, Vue, Svelte, Zig

### Configuration
JSON, YAML, TOML, HCL, Markdown

### Text
Text files, PDF

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
