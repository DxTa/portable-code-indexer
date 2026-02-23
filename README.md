# Sia Code

Local-first codebase intelligence for CLI workflows.

Sia Code indexes your repo and lets you:

- search code fast via ChunkHound CLI (lexical or semantic)
- trace architecture with ChunkHound research
- store/retrieve project decisions and timeline context

Search and research are hard-switched to ChunkHound CLI. Sia keeps index orchestration and memory storage local.

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
# install ChunkHound CLI once
uv tool install chunkhound

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
| `sia-code search "query"` | ChunkHound-backed search (default mode from config) |
| `sia-code search --regex "pattern"` | ChunkHound lexical search |
| `sia-code research "question"` | ChunkHound research |
| `sia-code memory sync-git` | Import timeline/changelog from git |
| `sia-code memory search "topic"` | Search stored project memory |
| `sia-code config show` | Print active configuration |

## Search Modes (important)

- Default search mode comes from `chunkhound.default_search_mode` (default: `regex`)
- Lexical mode: `sia-code search --regex "pattern"`
- Semantic-only mode: `sia-code search --semantic-only "query"` (requires ChunkHound semantic setup)

Dependency visibility flags (`--no-deps`, `--deps-only`) are currently compatibility no-ops with ChunkHound-backed search.

## Git Sync Memory + Semantic Changelog

`sia-code memory sync-git` is the fastest way to build project memory from git history.

- Scans tags into changelog entries
- Scans merge commits into timeline events
- For merge commits whose subject matches `Merge branch '...'`, also creates changelog entries
- Stores `files_changed` and diff stats (`insertions`, `deletions`, `files`)
- Optionally enhances sparse summaries using a local summarization model
- `memory sync-git --limit 0` processes all eligible events

How semantic summary generation works:

1. `sync-git` collects git context (tags, merges, commit ranges, diff stats)
2. It gathers commit subjects for each release/merge window
3. A local model (default `google/flan-t5-base`) generates a concise summary sentence
4. The enhanced summary is stored in memory and later exposed by `memory changelog`

```bash
sia-code memory sync-git
sia-code memory changelog --format markdown
```

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
sia-code config get chunkhound.default_search_mode
sia-code config set chunkhound.default_search_mode semantic
```

Note: backend selection is auto by default (`sqlite-vec` for new indexes, legacy `usearch` supported).

## Multi-Worktree / Multi-Agent Setup

Yes - Sia Code works with multiple git worktrees and multiple LLM CLI instances.

Scope resolution order:

1. `SIA_CODE_INDEX_DIR` (explicit path override)
2. `SIA_CODE_INDEX_SCOPE` (`shared`, `worktree`, or `auto`)
3. `auto` fallback:
   - linked worktree -> shared index at `<git-common-dir>/sia-code`
   - normal checkout -> local `.sia-code`

```bash
# Shared index across worktrees/agents
export SIA_CODE_INDEX_SCOPE=shared

# Isolated index per worktree
export SIA_CODE_INDEX_SCOPE=worktree

# Full explicit control
export SIA_CODE_INDEX_DIR=/absolute/path/to/sia-index
```

Typical worktree workflow:

```bash
# in main checkout (build shared index once)
export SIA_CODE_INDEX_SCOPE=shared
sia-code init
sia-code index .

# create feature worktree
git worktree add ../feat-auth feat/auth
cd ../feat-auth

# reuse same shared index, then incrementally refresh
sia-code status
sia-code index --update
```

When a worktree is merged/removed:

- `shared` scope: index stays in git common dir and remains usable
- `worktree` scope: index lives in that worktree directory and is removed with it
- after merge, run `sia-code index --update` in the remaining checkout

Practical guidance:

- Many readers/searchers are fine in shared mode
- Prefer one active index writer per shared index
- For strict branch/agent isolation, use `worktree`
- Teams on different machines should keep local indexes and sync context via git + `sia-code memory sync-git`

## Documentation

- `docs/CLI_FEATURES.md` - concise CLI command reference
- `docs/CODE_STRUCTURE.md` - repo/module map
- `docs/ARCHITECTURE.md` - core runtime architecture
- `docs/INDEXING.md` - indexing behavior and maintenance
- `docs/QUERYING.md` - search modes and tuning
- `docs/MEMORY_FEATURES.md` - memory workflow
- `docs/BENCHMARK_RESULTS.md` - benchmark summary

## License

MIT
