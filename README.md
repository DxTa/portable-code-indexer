# Sia Code

**v0.2** - Local-first codebase search with semantic understanding and multi-hop code discovery.

## Features

- **Semantic Search** - Natural language queries with OpenAI embeddings (auto-fallback to lexical)
- **Multi-Hop Research** - Automatically discover code relationships and call graphs
- **12 Languages** - Python, JS/TS, Go, Rust, Java, C/C++, C#, Ruby, PHP (full AST support)
- **Interactive Mode** - Live search with result navigation and export
- **Watch Mode** - Auto-reindex on file changes
- **Portable** - Single `.mv2` file storage, no database required

## Installation

```bash
# From PyPI (recommended)
pip install sia-code

# Or with uv
uv tool install sia-code

# Or from source
uv tool install git+https://github.com/DxTa/portable-code-indexer.git

# Verify installation
sia-code --version
```

## Quick Start

```bash
# Initialize and index
sia-code init
sia-code index .

# Search
sia-code search "authentication logic"           # Semantic search
sia-code search --regex "def.*login"             # Regex search

# Multi-hop research (discover relationships)
sia-code research "how does the API handle errors?"

# Check index health
sia-code status
```

## Commands

| Command | Description |
|---------|-------------|
| `sia-code init` | Initialize index in current directory |
| `sia-code index .` | Index codebase (first time) |
| `sia-code index --update` | Re-index only changed files (10x faster) |
| `sia-code index --clean` | Full rebuild from scratch |
| `sia-code index --watch` | Auto-reindex on file changes |
| `sia-code search "query"` | Semantic or regex search |
| `sia-code research "question"` | Multi-hop code discovery with `--graph` |
| `sia-code interactive` | Live search mode with result navigation |
| `sia-code status` | Index health and staleness metrics |
| `sia-code compact` | Remove stale chunks when index grows |
| `sia-code config show` | View configuration |

## Configuration

**Semantic search** requires OpenAI API key (optional):

```bash
export OPENAI_API_KEY=sk-your-key-here
sia-code init
sia-code index .
```

**Without API key:** Searches automatically fallback to lexical/regex mode. No crashes.

**Edit config** at `.sia-code/config.json` to:
- Change embedding model (`openai-small`, `openai-large`, `bge-small`)
- Exclude patterns (`node_modules/`, `__pycache__/`, etc.)
- Adjust chunk sizes

View config: `sia-code config show`

## Output Formats

```bash
sia-code search "query" --format json            # JSON output
sia-code search "query" --format table           # Rich table
sia-code search "query" --format csv             # CSV for Excel
sia-code search "query" --output results.json    # Save to file
```

## Supported Languages

**Full AST Support (12):** Python, JavaScript, TypeScript, JSX, TSX, Go, Rust, Java, C, C++, C#, Ruby, PHP

**Recognized:** Kotlin, Groovy, Swift, Bash, Vue, Svelte, and more (indexed as text)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No API key warning | Normal - searches fallback to lexical mode |
| Index growing large | Run `sia-code compact` to remove stale chunks |
| Slow indexing | Use `sia-code index --update` for incremental |
| Stale search results | Run `sia-code index --clean` to rebuild |

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
