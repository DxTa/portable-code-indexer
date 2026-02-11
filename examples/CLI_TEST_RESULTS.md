# CLI Test Results (Compact)

Quick snapshot of expected command behavior.

## Smoke flow

```bash
sia-code init
sia-code index .
sia-code search --regex "auth"
sia-code research "how does auth work?"
sia-code status
```

## Expected outcomes

- commands execute without crashes
- search returns relevant file/line chunks
- research returns multi-hop related symbols
- status reports valid/stale chunk metrics

For detailed logs, use CI artifacts or local command output capture.
