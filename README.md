# PCI - Portable Code Index

**v2.4** - Local-first codebase search with semantic understanding and multi-hop code discovery.

## Features

- **Semantic Search** - Natural language queries with OpenAI embeddings (auto-fallback to lexical)
- **Multi-Hop Research** - Automatically discover code relationships and call graphs
- **12 Languages** - Python, JS/TS, Go, Rust, Java, C/C++, C#, Ruby, PHP (full AST support)
- **Interactive Mode** - Live search with result navigation and export
- **Watch Mode** - Auto-reindex on file changes
- **Portable** - Single `.mv2` file storage, no database required

## Installation

```bash
# Try without installing (recommended for first use)
uvx --from git+https://github.com/DxTa/portable-code-indexer.git pci --help

# Install permanently
uv tool install git+https://github.com/DxTa/portable-code-indexer.git

# Verify installation
pci --version
```

## Quick Start

```bash
# Initialize and index
pci init
pci index .

# Search
pci search "authentication logic"           # Semantic search
pci search --regex "def.*login"             # Regex search

# Multi-hop research (discover relationships)
pci research "how does the API handle errors?"

# Check index health
pci status
```

## Commands

| Command | Description |
|---------|-------------|
| `pci init` | Initialize index in current directory |
| `pci index .` | Index codebase (first time) |
| `pci index --update` | Re-index only changed files (10x faster) |
| `pci index --clean` | Full rebuild from scratch |
| `pci index --watch` | Auto-reindex on file changes |
| `pci search "query"` | Semantic or regex search |
| `pci research "question"` | Multi-hop code discovery with `--graph` |
| `pci interactive` | Live search mode with result navigation |
| `pci status` | Index health and staleness metrics |
| `pci compact` | Remove stale chunks when index grows |
| `pci config show` | View configuration |

## Configuration

**Semantic search** requires OpenAI API key (optional):

```bash
export OPENAI_API_KEY=sk-your-key-here
pci init
pci index .
```

**Without API key:** Searches automatically fallback to lexical/regex mode. No crashes.

**Edit config** at `.pci/config.json` to:
- Change embedding model (`openai-small`, `openai-large`, `bge-small`)
- Exclude patterns (`node_modules/`, `__pycache__/`, etc.)
- Adjust chunk sizes

View config: `pci config show`

## Output Formats

```bash
pci search "query" --format json            # JSON output
pci search "query" --format table           # Rich table
pci search "query" --format csv             # CSV for Excel
pci search "query" --output results.json    # Save to file
```

## Supported Languages

**Full AST Support (12):** Python, JavaScript, TypeScript, JSX, TSX, Go, Rust, Java, C, C++, C#, Ruby, PHP

**Recognized:** Kotlin, Groovy, Swift, Bash, Vue, Svelte, and more (indexed as text)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No API key warning | Normal - searches fallback to lexical mode |
| Index growing large | Run `pci compact` to remove stale chunks |
| Slow indexing | Use `pci index --update` for incremental |
| Stale search results | Run `pci index --clean` to rebuild |

## How It Works

1. **Parse** - Tree-sitter generates AST for each file
2. **Chunk** - cAST algorithm creates semantic chunks (functions, classes)
3. **Embed** - Optional OpenAI embeddings for semantic search
4. **Store** - Single portable `.mv2` file with Memvid
5. **Search** - Hybrid BM25 + vector similarity

## Links

- [ROADMAP.md](ROADMAP.md) - Future development plans
- [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) - Current limitations and workarounds

## License

MIT
