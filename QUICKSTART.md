# PCI Quick Start Guide

## What is PCI?

**PCI (Portable Code Index)** is a local-first codebase intelligence tool that provides ChunkHound-like functionality using Memvid as the storage backend.

### Key Features
- ✅ **Local-first** - All data stays on your machine
- ✅ **Portable** - Single .mv2 file storage
- ✅ **Semantic search** - Natural language queries
- ✅ **30 languages** - Comprehensive language support (planned)
- ⏸️ **cAST chunking** - Smart semantic code chunking (in progress)
- ⏸️ **Multi-hop search** - Discover code relationships (planned)

## Installation

```bash
# Clone or download the project
cd pci/

# Install in development mode
pip install -e .
```

## Usage

### 1. Initialize a Project

```bash
cd /path/to/your/codebase
python -m pci.cli init
```

This creates `.pci/` directory with:
- `config.json` - Configuration
- `index.mv2` - Memvid storage file
- `cache/` - For incremental indexing

### 2. Index Your Code (Not Yet Implemented)

```bash
python -m pci.cli index
```

This will:
- Discover source files
- Parse with Tree-sitter
- Chunk using cAST algorithm
- Store in Memvid with embeddings

**Status:** Parser implementation in progress

### 3. Search

```bash
# Semantic search (once indexed)
python -m pci.cli search "find authentication logic"

# Lexical/regex search
python -m pci.cli search --regex "def.*auth"
```

### 4. Code Research (Planned)

```bash
python -m pci.cli research "how does error handling work?"
```

Multi-hop search to discover interconnected code.

### 5. Check Status

```bash
python -m pci.cli status
```

Shows index statistics.

### 6. View Configuration

```bash
python -m pci.cli config --show
```

## Configuration

Edit `.pci/config.json`:

```json
{
  "embedding": {
    "provider": "local",
    "model": "bge-small"
  },
  "indexing": {
    "exclude_patterns": [
      "node_modules/",
      "__pycache__/",
      ".git/"
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
    "default_limit": 10,
    "multi_hop_enabled": true,
    "max_hops": 2
  }
}
```

### Embedding Options

**Local (default, no API key needed):**
```json
{
  "embedding": {
    "provider": "local",
    "model": "bge-small"
  }
}
```

**OpenAI (requires API key):**
```json
{
  "embedding": {
    "provider": "openai",
    "model": "text-embedding-3-small",
    "api_key": "sk-..."
  }
}
```

**Voyage (requires API key):**
```json
{
  "embedding": {
    "provider": "voyage",
    "model": "voyage-code-2",
    "api_key": "..."
  }
}
```

## Architecture

```
User Query
    ↓
CLI (cli.py)
    ↓
Search Service → Memvid Backend (.mv2 file)
                      ↓
                 Hybrid Search (BM25 + Vector)
                      ↓
                 Search Results
```

For indexing (when implemented):
```
Source Files
    ↓
Tree-sitter Parser
    ↓
Concept Extraction
    ↓
cAST Chunker
    ↓
Memvid Backend (with embeddings)
```

## Current Status

### ✅ Implemented
- Project structure
- Configuration management
- Memvid storage backend
- CLI framework
- Search commands (ready for data)

### 🚧 In Progress
- Parser implementation
- Indexing coordinator

### ⏸️ Planned
- Full cAST algorithm
- Multi-hop search
- All 30 language mappings
- Executable packaging

## Development

### Run Tests

```bash
pytest
```

### Build Executable

```bash
pyinstaller --onefile --name pci pci/cli.py
```

Creates standalone `pci` executable.

## Supported Languages (Planned)

### Programming (via Tree-sitter)
Python, JavaScript, TypeScript, JSX, TSX, Java, Kotlin, Groovy, C, C++, C#, Go, Rust, Haskell, Swift, Bash, MATLAB, Makefile, Objective-C, PHP, Vue, Svelte, Zig

### Configuration
JSON, YAML, TOML, HCL, Markdown

### Text-based
Text files, PDF

## Troubleshooting

### "PCI not initialized"
Run `python -m pci.cli init` in your project directory first.

### "No results found"
The indexing feature is not yet implemented. You'll need to wait for the parser implementation or contribute!

### Dependencies not installing
Make sure you have Python 3.10+ installed:
```bash
python --version
```

## Contributing

The foundation is built! Contributions needed for:
1. **Parser implementation** (`parser/engine.py`, `parser/concepts.py`, `parser/chunker.py`)
2. **Language mappings** (`parser/languages/*.py`)
3. **Indexing coordinator** (`indexer/coordinator.py`)
4. **Multi-hop search** (`search/multi_hop.py`)
5. **Tests**

See `STATUS.md` for detailed task breakdown.

## License

MIT

## Acknowledgments

- **ChunkHound** - Inspiration and cAST algorithm
- **Memvid** - Storage and search backend
- **Tree-sitter** - Language parsing
