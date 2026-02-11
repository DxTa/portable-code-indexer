# Architecture (Compact)

## Runtime Overview

Sia Code has two core pipelines:

1. **Indexing pipeline**
   - discover files
   - parse/chunk code with AST-aware logic
   - generate embeddings (if enabled)
   - write lexical/vector indexes

2. **Query pipeline**
   - preprocess query
   - run lexical and/or semantic search
   - rank + return chunk matches

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
- `storage/*`: search execution and persistence
- `memory/*`: git-to-memory sync and timeline/changelog tooling
- `embed_server/*`: optional shared embed daemon

## Search Architecture

- **Hybrid (default):** lexical + semantic
- **Lexical (`--regex`):** exact token/symbol heavy queries
- **Semantic (`--semantic-only`):** concept similarity only

Flags like `--no-deps` and `--deps-only` control dependency-code visibility.

## Design Goals

- Local-first and repo-portable
- Fast symbol-level search
- Practical architecture discovery
- Agent-friendly memory for decisions and history

## Related Docs

- `docs/CODE_STRUCTURE.md`
- `docs/INDEXING.md`
- `docs/QUERYING.md`
