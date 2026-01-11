# PCI - Portable Code Index

Local-first codebase intelligence using Memvid storage and cAST semantic chunking.

## Features

- **cAST Algorithm** - Semantic code chunking via Abstract Syntax Tree
- **Multi-Hop Semantic Search** - Discovers interconnected code relationships
- **Semantic Search** - Natural language queries like "find authentication code"
- **Regex/Lexical Search** - Pattern matching without API keys
- **Local-First** - All code stays on your machine
- **30 Languages** - Comprehensive language support via Tree-sitter
- **Portable** - Single .mv2 file storage (no database required)

## Installation

```bash
pip install -e .
```

## Quick Start

```bash
# Initialize index in current directory
pci init

# Index your codebase
pci index

# Search semantically
pci search "find authentication logic"

# Search with regex/lexical
pci search --regex "def.*auth"

# Multi-hop code research
pci research "how does the API handle errors?"

# Show statistics
pci status
```

## Configuration

Configuration is stored in `.pci/config.json`:

```json
{
  "embedding": {
    "provider": "local",
    "model": "bge-small"
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

## License

MIT
