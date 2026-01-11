# PCI Usage Examples

This document provides comprehensive examples for using PCI (Portable Code Index).

## Table of Contents
- [Basic Workflow](#basic-workflow)
- [Search Examples](#search-examples)
- [Multi-Hop Code Research](#multi-hop-code-research)
- [Incremental Indexing](#incremental-indexing)
- [Performance Monitoring](#performance-monitoring)
- [Advanced Configuration](#advanced-configuration)

---

## Basic Workflow

### Initialize a New Project

```bash
cd my-project
pci init

# Output:
# ✓ Initialized PCI at .pci
# Next: pci index [path]
```

### Index Your Codebase

```bash
# Index current directory
pci index .

# Index specific directory
pci index src/

# Output:
# Indexing /path/to/src...
# ✓ Indexing complete
#   Files indexed: 45/50
#   Total chunks: 523
#
# Performance:
#   Duration: 8.34s
#   Throughput: 5.4 files/s, 62.7 chunks/s
#   Processed: 0.15 MB/s
```

### Check Index Status

```bash
pci status

# Output:
# ┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
# ┃ Property   ┃ Value           ┃
# ┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
# │ Index Path │ .pci/index.mv2  │
# │ Exists     │ Yes             │
# │            │                 │
# │ Cached Files │ 45            │
# │ Cache Size │ 12,456 bytes    │
# │            │                 │
# │ Index Size │ 2,345,678 bytes │
# │ Index Age  │ 0 days, 2 hours │
# └────────────┴─────────────────┘
```

---

## Search Examples

### Lexical/Regex Search

```bash
# Find all authentication-related code
pci search --regex "auth"

# Find function definitions
pci search --regex "def.*login"

# Case-sensitive search
pci search --regex "API"

# Limit results
pci search --regex "error" -k 5

# Output:
# Searching (lexical)...
#
# 1. login_handler
# src/auth.py:45-67
# Score: 8.234
#
# def login_handler(request):
#     """Handle user login requests."""
#     ...
```

### Semantic Search

```bash
# Natural language query
pci search "find user authentication logic"

# Search for specific concepts
pci search "database connection pooling"
pci search "error handling middleware"
pci search "API rate limiting"

# Note: Requires embeddings to be enabled
```

---

## Multi-Hop Code Research

Multi-hop research automatically discovers code relationships to answer architectural questions.

### Basic Research

```bash
pci research "How does authentication work?"

# Output:
# Researching: How does authentication work?
# Max hops: 2, Results per hop: 5
#
# ✓ Research Complete
#   Found: 12 related code chunks
#   Relationships: 18
#   Entities discovered: 24
#   Hops executed: 2/2
#
# Top Related Code:
#
# 1. login_handler
#    src/auth/handlers.py:45-67
#
# 2. validate_token
#    src/auth/tokens.py:23-41
#
# 3. check_user_credentials
#    src/auth/validators.py:12-34
#    ...
```

### Research with Call Graph

```bash
pci research "What calls the database?" --graph

# Output includes:
# Call Graph:
#
# Entry points:
#   → main
#   → handle_request
#   → process_batch
#
# Relationships:
#   main
#     calls → init_database
#     calls → setup_connections
#   handle_request
#     calls → query_user
#     calls → fetch_data
#   ...
```

### Custom Research Depth

```bash
# Shallow research (faster)
pci research "logging setup" --hops 1

# Deep research (more comprehensive)
pci research "data flow through API" --hops 3 -k 10
```

### Research Use Cases

**1. Understanding Unfamiliar Codebases:**
```bash
pci research "How is configuration loaded?"
pci research "What's the application entry point?"
pci research "How are routes registered?"
```

**2. Debugging:**
```bash
pci research "What calls this broken function?"
pci research "Error handling flow"
pci research "Where is this exception raised?"
```

**3. Refactoring:**
```bash
pci research "All usages of legacy API"
pci research "Dependencies of auth module"
pci research "What imports database module?"
```

**4. Documentation:**
```bash
pci research "Complete authentication flow" --graph
pci research "API request lifecycle" --graph
```

---

## Incremental Indexing

Incremental indexing is 10x faster for re-indexing after changes.

### Basic Incremental Update

```bash
# Make changes to your code
vim src/main.py src/utils.py

# Re-index only changed files
pci index --update

# Output:
# Incremental indexing /path/to/project...
# Checking for changes...
#
# ✓ Incremental indexing complete
#   Changed files: 2
#   Skipped files: 43
#   Indexed files: 2/45
#   Total chunks: 18
#
# Performance:
#   Duration: 0.83s
#   Throughput: 2.4 files/s, 21.7 chunks/s
#   Processed: 0.04 MB/s
```

### When to Use Incremental vs Clean

**Use `pci index --update` for:**
- Daily development workflow
- After modifying a few files
- Fast feedback loop

**Use `pci index --clean` for:**
- Weekly/monthly maintenance
- After major refactoring
- When search results seem stale
- After index grows too large

### Workflow Example

```bash
# Day 1: Initial index
pci index .

# Day 2-7: Incremental updates
pci index --update  # After each coding session

# Week 2: Clean rebuild
pci index --clean   # Periodic maintenance
```

---

## Performance Monitoring

### Verbose Logging

```bash
# Enable detailed logging
pci --verbose index src/

# Output includes:
# 2026-01-11 18:52:46 - pci.indexer.coordinator - INFO - Indexed src/api.py: 12 chunks
# 2026-01-11 18:52:47 - pci.indexer.coordinator - INFO - Indexed src/models.py: 8 chunks
# 2026-01-11 18:52:48 - pci.indexer.coordinator - INFO - Indexed src/utils.py: 5 chunks
# ...
# 2026-01-11 18:52:56 - pci.indexer.coordinator - INFO - Indexing complete: Duration: 10.2s | Files: 45 (4.4/s) | Chunks: 523 (51.3/s) | Throughput: 0.15 MB/s
```

### Performance Metrics

Every indexing operation shows performance metrics:

```
Performance:
  Duration: 8.34s              # Total time
  Throughput: 5.4 files/s      # Files processed per second
               62.7 chunks/s   # Chunks created per second
  Processed: 0.15 MB/s         # Data throughput
```

**Typical Performance (on modern hardware):**
- Small project (100 files): 5-10 seconds
- Medium project (1,000 files): 30-60 seconds
- Large project (10,000 files): 5-10 minutes

**Optimization tips:**
- Use `--update` for incremental indexing (10x faster)
- Exclude large directories in config (`node_modules`, `venv`, `.git`)
- Increase `max_file_size_mb` if needed
- Use SSD for better I/O performance

---

## Advanced Configuration

### Custom Configuration

Edit `.pci/config.json`:

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
    "include_patterns": ["*.py", "*.js", "*.ts", "*.tsx"],
    "exclude_patterns": [
      "node_modules/",
      "__pycache__/",
      "*.pyc",
      ".git/",
      "venv/",
      "build/",
      "dist/"
    ],
    "max_file_size_mb": 10
  },
  "chunking": {
    "max_chunk_size": 1200,
    "min_chunk_size": 50,
    "merge_threshold": 0.7,
    "greedy_merge": true
  }
}
```

### Embedding Configuration

**OpenAI Embeddings (Cloud, High Quality):**

```bash
# Set API key
export OPENAI_API_KEY=sk-your-key-here

# Edit config for OpenAI small model (1536 dimensions)
# .pci/config.json:
{
  "embedding": {
    "enabled": true,
    "provider": "openai",
    "model": "openai-small",
    "api_key_env": "OPENAI_API_KEY",
    "dimensions": 1536
  }
}
```

**OpenAI Large Model (Higher Quality):**

```json
{
  "embedding": {
    "enabled": true,
    "provider": "openai",
    "model": "openai-large",
    "api_key_env": "OPENAI_API_KEY",
    "dimensions": 3072
  }
}
```

**Local Embeddings (Offline, No API Key):**

```json
{
  "embedding": {
    "enabled": true,
    "provider": "local",
    "model": "bge-small",
    "dimensions": 384
  }
}
```

**Disable Embeddings (Lexical Search Only):**

```json
{
  "embedding": {
    "enabled": false
  }
}
```

When embeddings are disabled, you can still use lexical/regex search:
```bash
pci search --regex "function.*login"
```

### View Current Configuration

```bash
pci config --show
```

### Exclude Patterns

Add patterns to skip certain files/directories:

```json
{
  "indexing": {
    "exclude_patterns": [
      "test_*.py",           // Skip test files
      "migrations/",         // Skip database migrations
      "*.min.js",           // Skip minified JavaScript
      "vendor/",            // Skip third-party code
      "*.generated.*"       // Skip generated files
    ]
  }
}
```

### Chunk Size Tuning

Adjust chunking parameters based on your needs:

```json
{
  "chunking": {
    "max_chunk_size": 1500,    // Larger chunks for better context
    "min_chunk_size": 100,     // Avoid tiny fragments
    "merge_threshold": 0.8,    // More aggressive merging
    "greedy_merge": true       // Always merge when possible
  }
}
```

**Trade-offs:**
- **Larger chunks:** Better context, but less precise search
- **Smaller chunks:** More precise, but may miss context
- **Higher merge threshold:** Fewer, larger chunks
- **Lower merge threshold:** More, smaller chunks

---

## Error Handling

### Common Errors

**1. PCI not initialized:**
```bash
pci search "query"
# Error: PCI not initialized. Run 'pci init' first.

# Solution:
pci init
```

**2. Index doesn't exist:**
```bash
pci search "query"
# Error: Index file not found

# Solution:
pci index .
```

**3. File size too large:**
```bash
pci index .
# Warning: large_file.min.js: File too large (>10MB)

# Solution: Increase max_file_size_mb in config
```

**4. Unsupported language:**
```bash
# Some files may be skipped if language isn't supported
# Check supported languages in README
```

**5. Embeddings disabled (no API key):**
```bash
pci search "authentication logic"
# WARNING - Embedding enabled but OPENAI_API_KEY not found. Embeddings will be disabled for this session.
# WARNING - Semantic search failed (vector index disabled). Falling back to lexical search.

# Solution 1: Set API key
export OPENAI_API_KEY=sk-your-key-here

# Solution 2: Use explicit lexical search
pci search --regex "auth"

# Solution 3: Disable embeddings in config
# Edit .pci/config.json: "enabled": false
```

**Note:** PCI automatically falls back to lexical search if embeddings fail. No crashes!

### Retry on Errors

PCI automatically retries failed files with exponential backoff:

```
2026-01-11 18:52:46 - pci.indexer.coordinator - WARNING - corrupt_file.py: Retry 1/3 after 1s
2026-01-11 18:52:47 - pci.indexer.coordinator - WARNING - corrupt_file.py: Retry 2/3 after 2s
2026-01-11 18:52:49 - pci.indexer.coordinator - ERROR - corrupt_file.py: Failed after 3 attempts
```

Memory errors fail immediately without retry.

---

## Tips & Best Practices

### 1. Regular Maintenance

```bash
# Weekly clean rebuild
pci index --clean

# Check index health
pci status
```

### 2. Development Workflow

```bash
# Morning: Start fresh
pci index --clean

# During day: Incremental updates
pci index --update  # After each coding session

# Before commit: Search for TODOs
pci search --regex "TODO|FIXME"
```

### 3. CI/CD Integration

```yaml
# .github/workflows/index.yml
name: Update Code Index

on: [push]

jobs:
  index:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install PCI
        run: pip install pci
      - name: Initialize PCI
        run: pci init
      - name: Index codebase
        run: pci index src/
      - name: Upload index
        uses: actions/upload-artifact@v2
        with:
          name: code-index
          path: .pci/
```

### 4. Large Codebases

For codebases with 1000+ files:

```bash
# Index in parallel (future feature)
# For now: exclude large directories

# Edit .pci/config.json
{
  "indexing": {
    "exclude_patterns": [
      "node_modules/",
      "vendor/",
      "third_party/",
      "*.min.*"
    ],
    "max_file_size_mb": 5  // Lower limit for faster indexing
  }
}
```

### 5. Search Strategy

```bash
# Start broad with lexical
pci search --regex "authentication"

# Then drill down with research
pci research "How does authentication work?" --graph

# Finally, semantic search for specific concepts
pci search "JWT token validation"
```

---

## Troubleshooting

### Slow Indexing

```bash
# 1. Enable verbose logging to see what's slow
pci --verbose index .

# 2. Check file count
pci status

# 3. Exclude unnecessary directories
# Edit .pci/config.json to add exclude patterns

# 4. Use incremental indexing
pci index --update
```

### Poor Search Results

```bash
# 1. Check if index is stale
pci status

# 2. Rebuild index
pci index --clean

# 3. Try different search modes
pci search --regex "keyword"  # Lexical
pci search "concept"          # Semantic (if embeddings enabled)

# 4. Use research for architectural questions
pci research "How does X work?"
```

### Index Growing Too Large

```bash
# Check index size
pci status

# Rebuild to remove stale chunks
pci index --clean

# Adjust exclude patterns to skip large files
```

---

## More Examples

For more examples and use cases, see:
- [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) - Workarounds for known issues
- [FUTURE_WORK.md](FUTURE_WORK.md) - Upcoming features
- [README.md](README.md) - Main documentation
