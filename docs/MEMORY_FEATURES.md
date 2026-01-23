# Sia-Code Memory Features

The usearch backend includes a **project memory system** that tracks technical decisions, timeline events, and changelogs alongside code.

## Overview

Memory features help teams:
- **Track decisions** - Why was X chosen over Y?
- **Understand history** - What changed and when?
- **Share context** - Export/import decisions across teams
- **Maintain documentation** - Auto-generate from git history

## Features

### 1. Technical Decisions

Track architectural and implementation decisions with approval workflow.

**Workflow:**
```
Pending → Approved → Stored in Memory
   ↓
Rejected → Discarded
```

**Storage:**
- **Pending queue**: Max 100 decisions (FIFO)
- **Approved memory**: Permanent storage
- **Vector indexed**: Searchable alongside code

**Example Use Case:**
```python
# Record decision: "Why did we choose usearch over memvid?"
decision = Decision(
    title="Switch to usearch+SQLite backend",
    description="Replace memvid with usearch HNSW for better performance",
    reasoning="memvid hit 50MB cap, usearch gives 10x faster search + unlimited size",
    alternatives_considered=["Keep memvid", "Use Faiss", "Use ChromaDB"],
    decision="Use usearch with f16 quantization",
    status="approved"
)
backend.store_decision(decision)
```

**Search decisions:**
```bash
sia-code memory search "why usearch" --type decision
```

### 2. Timeline Events

Auto-extracted from git commit history.

**Sources:**
- Merge commits (features, PRs)
- Release tags
- Breaking changes
- Major refactors

**Example:**
```python
# Auto-extracted from git log
TimelineEvent(
    title="Add usearch backend",
    description="Implement usearch+SQLite storage backend",
    event_type="feature",
    timestamp=datetime(2026, 1, 22),
    metadata={"pr": "#123", "commit": "abc123"}
)
```

**Search timeline:**
```bash
sia-code memory timeline --since 2026-01-01
```

### 3. Changelogs

Auto-generated from git tags and release notes.

**Example:**
```python
ChangelogEntry(
    version="2.0.0",
    date=datetime(2026, 1, 22),
    changes=[
        "Added usearch+SQLite backend",
        "63% size reduction vs memvid",
        "Project memory system"
    ],
    breaking_changes=["Changed storage format"],
    migration_notes="Run `sia-code migrate` to convert from memvid"
)
```

**Generate changelog:**
```bash
sia-code memory changelog v1.0.0..v2.0.0
```

## Storage Architecture

```
.sia-code/
├── index.db (SQLite)
│   ├── decisions         # Pending queue (max 100, FIFO)
│   ├── approved_memory   # Permanent decisions
│   ├── timeline          # Git events
│   ├── changelogs        # Version history
│   └── memory_fts        # FTS5 search for memory
├── vectors.usearch       # Unified HNSW index
│   ├── chunks (1-999999)
│   ├── decisions (1000000-1999999)
│   ├── timeline (2000000-2999999)
│   └── changelogs (3000000-3999999)
└── memory.json           # Git-trackable export
```

## Git Collaboration

Export/import memory for team sharing:

```bash
# Export to memory.json
sia-code memory export

# Commit to git
git add .sia-code/memory.json
git commit -m "Update project memory"

# Team member imports
git pull
sia-code memory import
```

**memory.json format:**
```json
{
  "decisions": [
    {
      "id": 1,
      "title": "Switch to usearch backend",
      "status": "approved",
      "created_at": "2026-01-22T10:00:00"
    }
  ],
  "timeline": [...],
  "changelogs": [...]
}
```

## Python API

```python
from sia_code.storage import factory
from sia_code.core.models import Decision, TimelineEvent

# Create backend
backend = factory.create_backend(Path(".sia-code"))
backend.open_index()

# Store decision
decision = Decision(
    title="Use React for UI",
    reasoning="Team expertise + ecosystem",
    decision="React with TypeScript",
    status="pending"
)
backend.store_decision(decision)

# List pending decisions
pending = backend.list_decisions(status="pending")
for d in pending:
    print(f"{d.id}: {d.title}")

# Approve decision
backend.approve_decision(decision_id=1)

# Search memory
results = backend.search_semantic("why did we choose React?", k=5)
for r in results:
    if r.chunk.chunk_type == "decision":
        print(f"Decision: {r.chunk.metadata['title']}")

# Generate context for LLM
context = backend.generate_context(
    query="authentication design decisions",
    include_decisions=True,
    include_timeline=True
)
print(context)
```

## CLI Commands (Future)

```bash
# Decisions
sia-code memory add-decision "Use GraphQL for API"
sia-code memory list-decisions --status pending
sia-code memory approve 123
sia-code memory reject 456

# Timeline
sia-code memory timeline --since 2026-01-01
sia-code memory timeline --event-type feature

# Changelog
sia-code memory changelog v1.0.0..HEAD
sia-code memory changelog --format markdown

# Export/Import
sia-code memory export --output memory.json
sia-code memory import --input memory.json

# Search
sia-code memory search "why mongodb" --type decision
sia-code memory search "authentication" --type all

# Git integration
sia-code memory sync-git    # Auto-extract from git log
sia-code memory scan-tags   # Extract changelogs from tags
```

## Use Cases

### 1. Onboarding New Developers

```bash
# Show all major decisions
sia-code memory list-decisions --status approved

# Explain architecture choices
sia-code memory search "why microservices"
```

### 2. Architecture Documentation

```python
# Auto-generate ADR (Architecture Decision Record)
backend.generate_adr(decision_id=123, format="markdown")
```

### 3. Release Notes

```bash
# Auto-generate from git tags
sia-code memory changelog v2.0.0..v2.1.0 --format markdown > RELEASE_NOTES.md
```

### 4. Code Archaeology

```bash
# Understand why code exists
sia-code memory timeline --file src/auth/jwt.py
sia-code memory search "why JWT over sessions"
```

## Technical Details

### Decision FIFO Queue

- Max 100 pending decisions
- SQLite trigger auto-deletes oldest
- Prevents unbounded growth

```sql
CREATE TRIGGER enforce_decision_limit
AFTER INSERT ON decisions
WHEN (SELECT COUNT(*) FROM decisions WHERE status = 'pending') > 100
BEGIN
    DELETE FROM decisions
    WHERE id = (
        SELECT id FROM decisions
        WHERE status = 'pending'
        ORDER BY created_at ASC
        LIMIT 1
    );
END;
```

### Vector Key Prefixes

Unified index uses numeric ranges:

| Type | Range | Example |
|------|-------|---------|
| Chunks | 1-999,999 | 12345 |
| Decisions | 1M-1.9M | 1000042 |
| Timeline | 2M-2.9M | 2000013 |
| Changelogs | 3M-3.9M | 3000005 |

### Embedding Strategy

Memory items embedded same as code:
```python
vector = embed(f"{title}\n\n{description}")
```

Searchable alongside code chunks in hybrid search.

## Performance

| Operation | Time |
|-----------|------|
| Store decision | <10ms |
| Search memory | ~9s (same as code) |
| Export memory.json | <100ms |
| Import memory.json | <500ms |
| Sync git (100 commits) | ~2s |

## Limitations

1. **Search speed**: Same bottleneck as code search (~9s/query)
2. **No nested decisions**: Flat structure only
3. **Git sync manual**: Not automatic on index
4. **No branching**: Linear timeline only

## Future Enhancements

- [ ] CLI commands for all memory operations
- [ ] Auto-sync on `sia-code index`
- [ ] Decision templates (ADR, RFCs)
- [ ] Dependency tracking between decisions
- [ ] Decision versioning/amendments
- [ ] Slack/Discord integration for approvals
- [ ] Web UI for memory management
- [ ] LLM-assisted decision extraction from PRs

## Examples

See `tests/test_usearch_backend.py` for:
- `test_decision_workflow()` - Full approval flow
- `test_decision_fifo()` - FIFO queue behavior
- `test_timeline_events()` - Git event extraction
- `test_export_import_memory()` - Collaboration workflow
- `test_generate_context()` - LLM context generation
