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
