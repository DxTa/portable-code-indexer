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

| Command | Description |
|---------|-------------|
| `sia-code init` | Initialize index in current directory |
| `sia-code index .` | Index codebase |
| `sia-code index --update` | Re-index changed files only |
| `sia-code index --watch` | Auto-reindex on file changes |
| `sia-code search "query"` | Hybrid search (BM25 + semantic) |
| `sia-code search --regex "pattern"` | Lexical-only search |
| `sia-code search --semantic-only "query"` | Semantic-only search |
| `sia-code research "question"` | Multi-hop code discovery |
| `sia-code status` | Index health and staleness metrics |
| `sia-code compact` | Remove stale chunks |
| `sia-code memory list` | List timeline/changelogs/decisions |
| `sia-code memory changelog` | Generate changelog from git |
| `sia-code memory sync-git` | Import events from git history |
| `sia-code config show` | Display configuration |
| `sia-code interactive` | Live search mode |

**See [docs/CLI_FEATURES.md](docs/CLI_FEATURES.md) for complete command reference with all options and examples.**

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

**Git worktrees:** by default, sia-code auto-detects worktrees and stores a single shared index in the git common dir. You can override with `SIA_CODE_INDEX_SCOPE` or set an explicit path with `SIA_CODE_INDEX_DIR`.

```bash
# Force shared index even outside worktrees
export SIA_CODE_INDEX_SCOPE=shared

# Or disable auto-detection (per-worktree index)
export SIA_CODE_INDEX_SCOPE=worktree

sia-code init
sia-code index .
```

**AI Summarization** (optional, enhances git changelogs):

```json
{
  "summarization": {
    "enabled": true,
    "model": "google/flan-t5-base",
    "max_commits": 20
  }
}
```

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
- [docs/CLI_FEATURES.md](docs/CLI_FEATURES.md) - **Complete CLI reference and examples**
- [examples/](examples/) - Test results and usage examples
- [ROADMAP.md](ROADMAP.md) - Development progress
- [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) - Current limitations and workarounds

## License

MIT
