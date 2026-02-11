# Embedding Server Verification (Compact)

## Verification Checklist

- daemon starts and reports healthy status
- CLI operations continue working if daemon is unavailable (fallback path)
- semantic/hybrid operations work after daemon start

## Quick Verification Commands

```bash
sia-code embed start
sia-code embed status
sia-code search "architecture"      # hybrid default
sia-code search --semantic-only "login flow"
sia-code embed stop
```

## Notes

- Keep long benchmark traces in CI artifacts, not here.
- Update this file only with practical pass/fail summaries.
