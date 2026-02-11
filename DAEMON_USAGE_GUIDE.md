# Embedding Daemon Guide (Compact)

Use daemon mode when you run many semantic/hybrid operations.

## Commands

```bash
sia-code embed start
sia-code embed status
sia-code embed stop
```

## When it helps

- repeated hybrid/semantic searches
- repeated memory operations that require embeddings
- multi-repo sessions where model warm-up cost matters

## Practical workflow

```bash
sia-code embed start
sia-code search "authentication flow"
sia-code research "how does auth work?"
```

If you mainly use `--regex`, daemon is usually optional.
