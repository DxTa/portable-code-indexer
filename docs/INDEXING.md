# Indexing (Compact)

## Basic Commands

```bash
sia-code init
sia-code index .
```

## Index Modes

| Mode | Command | When to use |
| --- | --- | --- |
| Full | `sia-code index .` | First run or broad refresh |
| Incremental | `sia-code index --update` | Daily edits |
| Clean rebuild | `sia-code index --clean` | Backend/config reset, major refactor |
| Parallel | `sia-code index --parallel --workers 8` | Large repos |
| Watch | `sia-code index --watch --debounce 2.0` | Continuous local development |

## What gets indexed

- Code files for supported languages
- Exclusions from config + `.gitignore` patterns
- Dependency code (unless disabled by config/flags)

## Health and Maintenance

```bash
sia-code status
sia-code compact
sia-code compact --force
```

- Use `status` to check stale/valid chunk health.
- Use `compact` when stale chunks accumulate.

## Git Sync During Indexing

By default, indexing syncs git history into memory.

- disable with `sia-code index --no-git-sync`

## Common Issues

- **Uninitialized repo**: run `sia-code init`
- **Results feel old**: run `sia-code index --update`
- **Major drift/corruption**: run `sia-code index --clean`

## Related Docs

- `docs/CLI_FEATURES.md`
- `docs/QUERYING.md`
- `docs/MEMORY_FEATURES.md`
