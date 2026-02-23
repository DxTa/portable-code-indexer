# Code Structure (Compact)

Fast map of where to work in this repo.

## Top-Level Layout

```text
sia_code/          # main package
tests/             # unit + integration + e2e + benchmarks
docs/              # user and technical docs
examples/          # example outputs and quick guides
scripts/           # helper scripts
```

## Main Package Layout

```text
sia_code/
  cli.py                 # click CLI entrypoint and command handlers
  config.py              # config models and .gitignore pattern loading
  core/                  # shared models and enums
  parser/                # AST concept extraction and chunking
  indexer/               # indexing orchestration, hash cache, metrics
  search/                # ChunkHound CLI bridge + query helpers
  storage/               # memory persistence + legacy local search backends
  memory/                # git sync, timeline, changelog, decision flow
  embed_server/          # optional embedding daemon
```

## Key Files by Task

| Task | File(s) |
| --- | --- |
| Add/adjust CLI command | `sia_code/cli.py` |
| Change default behavior | `sia_code/config.py`, `sia_code/cli.py` |
| Tune indexing | `sia_code/indexer/coordinator.py`, `sia_code/indexer/chunk_index.py` |
| Tune chunking | `sia_code/parser/chunker.py`, `sia_code/parser/concepts.py` |
| ChunkHound search/research bridge | `sia_code/search/chunkhound_cli.py`, `sia_code/cli.py` |
| Legacy/local search ranking (interactive) | `sia_code/storage/sqlite_vec_backend.py`, `sia_code/storage/usearch_backend.py` |
| Backend selection logic | `sia_code/storage/factory.py` |
| Memory commands and sync | `sia_code/memory/git_sync.py`, `sia_code/memory/git_events.py`, `sia_code/cli.py` |

## Test Layout

- `tests/unit/`: isolated module behavior
- `tests/integration/`: cross-module flows
- `tests/e2e/`: full CLI against real repos
- `tests/benchmarks/`: benchmark harness and datasets

## Entry Points

- CLI script from `pyproject.toml`: `sia-code = "sia_code.cli:main"`
- Package version: `sia_code/__init__.py`

## Related Docs

- `docs/ARCHITECTURE.md`
- `docs/INDEXING.md`
- `docs/QUERYING.md`
