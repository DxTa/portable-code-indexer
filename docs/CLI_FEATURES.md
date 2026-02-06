# CLI Features

Complete guide to sia-code command-line interface, including all commands, options, and usage examples.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Command Reference](#command-reference)
  - [init](#init---initialize-index)
  - [index](#index---build-index)
  - [search](#search---query-code)
  - [research](#research---multi-hop-exploration)
  - [status](#status---check-index-health)
  - [compact](#compact---remove-stale-chunks)
  - [memory](#memory---project-memory)
  - [config](#config---manage-configuration)
- [Configuration](#configuration)
- [Advanced Features](#advanced-features)
- [Migration Guide](#migration-guide)

---

## Installation

```bash
# Install from source
cd /path/to/sia-code
pip install -e .

# Or with pip (when published)
pip install sia-code

# Verify installation
sia-code --version
```

**Requirements:**
- Python 3.10+
- 4GB+ RAM (8GB+ recommended for large codebases)
- GPU optional (5-10x faster indexing with CUDA)

---

## Quick Start

```bash
# 1. Initialize in your project
cd /path/to/project
sia-code init

# 2. Index your codebase
sia-code index .

# 3. Search
sia-code search "authentication middleware"

# 4. Check index status
sia-code status
```

---

## Command Reference

### `init` - Initialize Index

Create a new sia-code index in the current directory.

**Usage:**
```bash
sia-code init [OPTIONS]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--path PATH` | Directory to initialize | `.` (current directory) |
| `--dry-run` | Preview project analysis without creating index | `false` |

**Environment variables:**

| Variable | Description |
|----------|-------------|
| `SIA_CODE_INDEX_DIR` | Override the index directory (absolute or project-relative) |
| `SIA_CODE_INDEX_SCOPE` | Set to `shared` to reuse one index across git worktrees |

**Examples:**

```bash
# Initialize in current directory
sia-code init

# Initialize in specific directory
sia-code init --path /path/to/project

# Dry run (preview project analysis)
sia-code init --dry-run
```

**What it does:**

1. **Analyzes project structure:**
   - Detects primary programming languages
   - Identifies dependencies (requirements.txt, package.json, etc.)
   - Finds documentation files
   - Determines recommended search strategy

2. **Creates index directory:**
   - `config.json` - Configuration with auto-detected settings
   - `vectors.usearch` - HNSW vector index (created empty)
   - `index.db` - SQLite database with FTS5 (created empty)
   - `cache/` - Directory for embedding cache

3. **Displays project profile:**
   ```
   Project Analysis
     Languages: Python, TypeScript
     Multi-language: yes
     Has dependencies: yes
     Has documentation: yes
     Recommended strategy: weighted
   ```

**Auto-Detection:**

The `init` command automatically detects:
- **Languages:** Based on file extensions and patterns
- **Dependencies:** `requirements.txt`, `package.json`, `go.mod`, `Cargo.toml`, etc.
- **Documentation:** `*.md`, `*.rst`, `docs/` directory
- **Search strategy:** Weighted (multi-language) or Non-dominated (single-language)

---

### `index` - Build Index

Index codebase files for search.

**Usage:**
```bash
sia-code index [PATH] [OPTIONS]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `PATH` | Path to index | `.` (current directory) |
| `--update` | Incremental indexing (changed files only) | `false` |
| `--clean` | Delete existing index and rebuild from scratch | `false` |
| `--parallel` | Use parallel processing (best for 100+ files) | `false` |
| `--workers N` | Number of worker processes | CPU count |
| `--watch` | Watch for file changes and auto-reindex | `false` |
| `--debounce SECONDS` | Wait time before reindexing after changes | `2.0` |
| `-v, --verbose` | Enable verbose logging | `false` |

**Examples:**

```bash
# Full index (first time)
sia-code index .

# Incremental update (changed files only)
sia-code index --update

# Clean rebuild
sia-code index --clean

# Parallel indexing (faster for large codebases)
sia-code index --parallel --workers 8

# Watch mode (auto-reindex on changes)
sia-code index --watch --debounce 3.0

# Verbose output (show skipped files, errors)
sia-code -v index .
```

**Indexing Modes:**

1. **Full Index** (default):
   - Indexes all files from scratch
   - Use for first-time indexing or after major changes
   - Progress bar shows files/chunks processed

2. **Incremental Update** (`--update`):
   - Checks file hashes to detect changes
   - Only re-indexes modified files
   - 10-100x faster for small changes
   - Maintains chunk index for staleness tracking

3. **Clean Rebuild** (`--clean`):
   - Deletes existing index and cache
   - Performs full reindex
   - Use after configuration changes or corruption

4. **Parallel Indexing** (`--parallel`):
   - Processes multiple files concurrently
   - Best for 100+ files
   - Uses CPU cores for parsing and chunking
   - GPU still used for embeddings (shared across workers)

5. **Watch Mode** (`--watch`):
   - Monitors file system for changes
   - Auto-triggers incremental reindex
   - Debounces rapid changes (default: 2 seconds)
   - Press Ctrl+C to stop

**Performance:**

| Codebase Size | Indexing Time (GPU) | Indexing Time (CPU) |
|---------------|---------------------|---------------------|
| Small (100 files) | 10-30 seconds | 30-60 seconds |
| Medium (1,000 files) | 2-5 minutes | 10-15 minutes |
| Large (10,000 files) | 20-40 minutes | 60-120 minutes |

**What gets indexed:**

- **Included:**
  - Source code (`.py`, `.ts`, `.js`, `.go`, `.rs`, `.java`, `.cpp`, `.c`, `.cs`, `.rb`, `.php`)
  - Documentation (`.md`, `.rst`, `.txt`)
  - Type definitions (`.pyi`, `.d.ts`)

- **Excluded (configurable in config.json):**
  - `node_modules/`, `__pycache__/`, `.git/`, `venv/`, `.venv/`
  - Binary files
  - Files > 5 MB (configurable)
  - Minified files

**Output Example:**

```
Indexing /home/user/project...
████████████████████████████████ 303/303 files [00:45]

✓ Indexing complete
  Files indexed: 303
  Files skipped: 12
    - Unsupported language: 5
    - Too large (>5MB): 3
    - Parse errors: 4
  Total chunks: 8,676

Performance:
  Duration: 45.3s
  Throughput: 6.7 files/s, 191.5 chunks/s
  Processed: 1.8 MB/s
```

---

### `search` - Query Code

Search the indexed codebase.

**Usage:**
```bash
sia-code search QUERY [OPTIONS]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--regex` | Lexical-only search (FTS5 BM25) | `false` (hybrid) |
| `--semantic-only` | Semantic-only search (vector similarity) | `false` (hybrid) |
| `-k, --limit N` | Number of results to return | `10` |
| `--no-filter` | Disable stale chunk filtering | `false` |
| `--no-deps` | Exclude dependency code from results | `false` |
| `--deps-only` | Show only dependency code | `false` |
| `--format FORMAT` | Output format: `text`, `json`, `table`, `csv` | `text` |
| `-o, --output FILE` | Save results to file | stdout |

**Search Modes:**

1. **Hybrid (default)** - Best for most queries:
   ```bash
   sia-code search "user authentication"
   ```
   - Combines BM25 lexical + semantic vector search
   - Uses Reciprocal Rank Fusion (RRF) to merge results
   - **Recommendation:** Use `vector_weight=0.0` in config for best results (lexical-only)

2. **Lexical-only** (`--regex`):
   ```bash
   sia-code search --regex "def authenticate"
   ```
   - BM25 full-text search with FTS5
   - Best for exact function/class names
   - 89.9% Recall@5 on RepoEval benchmark

3. **Semantic-only** (`--semantic-only`):
   ```bash
   sia-code search --semantic-only "handle user login"
   ```
   - Vector similarity search only
   - Good for conceptual queries
   - Not recommended for precise code search

**Examples:**

```bash
# Basic search (hybrid)
sia-code search "authentication middleware"

# Lexical search (exact matches)
sia-code search --regex "class User"

# Semantic search (conceptual)
sia-code search --semantic-only "error handling patterns"

# More results
sia-code search "database connection" -k 20

# Exclude dependencies
sia-code search --no-deps "logging setup"

# Show only dependencies
sia-code search --deps-only "requests.get"

# JSON output
sia-code search --format json "api endpoint" > results.json

# Table format
sia-code search --format table "authentication"

# CSV export
sia-code search --format csv "error handling" -o results.csv
```

**Output Formats:**

1. **Text (default):**
   ```
   Searching (hybrid)...

   1. src/auth/middleware.py:45-67 (score: 0.892)
      authenticate_request
      ────────────────────────────────────────
      def authenticate_request(request):
          """Verify JWT token in request headers."""
          token = request.headers.get('Authorization')
          ...

   2. src/auth/utils.py:12-28 (score: 0.765)
      verify_token
      ────────────────────────────────────────
      def verify_token(token):
          """Validate JWT token and extract claims."""
          ...
   ```

2. **JSON:**
   ```json
   {
     "query": "authentication middleware",
     "mode": "hybrid",
     "results": [
       {
         "file": "src/auth/middleware.py",
         "start_line": 45,
         "end_line": 67,
         "symbol": "authenticate_request",
         "score": 0.892,
         "code": "def authenticate_request(request): ..."
       }
     ]
   }
   ```

3. **Table:**
   ```
   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┓
   ┃ File                      ┃ Line  ┃ Symbol              ┃ Score ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━┩
   │ src/auth/middleware.py    │ 45-67 │ authenticate_request│ 0.892 │
   │ src/auth/utils.py         │ 12-28 │ verify_token        │ 0.765 │
   └───────────────────────────┴───────┴─────────────────────┴───────┘
   ```

4. **CSV:**
   ```csv
   File,Start Line,End Line,Symbol,Score,Preview
   src/auth/middleware.py,45,67,authenticate_request,0.892,"def authenticate_request(request):..."
   src/auth/utils.py,12,28,verify_token,0.765,"def verify_token(token):..."
   ```

**Filtering:**

- **Stale chunks** (default: filtered):
  - Chunks from deleted/moved files are excluded
  - Use `--no-filter` to include all chunks

- **Dependencies** (default: included):
  - `--no-deps`: Exclude stdlib and third-party code
  - `--deps-only`: Show only dependency code

**Configuration Impact:**

The `vector_weight` setting in `.sia-code/config.json` controls hybrid search:

```json
{
  "search": {
    "vector_weight": 0.0  // 0.0 = lexical-only (RECOMMENDED!)
  }
}
```

- `0.0` - Lexical-only (89.9% Recall@5) **← Best for code**
- `0.5` - Balanced hybrid (89.1% Recall@5)
- `1.0` - Semantic-only (not recommended)

---

### `config` - Manage Configuration

View and modify sia-code configuration.

**Usage:**
```bash
sia-code config get KEY
sia-code config set KEY VALUE
sia-code config show
```

**Examples:**

```bash
# Show all configuration
sia-code config show

# Get specific value
sia-code config get search.vector_weight

# Set value
sia-code config set search.vector_weight 0.0
sia-code config set chunking.max_chunk_size 1500
```

**Key Configuration Options:**

```json
{
  "embedding": {
    "enabled": true,
    "model": "BAAI/bge-small-en-v1.5",
    "dimensions": 384
  },
  "search": {
    "vector_weight": 0.0,        // 0.0 = lexical-only (best!)
    "default_limit": 10,
    "include_dependencies": true
  },
  "chunking": {
    "max_chunk_size": 1200,      // Max characters per chunk
    "min_chunk_size": 50,        // Min characters per chunk
    "merge_threshold": 0.8,      // Greedy merge threshold
    "greedy_merge": true         // Enable chunk merging
  },
  "indexing": {
    "max_file_size_mb": 5,       // Skip files larger than this
    "exclude_patterns": [
      "node_modules/",
      "__pycache__/",
      ".git/",
      "venv/"
    ]
  }
}
```

---

### `status` - Check Index Health

Check index health and staleness.

**Usage:**
```bash
sia-code status
```

**Output:**

```
Index Health Status

  Health: 🟢 Healthy
  Staleness Ratio: 2.3%

  Chunks:
    Valid: 8,476 (97.7%)
    Stale: 200 (2.3%)

  Recommendation:
    ✓ Index is healthy
    Consider running 'sia-code index --update' if staleness > 20%
```

**Health Indicators:**

- 🟢 **Healthy:** Staleness < 10%
- 🟡 **Degraded:** Staleness 10-20%
- 🔴 **Poor:** Staleness > 20%

---

### `compact` - Remove Stale Chunks

Remove stale chunks from the index to reduce size and improve search quality.

**Usage:**
```bash
sia-code compact [OPTIONS]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--threshold FLOAT` | Staleness ratio to trigger compaction | `0.2` (20%) |
| `--force` | Force compaction regardless of staleness | `false` |

**Examples:**

```bash
# Compact if >20% stale (default)
sia-code compact

# Compact if >10% stale
sia-code compact --threshold 0.1

# Force compaction regardless
sia-code compact --force
```

**When to use:**
- Index health shows 🟡 Degraded or 🔴 Poor
- After deleting many files
- Before sharing index with team

---

### `memory` - Project Memory

Manage project memory including timeline events, changelogs, and technical decisions.

**Usage:**
```bash
sia-code memory [COMMAND] [OPTIONS]
```

**Subcommands:**

| Command | Description |
|---------|-------------|
| `list` | List memory items (decisions, timeline, changelogs) |
| `changelog` | Generate changelog from memory |
| `search` | Search project memory |
| `sync-git` | Import timeline events and changelogs from git |
| `timeline` | Show project timeline events |
| `add-decision` | Add a pending technical decision |
| `approve` | Approve a pending decision |
| `reject` | Reject a pending decision |
| `export` | Export memory to JSON file |
| `import` | Import memory from JSON file |

#### `memory list`

List memory items by type.

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--type TYPE` | Filter by type: `timeline`, `changelog`, `decision` | all |
| `--limit N` | Maximum items to show | `10` |
| `--status STATUS` | Filter decisions: `pending`, `approved`, `rejected` | all |

**Examples:**

```bash
# List all timeline events
sia-code memory list --type timeline

# List changelogs
sia-code memory list --type changelog --limit 20

# List pending decisions
sia-code memory list --type decision --status pending
```

#### `memory changelog`

Generate changelog from stored memory.

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--format FORMAT` | Output format: `text`, `json`, `markdown` | `text` |
| `-o, --output FILE` | Save to file | stdout |
| `RANGE` | Tag range (e.g., `v1.0.0..v2.0.0`) | all |

**Examples:**

```bash
# Generate markdown changelog
sia-code memory changelog --format markdown

# Export to file
sia-code memory changelog --format markdown -o CHANGELOG.md

# Specific tag range
sia-code memory changelog v1.0.0..v2.0.0
```

#### `memory sync-git`

Import timeline events and changelogs from git history.

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--limit N` | Maximum events to import | `50` |
| `--since DATE` | Only events after date | none |

**Examples:**

```bash
# Sync all git history
sia-code memory sync-git

# Sync last 100 events
sia-code memory sync-git --limit 100
```

#### `memory search`

Search project memory.

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--limit N` | Maximum results | `10` |

**Examples:**

```bash
# Search for authentication-related items
sia-code memory search "authentication"

# Search with more results
sia-code memory search "database migration" --limit 20
```

#### `memory add-decision`

Add a pending technical decision for tracking.

**Examples:**

```bash
# Add a decision
sia-code memory add-decision "Migrate from REST to GraphQL"

# Approve decision ID 1
sia-code memory approve 1

# Reject decision ID 2
sia-code memory reject 2
```

#### `memory export/import`

Export and import memory for backup or sharing.

**Examples:**

```bash
# Export to JSON
sia-code memory export memory-backup.json

# Import from JSON
sia-code memory import memory-backup.json
```

---

### `research` - Multi-Hop Exploration

Perform multi-hop code exploration (advanced feature).

**Usage:**
```bash
sia-code research QUESTION [OPTIONS]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--hops N` | Maximum relationship hops | `2` |
| `-k, --limit N` | Results per hop | `5` |
| `--graph` | Show call graph visualization | `false` |
| `--no-filter` | Include stale chunks | `false` |

**Examples:**

```bash
# Basic research
sia-code research "authentication flow"

# More hops for deeper analysis
sia-code research "database connection" --hops 3

# More results per hop
sia-code research "error handling" --limit 10

# Show call graph
sia-code research "what calls the indexer?" --graph
```

**How it works:**

1. **Initial search:** Find relevant chunks
2. **Hop 1:** Find related code (imports, calls, definitions)
3. **Hop 2:** Expand to connected components
4. **Result:** Complete architectural map

---

## Configuration

### Configuration File

**Location:** `.sia-code/config.json`

**Structure:**

```json
{
  "embedding": {
    "enabled": true,
    "model": "BAAI/bge-small-en-v1.5",
    "dimensions": 384
  },
  "indexing": {
    "exclude_patterns": [
      "node_modules/",
      "__pycache__/",
      ".git/",
      "venv/",
      ".venv/",
      "*.pyc"
    ],
    "max_file_size_mb": 5
  },
  "chunking": {
    "max_chunk_size": 1200,
    "min_chunk_size": 50,
    "merge_threshold": 0.8,
    "greedy_merge": true
  },
  "search": {
    "vector_weight": 0.0,
    "default_limit": 10,
    "include_dependencies": true,
    "tier_boost": {
      "project": 1.0,
      "dependency": 0.7,
      "stdlib": 0.5
    }
  },
  "dependencies": {
    "enabled": true,
    "index_stubs": true,
    "languages": ["python", "typescript", "javascript"]
  },
  "summarization": {
    "enabled": true,
    "model": "google/flan-t5-base",
    "max_commits": 20
  }
}
```

### Environment Variables

**Optional:**

- `OPENAI_API_KEY` - For OpenAI embedding models (if using)
- `CUDA_VISIBLE_DEVICES` - Control GPU selection

---

## Advanced Features

### Incremental Indexing

**How it works:**

1. Computes SHA-256 hash of each file
2. Stores hashes in `.sia-code/cache/file_hashes.json`
3. On `--update`, checks hashes to detect changes
4. Only re-indexes modified files

**Benefits:**

- 10-100x faster for small changes
- Maintains chunk index for staleness tracking
- Tracks file moves and deletions

**Example:**

```bash
# First index
sia-code index .  # Takes 5 minutes

# Make small changes to 3 files
# ... edit files ...

# Incremental update
sia-code index --update  # Takes 10 seconds!
```

### Watch Mode

**Use case:** Development workflow with auto-reindex

**Setup:**

```bash
# Start watch mode
sia-code index --watch --debounce 3.0
```

**Behavior:**

- Monitors file system for code file changes (`.py`, `.js`, `.ts`, etc.)
- Debounces rapid changes (waits 3 seconds after last change)
- Auto-triggers incremental reindex
- Shows notification on completion

**Press Ctrl+C to stop**

### Parallel Indexing

**When to use:**

- Large codebases (100+ files)
- Multi-core machines
- Initial indexing (not incremental)

**Example:**

```bash
# Use all CPU cores
sia-code index --parallel

# Limit workers
sia-code index --parallel --workers 4
```

**Performance:**

- 2-4x faster for CPU-bound parsing
- GPU still shared (embeddings run sequentially)
- Diminishing returns beyond 8 workers

### Dependency Filtering

**Tiers:**

- `project` - Your source code (boost: 1.0)
- `dependency` - Third-party libraries (boost: 0.7)
- `stdlib` - Standard library (boost: 0.5)

**Configuration:**

```json
{
  "search": {
    "include_dependencies": true,
    "tier_boost": {
      "project": 1.0,
      "dependency": 0.7,
      "stdlib": 0.5
    }
  }
}
```

**CLI flags:**

```bash
# Exclude all dependencies
sia-code search --no-deps "authentication"

# Show only dependencies
sia-code search --deps-only "requests.get"
```

---

## Migration Guide

### From Memvid Backend

**Old backend:** `.mv2` file (LMDB + FAISS)

**New backend:** `.sia-code/` directory (Usearch + SQLite)

**Migration steps:**

1. **Export old index** (if possible):
   ```bash
   # Not implemented yet - data cannot be migrated
   ```

2. **Initialize new index:**
   ```bash
   sia-code init
   ```

3. **Reindex:**
   ```bash
   sia-code index .
   ```

**Key differences:**

| Feature | Old (Memvid) | New (Usearch) |
|---------|--------------|---------------|
| Vector index | FAISS (f32) | Usearch HNSW (f16) |
| Metadata | LMDB | SQLite FTS5 |
| Index size | 40-50 MB | 17-25 MB (2x smaller) |
| Query speed | ~200ms | ~60ms (3x faster) |
| Lexical search | No | Yes (FTS5 BM25) |
| Hybrid search | No | Yes (RRF) |

**Benefits of new backend:**

- 2x smaller index size (f16 quantization)
- 3x faster queries (optimized HNSW)
- Lexical search with BM25 (89.9% Recall@5)
- Hybrid search with RRF fusion
- Better incremental indexing
- SQLite for reliability

---

## Troubleshooting

### Index not found

**Error:** `Error: Sia Code not initialized. Run 'sia-code init' first.`

**Solution:**
```bash
sia-code init
sia-code index .
```

### Empty search results

**Problem:** No results for queries that should match

**Possible causes:**

1. **Stale index:** Files changed but not reindexed
   ```bash
   sia-code index --update
   ```

2. **Wrong search mode:** Try different modes
   ```bash
   sia-code search --regex "exact query"
   sia-code search --semantic-only "conceptual query"
   ```

3. **Dependencies filtered:** Include dependencies
   ```bash
   sia-code config set search.include_dependencies true
   sia-code index --update
   ```

### Slow indexing

**Problem:** Indexing takes too long

**Solutions:**

1. **Use GPU:** Ensure CUDA is available
   ```bash
   python -c "import torch; print(torch.cuda.is_available())"
   ```

2. **Use parallel indexing:**
   ```bash
   sia-code index --parallel --workers 8
   ```

3. **Exclude large directories:**
   ```bash
   sia-code config set indexing.exclude_patterns '["node_modules/", "dist/", "build/"]'
   ```

### Out of memory

**Problem:** `MemoryError` during indexing

**Solutions:**

1. **Reduce batch size** (edit source code):
   - `sia_code/indexer/embedder.py` → `batch_size=16`

2. **Increase file size limit:**
   ```bash
   sia-code config set indexing.max_file_size_mb 2
   ```

3. **Disable embeddings:**
   ```bash
   sia-code config set embedding.enabled false
   sia-code index --clean
   ```

---

## Best Practices

### Recommended Configuration

**For best search results (based on 89.9% Recall@5 benchmark):**

```json
{
  "search": {
    "vector_weight": 0.0  // Lexical-only search
  }
}
```

### Indexing Workflow

1. **Initial index:**
   ```bash
   sia-code init
   sia-code index .
   ```

2. **Daily development:**
   ```bash
   sia-code index --update  # Quick incremental
   ```

3. **After major refactoring:**
   ```bash
   sia-code index --clean  # Full rebuild
   ```

4. **Watch mode for active development:**
   ```bash
   sia-code index --watch
   ```

### Search Tips

1. **Use lexical search for exact matches:**
   ```bash
   sia-code search --regex "def authenticate"
   ```

2. **Use semantic search for concepts:**
   ```bash
   sia-code search --semantic-only "error handling patterns"
   ```

3. **Increase results for exploration:**
   ```bash
   sia-code search "database" -k 50
   ```

4. **Export results for analysis:**
   ```bash
   sia-code search --format csv "api endpoints" -o results.csv
   ```

---

## Performance Benchmarks

**RepoEval Benchmark (1,600 queries, 8 repositories):**

| Configuration | Recall@5 | Query Time | Index Size |
|---------------|----------|------------|------------|
| **Lexical-only (recommended)** | **89.9%** | ~60ms | 17-25 MB |
| Hybrid (w=0.5) | 89.1% | ~80ms | 24-30 MB |
| Semantic-only | 78.0% | ~50ms | 24-30 MB |

**cAST Paper Comparison:**

- cAST: 77.0% Recall@5
- Sia-code: **89.9% Recall@5**
- **Improvement: +12.9 percentage points**

See [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md) for full analysis.

---

## Next Steps

- **Architecture:** See [ARCHITECTURE.md](ARCHITECTURE.md)
- **Code Structure:** See [CODE_STRUCTURE.md](CODE_STRUCTURE.md)
- **Benchmarks:** See [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md)
- **Performance Analysis:** See [PERFORMANCE_ANALYSIS.md](PERFORMANCE_ANALYSIS.md)
