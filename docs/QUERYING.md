# Querying (Compact)

## Search Commands

```bash
# default mode from config (ChunkHound-backed; default is regex)
sia-code search "authentication flow"

# lexical / symbol-heavy
sia-code search --regex "AuthService|token"

# semantic only (requires embedding setup)
sia-code search --semantic-only "handle login failures"
```

## Useful Flags

- `-k, --limit <N>`: number of results
- `--no-deps`: accepted for compatibility (currently no-op)
- `--deps-only`: accepted for compatibility (currently no-op)
- `--no-filter`: accepted for compatibility (currently no-op)
- `--format text|json|table|csv`
- `--output <path>`: write results to file

## Multi-Hop Research

```bash
sia-code research "how does auth middleware work?"
```

Use this for architecture tracing, call-path discovery, and unfamiliar code.

Compatibility flags for `research` (`--hops`, `--graph`, `--limit`, `--no-filter`) are accepted by Sia and ignored by ChunkHound.

## Practical Tuning

- `chunkhound.default_search_mode = regex|semantic`
- defaults come from `.sia-code/config.json`

```bash
sia-code config get chunkhound.default_search_mode
sia-code config set chunkhound.default_search_mode semantic
```

## Output Tips

- Use `--format json` for scripts/agents.
- Use `--format table` for quick terminal scanning.
- Use tighter regex terms or path-like query text when results are noisy.

## Related Docs

- `docs/CLI_FEATURES.md`
- `docs/INDEXING.md`
