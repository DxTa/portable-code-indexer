# Sia Code

Local-first codebase search with semantic understanding and multi-hop code discovery.

## Benchmark Results

**89.9% Recall@5** on RepoEval benchmark (1,600 queries, 8 repositories)

- **+12.9 percentage points** better than cAST (77.0%)
- **Lexical-only search outperforms hybrid** (BM25 > BM25+embeddings)
- Publication-quality results with ±1.5% confidence interval

See [docs/BENCHMARK_RESULTS.md](docs/BENCHMARK_RESULTS.md) for full analysis.

## Features

- **89.9% Recall@5** - State-of-the-art code search performance on RepoEval benchmark
- **Lexical-First Search** - BM25 + FTS5 optimized for code queries (outperforms semantic-only)
- **Multi-Hop Research** - Automatically discover code relationships and call graphs
- **AST-Aware Chunking** - Tree-sitter preserves function/class boundaries
- **Project Auto-Detection** - Automatic language detection and indexing strategy
- **Tiered Search** - Filter by project code, dependencies, or both
- **12 Languages** - Python, JS/TS, Go, Rust, Java, C/C++, C#, Ruby, PHP (full AST support)
- **Watch Mode** - Auto-reindex on file changes with incremental updates
- **Portable Index** - Usearch HNSW + SQLite FTS5 in `.sia-code/` directory

## Installation

```bash
# From PyPI (recommended)
pip install sia-code

# Or with uv
uv tool install sia-code

# Or from source
uv tool install git+https://github.com/DxTa/sia-code.git

# Try without installing (ephemeral run)
uvx sia-code --version
uvx sia-code search "authentication logic"

# Verify installation
sia-code --version
```

## Quick Start

```bash
# Initialize and index
sia-code init
sia-code index .

# Search
sia-code search "authentication logic"           # Hybrid search (default: BM25 + semantic)
sia-code search --regex "def.*login"             # Lexical-only search (BM25)
sia-code search --semantic-only "handle errors"  # Semantic-only search

# Multi-hop research (discover relationships)
sia-code research "how does the API handle errors?"

# Check index health
sia-code status
```

## Commands

### Core Commands

| Command | Description |
|---------|-------------|
| `sia-code init` | Initialize index in current directory |
| `sia-code init --path PATH` | Initialize in specific directory |
| `sia-code init --dry-run` | Preview project analysis without creating index |
| `sia-code index PATH` | Index codebase (default: current directory `.`) |
| `sia-code index --update` | Re-index only changed files (10x faster) |
| `sia-code index --clean` | Delete existing index and rebuild from scratch |
| `sia-code index --watch` | Auto-reindex on file changes (Ctrl+C to stop) |
| `sia-code index --parallel` | Use parallel processing (best for 100+ files) |
| `sia-code index --workers N` | Number of worker processes (default: CPU count) |
| `sia-code index --debounce N` | Seconds to wait before reindexing (default: 2.0) |
| `sia-code status` | Index health and staleness metrics |
| `sia-code compact` | Remove stale chunks (runs if >20% stale) |
| `sia-code compact --threshold 0.1` | Compact if staleness exceeds threshold (0.1 = 10%) |
| `sia-code compact --force` | Force compaction regardless of staleness ratio |

### Search Commands

| Command | Description |
|---------|-------------|
| `sia-code search "query"` | Hybrid search: BM25 + semantic (default, best results) |
| `sia-code search --regex "pattern"` | Lexical-only search using FTS5 BM25 |
| `sia-code search --semantic-only "query"` | Semantic-only vector search |
| `sia-code search -k N "query"` | Number of results to return (default: 10) |
| `sia-code search --no-deps "query"` | Exclude dependency code from results |
| `sia-code search --deps-only "query"` | Show only dependency code |
| `sia-code search --no-filter "query"` | Include stale chunks (default: filtered) |
| `sia-code search --format json "query"` | Output as JSON (options: text, json, table, csv) |
| `sia-code search -o FILE "query"` | Save results to file instead of stdout |

### Research & Interactive

| Command | Description |
|---------|-------------|
| `sia-code research "question"` | Multi-hop code discovery with relationship mapping |
| `sia-code research --hops N` | Maximum relationship depth (default: 2) |
| `sia-code research -k N` | Results per hop (default: 5) |
| `sia-code research --graph` | Show call graph visualization |
| `sia-code research --no-filter` | Include stale chunks (default: filtered) |
| `sia-code interactive` | Live search mode with result navigation |
| `sia-code interactive --regex` | Interactive mode with lexical search |
| `sia-code interactive -k N` | Number of results per query (default: 10) |

### Configuration

| Command | Description |
|---------|-------------|
| `sia-code config show` | Display current configuration |
| `sia-code config path` | Show configuration file location |
| `sia-code config edit` | Open configuration in $EDITOR |

## Configuration

**Recommended:** Lexical-only search (best performance, no API key needed)

```bash
sia-code init
sia-code index .
# Search uses BM25 by default (89.9% Recall@5)
```

**Optional: Hybrid search** (adds semantic embeddings):

```bash
export OPENAI_API_KEY=sk-your-key-here
sia-code config set embedding.enabled true
sia-code config set search.vector_weight 0.0  # 0.0 = lexical-only (recommended!)
sia-code index --clean
```

**Edit config** at `.sia-code/config.json` to:
- Set `vector_weight` (0.0 = lexical-only, 0.5 = hybrid, 1.0 = semantic-only)
- Change embedding model (`BAAI/bge-small-en-v1.5`, `openai-small`)
- Exclude patterns (`node_modules/`, `__pycache__/`, etc.)
- Adjust chunk sizes (`max_chunk_size`, `min_chunk_size`)

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

1. **Parse** - Tree-sitter generates language-agnostic AST for each file
2. **Chunk** - AST-aware chunking preserves function/class boundaries (max 1200 chars)
3. **Index** - Usearch HNSW (vectors) + SQLite FTS5 (lexical search with BM25)
4. **Store** - Portable `.sia-code/` directory (17-25 MB per repo)
5. **Search** - Lexical-first (BM25) with optional hybrid fusion (RRF)

**Key Innovation:** Lexical-only search (BM25) outperforms hybrid (BM25+embeddings) for code queries because code contains precise identifiers that benefit from exact keyword matching.

## Documentation

### Architecture & Implementation
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design, data structures, and technology stack
- [docs/CODE_STRUCTURE.md](docs/CODE_STRUCTURE.md) - Codebase organization and key classes
- [docs/INDEXING.md](docs/INDEXING.md) - Indexing pipeline and AST-aware chunking
- [docs/QUERYING.md](docs/QUERYING.md) - Search methods and hybrid fusion

### Benchmark Results
- [docs/BENCHMARK_RESULTS.md](docs/BENCHMARK_RESULTS.md) - **89.9% Recall@5** full results and analysis
- [docs/BENCHMARK_METHODOLOGY.md](docs/BENCHMARK_METHODOLOGY.md) - RepoEval benchmark setup
- [docs/PERFORMANCE_ANALYSIS.md](docs/PERFORMANCE_ANALYSIS.md) - Why sia-code outperforms cAST by +12.9 pts

### Usage & Configuration
- [docs/CLI_FEATURES.md](docs/CLI_FEATURES.md) - Complete CLI reference and examples
- [ROADMAP.md](ROADMAP.md) - Future development plans
- [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) - Current limitations and workarounds

## License

MIT
