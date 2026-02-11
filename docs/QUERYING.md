# Querying (Compact)

## Search Commands

```bash
# default hybrid
sia-code search "authentication flow"

# lexical / symbol-heavy
sia-code search --regex "AuthService|token"

# semantic only
sia-code search --semantic-only "handle login failures"
```

## Useful Flags

- `-k, --limit <N>`: number of results
- `--no-deps`: only project code
- `--deps-only`: only dependency code
- `--no-filter`: include stale chunks
- `--format text|json|table|csv`
- `--output <path>`: write results to file

## Multi-Hop Research

```bash
sia-code research "how does auth middleware work?" --hops 3 --graph
```

Use this for architecture tracing, call-path discovery, and unfamiliar code.

## Practical Tuning

- `search.vector_weight = 0.0` => lexical-heavy behavior
- `search.vector_weight = 1.0` => semantic-heavy behavior
- defaults come from `.sia-code/config.json`

```bash
sia-code config get search.vector_weight
sia-code config set search.vector_weight 0.0
```

## Output Tips

- Use `--format json` for scripts/agents.
- Use `--format table` for quick terminal scanning.
- Use `--no-deps` in large repos to reduce noise.

## Related Docs

- `docs/CLI_FEATURES.md`
- `docs/INDEXING.md`
