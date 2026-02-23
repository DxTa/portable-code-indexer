---
name: sia-code
description: Compact local-first code search skill for CLI agents using ChunkHound-backed search/research and Sia project memory.
license: MIT
compatibility: opencode
version: 0.7.1
---

# Sia-Code Skill (Compact)

Use this skill when an agent needs to explore a codebase quickly, trace architecture, or store/retrieve project decisions.

This is a compact, repo-local variant intended for easy copy/paste into LLM CLI skill directories.

## Quick Start

```bash
# initialize once per repo
uvx sia-code init
uvx sia-code index .

# fast lexical search (ChunkHound-backed)
uvx sia-code search --regex "auth|login|token"

# architecture exploration (ChunkHound-backed)
uvx sia-code research "how does authentication flow work?"

# health check
uvx sia-code status
```

## Search + Research Backend

`sia-code search` and `sia-code research` are powered by ChunkHound CLI.
Sia's own memory/decision database remains unchanged.

Install once:

```bash
uv tool install chunkhound
```

## Search Modes

- `uvx sia-code search "query"`: default mode from config (`chunkhound.default_search_mode`)
- `uvx sia-code search --regex "pattern"`: lexical search (recommended for exact symbols)
- `uvx sia-code search --semantic-only "query"`: semantic search (requires embedding setup)

Supported flags:

- `-k, --limit <N>`: result count
- `--format json|table|csv`: output shaping in Sia wrapper

Compatibility notes (currently no-op with ChunkHound):

- `--no-deps`
- `--deps-only`
- `--no-filter`

## Multi-Hop Research

```bash
uvx sia-code research "how is config loaded?"
```

- Use for dependency tracing, call flow mapping, and architecture questions.
- `--hops`, `--graph`, and `--limit` are accepted for compatibility in Sia but ignored by ChunkHound CLI.

## Memory Workflow

```bash
# import timeline/changelogs from git
uvx sia-code memory sync-git --limit 0

# store a pending decision
uvx sia-code memory add-decision "Adopt sqlite-vec by default" \
  -d "Align with current backend defaults" \
  -r "Lower operational overhead"

# review and triage
uvx sia-code memory list --type decision --status pending
uvx sia-code memory approve 1 --category architecture

# recall context
uvx sia-code memory search "backend default" --type all
```

Notes:

- `memory sync-git` derives changelog entries from merge commits whose subject matches `Merge branch '...'`.
- Use `--limit 0` when you want to process all eligible git events.

## Agent-Friendly Session Pattern

```bash
# 1) verify index health
uvx sia-code status

# 2) initialize/index if needed
uvx sia-code init
uvx sia-code index .

# 3) investigate code
uvx sia-code search --regex "target_symbol"
uvx sia-code research "how does X work?"

# 4) record reusable decision
uvx sia-code memory add-decision "..." -d "..." -r "..."
```

## Troubleshooting

- If uninitialized: run `uvx sia-code init && uvx sia-code index .`
- If results look stale: run `uvx sia-code index --update` (this also syncs ChunkHound index)
- If memory add/search fails with embedding issues: run `uvx sia-code embed start`
- If ChunkHound is missing: run `uv tool install chunkhound`

## Notes

- Lexical search is often strong for code due to exact identifiers.
- Semantic research/search requires ChunkHound embedding/LLM provider setup.
- Keep this file short and operational; move deep theory to project docs.
