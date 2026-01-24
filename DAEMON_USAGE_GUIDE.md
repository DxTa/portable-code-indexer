# Embedding Server Daemon Usage Guide

## When Should the Daemon Run?

The daemon is beneficial for **both indexing and searching**, but provides the most value during frequent query operations:

### During Indexing
```bash
# Indexing computes embeddings for every code chunk
sia-code embed start
sia-code index .
```
**Benefit:** Faster indexing (uses warm model after first chunk)  
**Typical use:** Once per repo, or after major changes

### During Search (MOST BENEFICIAL)
```bash
# Searching computes embeddings for each query
sia-code embed start
sia-code search "authentication"
sia-code search "http server"
sia-code search "database query"
```
**Benefit:** Near-instant results (<100ms per query)  
**Typical use:** Many times per day during development

### Recommended Workflow

**Daily workflow:**
```bash
# Morning: Start daemon
sia-code embed start

# Throughout the day: Search across repos
cd ~/project-1 && sia-code search "user auth"
cd ~/project-2 && sia-code search "api routes"
cd ~/project-3 && sia-code search "error handling"

# Evening: Daemon auto-unloads after 1 hour idle (saves memory)
# Next day: Daemon still running, model reloads on first search
```

---

## Auto-Unload Feature

The daemon automatically unloads models after **1 hour of inactivity** to save memory, but **keeps running** to provide instant reloading on the next request.

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    Daemon Lifecycle                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [Daemon Start]                                              │
│       │                                                      │
│       v                                                      │
│  Memory: 58 MB (no model loaded)                            │
│       │                                                      │
│       v                                                      │
│  [First Request] ──> Load model (3-5s)                      │
│       │                                                      │
│       v                                                      │
│  Memory: 1164 MB (model loaded)                             │
│  Subsequent requests: <100ms ⚡                              │
│       │                                                      │
│       v                                                      │
│  [1 hour idle] ──> Auto-unload model                        │
│       │                                                      │
│       v                                                      │
│  Memory: 58 MB (model unloaded, daemon still running)       │
│       │                                                      │
│       v                                                      │
│  [Next Request] ──> Reload model (2-3s)                     │
│       │                                                      │
│       v                                                      │
│  Memory: 1164 MB (model reloaded)                           │
│  Cycle repeats...                                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Benefits

1. **Memory efficiency:** Model unloaded when not in use
2. **No manual management:** Daemon keeps running, you don't need to restart it
3. **Fast reload:** Model reloads automatically on next request (~2-3s)
4. **Transparent:** Works automatically, no user intervention needed

### Configuration

Change idle timeout:

```bash
# Default: 1 hour
sia-code embed start

# Custom: 2 hours
sia-code embed start --idle-timeout 7200

# Custom: 30 minutes
sia-code embed start --idle-timeout 1800

# Disable auto-unload (never unload)
sia-code embed start --idle-timeout 999999999
```

---

## CLI Commands

### Start Daemon

```bash
# Start with default settings (1 hour idle timeout)
sia-code embed start

# Start with custom idle timeout (2 hours)
sia-code embed start --idle-timeout 7200

# Start in foreground (for debugging)
sia-code embed start --foreground

# Start with custom log file
sia-code embed start --log /tmp/embed-server.log
```

### Check Status

```bash
# Basic status
sia-code embed status

# Example output:
● Embedding server is running
  PID: 12345
  Device: cuda
  Memory: 1164.2 MB
  Idle timeout: 60 minutes
  Models loaded: BAAI/bge-base-en-v1.5

# Detailed status (shows idle time per model)
sia-code embed status --verbose

# Example output:
● Embedding server is running
  PID: 12345
  Device: cuda
  Memory: 1164.2 MB
  Idle timeout: 60 minutes
  Models loaded: BAAI/bge-base-en-v1.5

  Model Status:
    BAAI/bge-base-en-v1.5: ✓ loaded, idle 5.2m
```

### Stop Daemon

```bash
sia-code embed stop
```

---

## Memory Usage Comparison

### Without Daemon (Traditional)
```
Repo 1: 1164 MB (loads model per command)
Repo 2: 1164 MB (loads model per command)
Repo 3: 1164 MB (loads model per command)
────────────────────────────────────────
Total:  3492 MB
```

### With Daemon (Model Loaded)
```
Daemon: 1164 MB (shared across all repos)
Repo 1: Uses daemon (0 MB model)
Repo 2: Uses daemon (0 MB model)
Repo 3: Uses daemon (0 MB model)
────────────────────────────────────────
Total:  1164 MB (67% savings!)
```

### With Daemon (Model Unloaded After Idle)
```
Daemon: 58 MB (daemon running, model unloaded)
Repo 1: Uses daemon (0 MB model)
Repo 2: Uses daemon (0 MB model)
Repo 3: Uses daemon (0 MB model)
────────────────────────────────────────
Total:  58 MB (95% savings!)
```

---

## Performance Comparison

### Without Daemon
```
$ time sia-code search "authentication"
→ 4.9s (load model every time)

$ time sia-code search "user login"
→ 4.8s (load model again)

$ time sia-code search "session management"
→ 5.1s (load model again)
```

### With Daemon (Warm Model)
```
$ sia-code embed start
$ time sia-code search "authentication"
→ 4.9s (first request loads model)

$ time sia-code search "user login"
→ 0.2s ⚡ (24x faster!)

$ time sia-code search "session management"
→ 0.2s ⚡ (25x faster!)
```

### With Daemon (After Auto-Unload)
```
# 1 hour passes with no requests...
# Model unloaded (saves 1100 MB)

$ time sia-code search "authentication"
→ 2.3s (reload model, faster than cold start)

$ time sia-code search "user login"
→ 0.2s ⚡ (back to fast!)
```

---

## Best Practices

### ✅ DO

- **Start daemon once per day** for daily dev work
- **Let it run in background** - auto-unload handles memory
- **Use for multi-repo workflows** - biggest benefit with 2+ repos
- **Monitor with `status -v`** to see idle times

### ❌ DON'T

- **Don't restart daemon frequently** - it stays running and auto-manages
- **Don't worry about memory** - auto-unload frees memory after 1 hour
- **Don't manually stop/start** for memory - let auto-unload handle it

---

## Troubleshooting

### Daemon won't start
```bash
# Check if already running
sia-code embed status

# If stale, clean up
rm -f /tmp/sia-embed.sock /tmp/sia-embed.pid

# Try again
sia-code embed start
```

### Slow first query after idle
**This is expected!** Model is reloading after auto-unload.
- First query: 2-3s (reload)
- Subsequent: <100ms

### Model not unloading
Check timeout:
```bash
sia-code embed status --verbose
```
Look for "idle_timeout_minutes" and "idle_minutes" per model.

### Want to keep model loaded longer
```bash
# Stop current daemon
sia-code embed stop

# Restart with longer timeout (4 hours)
sia-code embed start --idle-timeout 14400
```

---

## Example Workflows

### Multi-Repo Development
```bash
# Morning
sia-code embed start

# Work on multiple projects
cd ~/frontend && sia-code search "button component"
cd ~/backend && sia-code search "api authentication"
cd ~/mobile && sia-code search "user profile"
# All searches are fast! ⚡

# Lunch break (1+ hour)
# Model auto-unloads, saves 1100 MB

# Afternoon
cd ~/frontend && sia-code search "navigation"
# Model reloads (2s), then fast again
```

### CI/CD Pipeline
```bash
# No daemon needed in CI - scripts run once
sia-code index .
sia-code search "TODO"
# Each command loads model individually (acceptable for CI)
```

### Personal Usage (Single Repo)
```bash
# Start daemon for speed boost
sia-code embed start

# Index once
sia-code index .

# Search many times throughout the day
sia-code search "auth"
sia-code search "database"
sia-code search "tests"
# All fast after first load ⚡
```

---

## Summary

| Aspect | Without Daemon | With Daemon + Auto-Unload |
|--------|----------------|---------------------------|
| **Startup time** | 4-5s every command | 4-5s first, 0.2s after |
| **Memory (active)** | N × 1164 MB | 1164 MB shared |
| **Memory (idle)** | N × 1164 MB | 58 MB (auto-unload) |
| **Management** | None needed | Starts once, auto-manages |
| **Best for** | CI/CD, scripts | Daily dev, multi-repo |

**Recommendation:** Start daemon for daily development work, let it auto-manage itself. Provides massive speed boost with minimal memory overhead thanks to auto-unload.
