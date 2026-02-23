# Architecture (Compact)

## Runtime Overview

Sia Code has two core pipelines:

1. **Indexing pipeline**
   - discover files
   - parse/chunk code with AST-aware logic
   - generate embeddings (if enabled)
   - write lexical/vector indexes

2. **Query pipeline**
   - resolve mode and build ChunkHound CLI command
   - execute ChunkHound search/research
   - parse and render results in Sia CLI formats

## Storage Model

Index data lives in `.sia-code/`.

- `index.db`: metadata + lexical index (+ sqlite-vec data when active)
- `vectors.usearch`: present for legacy usearch indexes
- `config.json`: runtime settings
- `cache/`: indexing and embedding caches

Backend selection:

- New/clean setups default to sqlite-vec mode
- Existing `vectors.usearch` keeps legacy usearch mode for compatibility

## Key Components

- `cli.py`: command entry and orchestration
- `indexer/coordinator.py`: full/incremental indexing lifecycle
- `parser/*`: language detection, concept extraction, chunk building
- `search/chunkhound_cli.py`: ChunkHound command bridge and output parsing
- `storage/*`: memory persistence plus legacy/local search paths
- `memory/*`: git-to-memory sync and timeline/changelog tooling
- `embed_server/*`: optional shared embed daemon

## Search Architecture

- **Default (`search`)**: mode from `chunkhound.default_search_mode` (default `regex`)
- **Lexical (`--regex`)**: exact token/symbol heavy queries
- **Semantic (`--semantic-only`)**: ChunkHound semantic mode

Flags like `--no-deps` and `--deps-only` are accepted for compatibility but currently no-op with ChunkHound-backed search.

## Design Goals

- Local-first and repo-portable
- Fast symbol-level search
- Practical architecture discovery
- Agent-friendly memory for decisions and history

## Related Docs

- `docs/CODE_STRUCTURE.md`
- `docs/INDEXING.md`
- `docs/QUERYING.md`
