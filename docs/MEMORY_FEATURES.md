# Memory Features (Compact)

Project memory helps preserve context beyond code search.

## Memory Types

- **Decisions**: pending/approved/rejected technical decisions
- **Timeline events**: important git-derived events
- **Changelogs**: release-oriented summaries

## Core Workflow

```bash
# import from git
sia-code memory sync-git

# add a decision
sia-code memory add-decision "Adopt X" -d "Context" -r "Reason" -a "Y,Z"

# triage
sia-code memory list --type decision --status pending
sia-code memory approve 1 --category architecture

# search memory later
sia-code memory search "Adopt X" --type decision
```

## Why `sync-git` matters

`memory sync-git` turns git history into searchable project context.

- Tags become changelog memory entries
- Merge commits become timeline memory events
- Merge commits whose subject matches `Merge branch '...'` also become changelog entries
- Each event captures changed files and diff stats
- Duplicate events are skipped automatically

This gives LLM agents structured context instead of raw git noise.

## Semantic changelog generation (local model)

When summarization is enabled, Sia Code can upgrade sparse tag/merge summaries.

Process:

1. Read git structure: tags, merge refs, and diff stats
2. Collect commit subjects for the relevant range
3. Run local summarization model (default `google/flan-t5-base`)
4. Save enhanced text into memory changelog/timeline records

```bash
sia-code memory sync-git
sia-code memory changelog --format markdown
```

Notes:

- Model inference is local (no required remote API)
- If model/dependencies are unavailable, Sia Code falls back to original git summary text

## Key Commands

| Command | Purpose |
| --- | --- |
| `memory sync-git` | import timeline/changelog from git |
| `memory add-decision` | create pending decision |
| `memory approve` / `memory reject` | decision workflow |
| `memory list` | list decisions/timeline/changelogs |
| `memory timeline` | view timeline with filters |
| `memory changelog` | render changelog text/json/markdown |
| `memory export` / `memory import` | backup/restore memory data |

Limit behavior:

- `memory sync-git --limit 0` processes all eligible events
- `memory list --limit 0`, `memory timeline --limit 0`, and `memory changelog --limit 0` return all rows

## Good Practices

- Add decisions with explicit `description` and `reasoning`.
- Run `memory sync-git` after major merges/tags.
- Use memory search before repeating architecture work.

## Troubleshooting

- If memory operations fail due to embedding/daemon issues: run `sia-code embed start`
- If memory seems empty: run `sia-code memory sync-git`

## Related Docs

- `docs/CLI_FEATURES.md`
- `docs/LLM_CLI_INTEGRATION.md`
