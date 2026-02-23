# CLI Features (Compact)

Short reference for daily `sia-code` usage.

## Typical Workflow

```bash
sia-code init
sia-code index .
sia-code search --regex "auth|token"
sia-code research "how does auth flow work?"
sia-code status
```

## Core Commands

| Command | Purpose | Key options |
| --- | --- | --- |
| `init` | Create `.sia-code/` index workspace | `--path`, `--dry-run` |
| `index [PATH]` | Build index | `--update`, `--clean`, `--parallel`, `--workers`, `--watch`, `--debounce`, `--no-git-sync` |
| `search QUERY` | Search code (ChunkHound-backed) | `--regex`, `--semantic-only`, `-k/--limit`, `--no-filter` (compat), `--no-deps` (compat), `--deps-only` (compat), `--format`, `--output` |
| `research QUESTION` | Architecture exploration (ChunkHound-backed) | `--hops` (compat), `--graph` (compat), `-k/--limit` (compat), `--no-filter` (compat) |
| `status` | Index health and statistics | none |
| `compact [PATH]` | Remove stale chunks | `--threshold`, `--force` |
| `interactive` | Live query loop | `--regex`, `-k/--limit` |

## Memory Commands

| Command | Purpose | Key options |
| --- | --- | --- |
| `memory sync-git` | Import timeline/changelog from git (with diff stats and optional local semantic summaries) | `--since`, `--limit` (`0` means all), `--dry-run`, `--tags-only`, `--merges-only`, `--min-importance` |
| `memory add-decision TITLE` | Add pending decision | `-d/--description` (required), `-r/--reasoning`, `-a/--alternatives` |
| `memory list` | List memory items | `--type`, `--status`, `--limit` (`0` means all), `--format` |
| `memory approve ID` | Approve decision | `-c/--category` (required) |
| `memory reject ID` | Reject decision | none |
| `memory search QUERY` | Search memory | `--type`, `-k/--limit` |
| `memory timeline` | View timeline events | `--since`, `--event-type`, `--importance`, `--limit` (`0` means all), `--format` |
| `memory changelog [RANGE]` | Generate changelog | `--limit` (`0` means all), `--format`, `--output` |
| `memory export` / `memory import` | Backup/restore memory | `-o/--output`, `-i/--input` |

`memory sync-git` is the entrypoint for semantic changelog generation: it extracts git context, then (if enabled) uses the local summarizer to enrich tag releases and merge-derived changelog entries stored in memory.

## Embed Daemon

| Command | Purpose |
| --- | --- |
| `embed start` | Start shared embedding daemon |
| `embed status` | Show daemon status |
| `embed stop` | Stop daemon |

Use daemon when you rely heavily on memory embedding operations.

## Config Commands

```bash
sia-code config show
sia-code config path
sia-code config get chunkhound.default_search_mode
sia-code config set chunkhound.default_search_mode semantic
```

## Output Formats

- `text` (default)
- `json` (automation)
- `table` (human scanning)
- `csv` (export)

## Good Defaults

- First index: `sia-code index .`
- Ongoing work: `sia-code index --update`
- Exact symbols: `sia-code search --regex "pattern"`
- If output is noisy: tighten regex terms or add path-like query terms
- Architecture questions: `sia-code research "..."`

## Related Docs

- `docs/INDEXING.md`
- `docs/QUERYING.md`
- `docs/MEMORY_FEATURES.md`
