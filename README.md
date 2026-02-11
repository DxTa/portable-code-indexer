# Sia Code

Local-first codebase intelligence for CLI workflows.

Sia Code indexes your repo and lets you:

- search code fast (lexical, semantic, or hybrid)
- trace architecture with multi-hop research
- store/retrieve project decisions and timeline context

## Why teams use it

- Works directly on local code (`.sia-code/` index per repo/worktree)
- Great for symbol-level search (`--regex`) and architecture questions (`research`)
- Supports 12 AST-aware languages (Python, JS/TS, Go, Rust, Java, C/C++, C#, Ruby, PHP)
- Integrates well with LLM CLI agents

## Install

```bash
# pip
pip install sia-code

# or uv tool
uv tool install sia-code

# verify
sia-code --version
```

## Quick Start (2 minutes)

```bash
# in your project
sia-code init
sia-code index .

# search
sia-code search --regex "auth|login|token"

# architecture trace
sia-code research "how does authentication work?"

# index health
sia-code status
```

## Command Cheatsheet

| Command | What it does |
| --- | --- |
| `sia-code init` | Initialize `.sia-code/` in current project |
| `sia-code index .` | Build index |
| `sia-code index --update` | Incremental re-index |
| `sia-code index --clean` | Rebuild index from scratch |
| `sia-code search "query"` | Hybrid search (default) |
| `sia-code search --regex "pattern"` | Lexical search |
| `sia-code research "question"` | Multi-hop relationship discovery |
| `sia-code memory sync-git` | Import timeline/changelog from git |
| `sia-code memory search "topic"` | Search stored project memory |
| `sia-code config show` | Print active configuration |

## Search Modes (important)

- Default command is hybrid: `sia-code search "query"`
- Lexical mode: `sia-code search --regex "pattern"`
- Semantic-only mode: `sia-code search --semantic-only "query"`

Use `--no-deps` when you want only your project code.

## LLM CLI Integration

This repo includes a compact reusable skill at:

- `skills/sia-code/SKILL.md`

Integration guide:

- `docs/LLM_CLI_INTEGRATION.md`

In short: copy that skill file into your LLM CLI skill directory, then load `sia-code` in your session.

## Configuration

Config path:

- `.sia-code/config.json`

Useful commands:

```bash
sia-code config show
sia-code config get search.vector_weight
sia-code config set search.vector_weight 0.0
```

Note: backend selection is auto by default (`sqlite-vec` for new indexes, legacy `usearch` supported).

## Documentation

- `docs/CLI_FEATURES.md` - concise CLI command reference
- `docs/CODE_STRUCTURE.md` - repo/module map
- `docs/ARCHITECTURE.md` - core runtime architecture
- `docs/INDEXING.md` - indexing behavior and maintenance
- `docs/QUERYING.md` - search modes and tuning
- `docs/MEMORY_FEATURES.md` - memory workflow
- `docs/BENCHMARK_RESULTS.md` - benchmark summary

For historical notes and compact reports, see the root-level markdown files.

## License

MIT
