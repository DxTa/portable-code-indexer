# PCI Roadmap: Achieving ChunkHound Feature Parity

**Current Status:** PCI 0.1.0 - MVP Complete (95%)  
**Target:** Full ChunkHound Feature Parity  
**Estimated Effort:** 20-30 hours  
**Priority:** High (ChunkHound being replaced by Serena)

---

## Executive Summary

PCI is 95% complete and has a **superior storage architecture** (portable .mv2 files vs database). To achieve full ChunkHound feature parity, we need to implement 5 key features over 20-30 hours of focused development.

**Strategic Recommendation:** Complete PCI rather than migrate to ChunkHound, since ChunkHound is being deprecated in favor of Serena MCP.

---

## ChunkHound vs PCI: Gap Analysis

### What ChunkHound Has That PCI Doesn't

| Feature | ChunkHound | PCI | Gap |
|---------|------------|-----|-----|
| **Multi-hop Code Research** | ✅ Production | ❌ Empty file | **CRITICAL** |
| **MCP Server Integration** | ✅ Working | ❌ None | **HIGH** |
| **Incremental Indexing** | ✅ Working | ❌ Stub only | **MEDIUM** |
| **Code Graph Construction** | ✅ Implied | ❌ None | **HIGH** |
| **Cross-file Linking** | ✅ Working | ❌ None | **HIGH** |
| **Production Scale** | ✅ Tested | ⚠️ Untested | **MEDIUM** |
| **Dependency Tracing** | ✅ Working | ❌ None | **HIGH** |

### PCI's Advantages Over ChunkHound

| Feature | PCI | ChunkHound | Advantage |
|---------|-----|------------|-----------|
| **Storage** | Single .mv2 file | Database (DuckDB) | **Simpler** |
| **Portability** | Git-friendly | Database files | **Better** |
| **Setup** | Zero config | DB setup | **Easier** |
| **Codebase** | 660 lines, documented | Unknown size | **Cleaner** |
| **Type Safety** | Full Pydantic | Unknown | **Better** |
| **Embedding Flexibility** | OpenAI/Local/Custom | Unknown | **More flexible** |

---

## Priority 1: Multi-hop Code Research 🔥

**Estimated Effort:** 8-12 hours  
**Impact:** CRITICAL - This is ChunkHound's killer feature  
**File:** `pci/search/multi_hop.py` (currently empty)

### What It Does

Automatically discovers code relationships without manual follow-up queries:

```
User: "How does authentication work?"

Traditional Search:
  → Returns: login_handler function
  → User must manually search for: validate_token, check_db, User model
  → Multiple rounds of queries needed

Multi-hop Research:
  → Returns: Complete authentication flow
    - login_handler (entry point)
    - validate_token (called by login_handler)  
    - check_db (called by validate_token)
    - User model (used by check_db)
  → ONE query, complete picture
```

### Implementation Plan

#### Phase 1: Entity Extraction (2-3 hours)

```python
# pci/search/entity_extractor.py

class EntityExtractor:
    """Extract code entities from search results."""
    
    def extract_from_chunk(self, chunk: Chunk) -> list[Entity]:
        """Extract function calls, class references, imports."""
        entities = []
        
        # Parse chunk code with Tree-sitter
        tree = self.parser.parse_code(chunk.code, chunk.language)
        
        # Find function calls
        for node in self.find_nodes(tree, "call_expression"):
            entities.append(Entity(
                name=node.text,
                type="function_call",
                source_chunk=chunk.id
            ))
        
        # Find class references
        for node in self.find_nodes(tree, "type_identifier"):
            entities.append(Entity(
                name=node.text,
                type="class_reference",
                source_chunk=chunk.id
            ))
        
        # Find imports
        for node in self.find_nodes(tree, "import_statement"):
            entities.append(Entity(
                name=node.text,
                type="import",
                source_chunk=chunk.id
            ))
        
        return entities
```

#### Phase 2: Multi-hop Strategy (4-6 hours)

```python
# pci/search/multi_hop.py

from dataclasses import dataclass
from typing import Set

@dataclass
class CodeRelationship:
    """Represents a relationship between code entities."""
    from_entity: str
    to_entity: str
    relationship_type: str  # "calls", "imports", "extends", "uses"
    from_chunk: ChunkId
    to_chunk: ChunkId | None

class MultiHopSearchStrategy:
    """Multi-hop code research implementation."""
    
    def __init__(self, backend: MemvidBackend, extractor: EntityExtractor):
        self.backend = backend
        self.extractor = extractor
        self.max_hops = 2
    
    def research(
        self, 
        question: str, 
        max_hops: int = 2,
        max_results_per_hop: int = 5
    ) -> ResearchResult:
        """Perform multi-hop code research.
        
        Args:
            question: Natural language question
            max_hops: Maximum relationship hops
            max_results_per_hop: Results to explore per hop
            
        Returns:
            Complete research with relationships
        """
        visited_chunks: Set[ChunkId] = set()
        relationships: list[CodeRelationship] = []
        all_chunks: list[Chunk] = []
        
        # Hop 0: Initial semantic search
        initial_results = self.backend.search_semantic(
            question, 
            k=max_results_per_hop
        )
        
        for result in initial_results:
            chunk = result.chunk
            all_chunks.append(chunk)
            visited_chunks.add(chunk.id)
            
            # Extract entities from this chunk
            entities = self.extractor.extract_from_chunk(chunk)
            
            # Hop 1-N: Follow entity references
            for entity in entities:
                if len(visited_chunks) >= 50:  # Safety limit
                    break
                
                # Search for this entity
                entity_results = self.backend.search_semantic(
                    entity.name,
                    k=3
                )
                
                for entity_result in entity_results:
                    target_chunk = entity_result.chunk
                    
                    if target_chunk.id not in visited_chunks:
                        all_chunks.append(target_chunk)
                        visited_chunks.add(target_chunk.id)
                        
                        # Record relationship
                        relationships.append(CodeRelationship(
                            from_entity=chunk.symbol,
                            to_entity=target_chunk.symbol,
                            relationship_type=entity.type,
                            from_chunk=chunk.id,
                            to_chunk=target_chunk.id
                        ))
        
        return ResearchResult(
            question=question,
            chunks=all_chunks,
            relationships=relationships,
            hops_executed=max_hops
        )
    
    def build_call_graph(self, relationships: list[CodeRelationship]) -> dict:
        """Build call graph from relationships."""
        graph = {}
        
        for rel in relationships:
            if rel.from_entity not in graph:
                graph[rel.from_entity] = []
            
            graph[rel.from_entity].append({
                "target": rel.to_entity,
                "type": rel.relationship_type,
                "chunk": rel.to_chunk
            })
        
        return graph
```

#### Phase 3: CLI Integration (2-3 hours)

```python
# pci/cli.py - Add research command

@main.command()
@click.argument("question")
@click.option("--hops", type=int, default=2, help="Maximum hops")
@click.option("--graph", is_flag=True, help="Show call graph")
def research(question: str, hops: int, graph: bool):
    """Multi-hop code research.
    
    Example:
        pci research "How does authentication work?"
    """
    pci_dir = Path(".pci")
    if not pci_dir.exists():
        console.print("[red]Error: PCI not initialized.[/red]")
        sys.exit(1)
    
    backend = MemvidBackend(pci_dir / "index.mv2")
    backend.open_index()
    
    extractor = EntityExtractor()
    strategy = MultiHopSearchStrategy(backend, extractor)
    
    console.print(f"[dim]Researching: {question}[/dim]")
    
    with Progress() as progress:
        task = progress.add_task("Analyzing code...", total=hops)
        result = strategy.research(question, max_hops=hops)
        progress.update(task, completed=hops)
    
    # Display results
    console.print(f"\n[bold]Found {len(result.chunks)} related chunks[/bold]")
    console.print(f"[dim]Discovered {len(result.relationships)} relationships[/dim]\n")
    
    # Show chunks
    for i, chunk in enumerate(result.chunks[:10], 1):
        console.print(f"{i}. [cyan]{chunk.symbol}[/cyan]")
        console.print(f"   {chunk.file_path}:{chunk.start_line}")
        console.print()
    
    # Show call graph if requested
    if graph:
        call_graph = strategy.build_call_graph(result.relationships)
        console.print("\n[bold]Call Graph:[/bold]")
        for entity, targets in call_graph.items():
            console.print(f"  {entity}")
            for target in targets:
                console.print(f"    → {target['target']} ({target['type']})")
```

### Testing Strategy

```bash
# Test on PCI codebase itself
cd /home/dxta/dev/portable-code-index/pci

# Research questions
pci research "How does indexing work?"
pci research "What calls the chunker?"
pci research "How is configuration loaded?"

# With call graph
pci research "How does search work?" --graph
```

### Success Criteria

- ✅ Automatically discovers 2-3 levels of code relationships
- ✅ Returns complete flow for architectural questions
- ✅ Builds accurate call graphs
- ✅ <5 second response time for typical queries
- ✅ Handles circular dependencies gracefully

---

## Priority 2: MCP Server Integration 🔌

**Estimated Effort:** 4-6 hours  
**Impact:** HIGH - Makes PCI usable by LLM agents  
**File:** New package `pci-mcp-server/`

### What It Enables

```python
# LLM agents can use PCI directly via MCP
@general
"Use PCI to research how authentication works in this codebase"

→ Agent calls: mcp__pci__code_research("authentication flow")
→ Returns: Complete authentication architecture
→ Agent summarizes for user
```

### Implementation Plan

#### Phase 1: MCP Server Package (2-3 hours)

```python
# pci-mcp-server/server.py

from mcp import MCPServer
from pci.storage.backend import MemvidBackend
from pci.search.multi_hop import MultiHopSearchStrategy

class PCIServer(MCPServer):
    """MCP server exposing PCI tools."""
    
    def __init__(self, index_path: Path):
        super().__init__(name="pci")
        self.backend = MemvidBackend(index_path)
        self.backend.open_index()
    
    @self.tool(
        name="search_semantic",
        description="Semantic code search using embeddings"
    )
    async def search_semantic(self, query: str, limit: int = 10):
        """Search codebase semantically."""
        results = self.backend.search_semantic(query, k=limit)
        return [
            {
                "symbol": r.chunk.symbol,
                "file_path": r.chunk.file_path,
                "start_line": r.chunk.start_line,
                "code": r.chunk.code[:500],
                "score": r.score
            }
            for r in results
        ]
    
    @self.tool(
        name="search_regex",
        description="Lexical search using BM25 ranking"
    )
    async def search_regex(self, pattern: str, limit: int = 10):
        """Search codebase with regex/keywords."""
        results = self.backend.search_lexical(pattern, k=limit)
        return [self._format_result(r) for r in results]
    
    @self.tool(
        name="code_research",
        description="Multi-hop code research for architectural questions"
    )
    async def code_research(self, question: str, max_hops: int = 2):
        """Research code architecture with multi-hop analysis."""
        strategy = MultiHopSearchStrategy(self.backend)
        result = strategy.research(question, max_hops=max_hops)
        
        return {
            "question": result.question,
            "chunks_found": len(result.chunks),
            "relationships": [
                {
                    "from": r.from_entity,
                    "to": r.to_entity,
                    "type": r.relationship_type
                }
                for r in result.relationships
            ],
            "top_chunks": [
                self._format_chunk(c) 
                for c in result.chunks[:10]
            ]
        }
    
    @self.tool(
        name="get_stats",
        description="Get PCI index statistics"
    )
    async def get_stats(self):
        """Return index statistics."""
        return self.backend.get_stats()

# Launch script
if __name__ == "__main__":
    server = PCIServer(Path(".pci/index.mv2"))
    server.run()
```

#### Phase 2: Integration with OpenCode (1-2 hours)

```json
// ~/.config/opencode/mcp-servers.json
{
  "pci": {
    "command": "pkgx",
    "args": ["python", "-m", "pci_mcp_server", "--index", ".pci/index.mv2"],
    "description": "PCI code intelligence server"
  }
}
```

#### Phase 3: Agent Configuration (1 hour)

Update `AGENTS.md` to reference PCI:

```markdown
### ChunkHound Code Research

**When to use `chunkhound_code_research` OR `pci_code_research`:**
- Before implementing features - find existing patterns
- During debugging - map complete flows
- Refactoring prep - understand all dependencies
- Code archaeology - learn unfamiliar systems
```

### Success Criteria

- ✅ MCP server starts without errors
- ✅ All 4 tools (search_semantic, search_regex, code_research, get_stats) work
- ✅ LLM agents can call PCI via MCP
- ✅ Integrated into OpenCode workflow

---

## Priority 3: Incremental Indexing ⚡

**Estimated Effort:** 6-8 hours  
**Impact:** MEDIUM - 10x faster re-indexing  
**File:** `pci/indexer/coordinator.py` + `.pci/cache/file_hashes.json`

### What It Does

```bash
# First index: 20 seconds for 100 files
pci index src/

# Change 2 files
vim src/main.py src/utils.py

# Re-index: Only 2 files, ~0.5 seconds (10x faster)
pci index src/ --update
```

### Implementation Plan

#### Phase 1: Hash Storage (2-3 hours)

```python
# pci/indexer/hash_cache.py

import hashlib
import json
from pathlib import Path
from dataclasses import dataclass

@dataclass
class FileHash:
    """File hash for change detection."""
    path: str
    hash: str
    mtime: float
    chunks: list[ChunkId]

class HashCache:
    """Manages file hash cache for incremental indexing."""
    
    def __init__(self, cache_path: Path):
        self.cache_path = cache_path
        self.hashes: dict[str, FileHash] = {}
        self.load()
    
    def load(self):
        """Load cache from disk."""
        if self.cache_path.exists():
            with open(self.cache_path) as f:
                data = json.load(f)
                self.hashes = {
                    k: FileHash(**v) for k, v in data.items()
                }
    
    def save(self):
        """Save cache to disk."""
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, 'w') as f:
            json.dump(
                {k: vars(v) for k, v in self.hashes.items()},
                f,
                indent=2
            )
    
    def compute_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file."""
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def has_changed(self, file_path: Path) -> bool:
        """Check if file has changed since last index."""
        path_str = str(file_path)
        
        if path_str not in self.hashes:
            return True  # New file
        
        cached = self.hashes[path_str]
        
        # Quick check: modification time
        current_mtime = file_path.stat().st_mtime
        if current_mtime != cached.mtime:
            # Verify with hash (mtime can be unreliable)
            current_hash = self.compute_hash(file_path)
            return current_hash != cached.hash
        
        return False
    
    def update(self, file_path: Path, chunks: list[ChunkId]):
        """Update cache entry for file."""
        self.hashes[str(file_path)] = FileHash(
            path=str(file_path),
            hash=self.compute_hash(file_path),
            mtime=file_path.stat().st_mtime,
            chunks=chunks
        )
```

#### Phase 2: Incremental Coordinator (3-4 hours)

```python
# pci/indexer/coordinator.py - Add incremental mode

class IndexingCoordinator:
    # ... existing code ...
    
    def index_directory_incremental(
        self, 
        directory: Path,
        cache: HashCache
    ) -> dict:
        """Index only changed files."""
        files = self._discover_files(directory)
        
        stats = {
            "total_files": len(files),
            "changed_files": 0,
            "skipped_files": 0,
            "indexed_files": 0,
            "total_chunks": 0,
            "deleted_chunks": 0,
            "errors": [],
        }
        
        for file_path in files:
            # Check if file changed
            if not cache.has_changed(file_path):
                stats["skipped_files"] += 1
                continue
            
            stats["changed_files"] += 1
            
            try:
                # Delete old chunks for this file
                if str(file_path) in cache.hashes:
                    old_chunks = cache.hashes[str(file_path)].chunks
                    for chunk_id in old_chunks:
                        self.backend.delete_chunk(chunk_id)
                        stats["deleted_chunks"] += 1
                
                # Index file
                language = Language.from_extension(file_path.suffix)
                if not self.chunker.engine.is_supported(language):
                    continue
                
                chunks = self.chunker.chunk_file(file_path, language)
                
                if chunks:
                    chunk_ids = self.backend.store_chunks_batch(chunks)
                    cache.update(file_path, chunk_ids)
                    
                    stats["indexed_files"] += 1
                    stats["total_chunks"] += len(chunks)
                    
            except Exception as e:
                stats["errors"].append(f"{file_path}: {str(e)}")
        
        # Save updated cache
        cache.save()
        
        return stats
```

#### Phase 3: CLI Update Command (1 hour)

```python
# pci/cli.py - Modify index command

@main.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--update", is_flag=True, help="Re-index changed files only")
def index(path: str, update: bool):
    """Index codebase for search."""
    pci_dir = Path(".pci")
    config = Config.load(pci_dir / "config.json")
    backend = MemvidBackend(pci_dir / "index.mv2")
    backend.open_index()
    
    coordinator = IndexingCoordinator(config, backend)
    
    if update:
        # Incremental indexing
        cache = HashCache(pci_dir / "cache" / "file_hashes.json")
        stats = coordinator.index_directory_incremental(Path(path), cache)
        
        console.print(f"\n✓ Incremental indexing complete")
        console.print(f"  Changed files: {stats['changed_files']}")
        console.print(f"  Skipped files: {stats['skipped_files']}")
        console.print(f"  Indexed files: {stats['indexed_files']}/{stats['total_files']}")
    else:
        # Full indexing
        stats = coordinator.index_directory(Path(path))
        # ... existing code ...
```

### Success Criteria

- ✅ Unchanged files skipped (0 processing time)
- ✅ Changed files re-indexed correctly
- ✅ 10x speedup for typical workflows (2 changed files)
- ✅ Hash cache persists across sessions
- ✅ Old chunks deleted before new chunks added

---

## Priority 4: Production Hardening 🛡️

**Estimated Effort:** 12-16 hours  
**Impact:** MEDIUM - Reliability at scale  

### Large Codebase Testing (4-6 hours)

Test on real-world codebases:

```bash
# Clone large repos
git clone https://github.com/django/django
git clone https://github.com/pallets/flask
git clone https://github.com/encode/httpx

# Index each
pci index django/      # ~1,000 Python files
pci index flask/       # ~200 Python files
pci index httpx/       # ~150 Python files

# Measure performance
time pci index django/
# Target: <5 minutes for 1,000 files

# Test search
pci search --regex "authentication"
# Target: <100ms
```

**What to measure:**
- Indexing time per file
- Memory usage (peak and steady-state)
- Index file size growth
- Search query latency
- Crash recovery

### Error Recovery (3-4 hours)

```python
# pci/indexer/coordinator.py - Add retry logic

class IndexingCoordinator:
    def index_file_with_retry(
        self, 
        file_path: Path,
        max_retries: int = 3
    ) -> list[Chunk]:
        """Index file with exponential backoff retry."""
        for attempt in range(max_retries):
            try:
                return self._index_file(file_path)
            except MemoryError:
                # Don't retry memory errors
                raise
            except Exception as e:
                if attempt == max_retries - 1:
                    # Final attempt failed
                    self.logger.error(f"Failed to index {file_path}: {e}")
                    raise
                
                # Exponential backoff
                wait_time = 2 ** attempt
                self.logger.warning(
                    f"Retry {attempt + 1}/{max_retries} for {file_path} "
                    f"after {wait_time}s"
                )
                time.sleep(wait_time)
```

### Query Optimization (3-4 hours)

```python
# pci/search/optimizer.py

class QueryOptimizer:
    """Optimize search queries for performance."""
    
    def optimize_query(self, query: str) -> str:
        """Preprocess query for better results."""
        # Remove stopwords
        stopwords = {'the', 'a', 'an', 'in', 'on', 'at'}
        words = [w for w in query.split() if w.lower() not in stopwords]
        
        # Stem technical terms
        stemmed = [self.stem_code_term(w) for w in words]
        
        # Add synonyms for common code terms
        synonyms = self.expand_synonyms(stemmed)
        
        return ' '.join(synonyms)
    
    def stem_code_term(self, term: str) -> str:
        """Stem code-specific terms."""
        # handler/handle → handl
        # validator/validate → valid
        # processor/process → process
        patterns = {
            r'handler$': 'handl',
            r'validator$': 'valid',
            r'processor$': 'process',
        }
        
        for pattern, replacement in patterns.items():
            term = re.sub(pattern, replacement, term)
        
        return term
```

### Memory Profiling (2-3 hours)

```python
# Test with memory_profiler
from memory_profiler import profile

@profile
def test_large_index():
    coordinator = IndexingCoordinator(config, backend)
    coordinator.index_directory(Path("large_codebase/"))
    
# Run profiling
python -m memory_profiler test_profiling.py

# Identify bottlenecks
# - Chunk storage batching
# - Parser memory leaks
# - Search result caching
```

### Success Criteria

- ✅ Successfully index 1,000+ file codebases
- ✅ Memory usage <2GB for 10,000 chunks
- ✅ Search latency <200ms for 10,000 chunks
- ✅ Graceful failure for corrupt files
- ✅ Automatic retry for transient errors

---

## Priority 5: Documentation & Examples 📚

**Estimated Effort:** 6-8 hours  
**Impact:** LOW - Usability and adoption

### API Documentation (2-3 hours)

```python
# Generate API docs with Sphinx
pip install sphinx sphinx-rtd-theme

# docs/conf.py
project = 'PCI'
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.napoleon']

# Generate
sphinx-apidoc -o docs/api pci/
sphinx-build -b html docs/ docs/_build/
```

### Usage Examples (2-3 hours)

```markdown
# docs/examples.md

## Example 1: Basic Code Search

\`\`\`bash
# Initialize
cd my-project
pci init

# Index
pci index src/

# Search
pci search --regex "authentication"
pci search "user login flow"
\`\`\`

## Example 2: Multi-hop Research

\`\`\`bash
# Research architectural questions
pci research "How does data flow through the API?"
pci research "What components handle user authentication?"
pci research "How are errors logged and reported?"
\`\`\`

## Example 3: Incremental Updates

\`\`\`bash
# Initial index
pci index src/

# Make changes
vim src/main.py

# Fast re-index (only changed files)
pci index src/ --update
\`\`\`

## Example 4: Python API

\`\`\`python
from pci import PCI

# Initialize
pci = PCI(index_path=".pci/index.mv2")

# Search
results = pci.search("authentication", mode="semantic")

for result in results:
    print(f"{result.chunk.symbol} - {result.score}")
    print(result.chunk.code)

# Research
research = pci.research("How does login work?", max_hops=2)
print(f"Found {len(research.chunks)} related components")
\`\`\`
```

### Integration Guides (2 hours)

```markdown
# docs/integrations.md

## VSCode Extension

Install the PCI VSCode extension:
\`\`\`bash
code --install-extension pci-vscode
\`\`\`

## MCP Server for LLM Agents

Configure in `~/.config/opencode/mcp-servers.json`:
\`\`\`json
{
  "pci": {
    "command": "pci-mcp-server",
    "args": ["--index", ".pci/index.mv2"]
  }
}
\`\`\`

## CI/CD Integration

\`\`\`yaml
# .github/workflows/pci-index.yml
name: Update Code Index

on: [push]

jobs:
  index:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install PCI
        run: pip install pci
      - name: Index codebase
        run: pci index src/ --update
      - name: Upload index
        uses: actions/upload-artifact@v2
        with:
          name: code-index
          path: .pci/
\`\`\`
```

---

## Implementation Timeline

### Phase 1: Core Features (12-18 hours)
**Week 1-2**

- [ ] Day 1-2: Multi-hop research implementation (8-12h)
  - Entity extraction
  - Multi-hop strategy
  - CLI integration
  
- [ ] Day 3: MCP server package (4-6h)
  - Server implementation
  - Tool definitions
  - Testing

### Phase 2: Production Ready (12-16 hours)
**Week 3-4**

- [ ] Day 4-5: Incremental indexing (6-8h)
  - Hash cache
  - Incremental coordinator
  - CLI update command
  
- [ ] Day 6-8: Production hardening (12-16h)
  - Large codebase testing
  - Error recovery
  - Query optimization
  - Memory profiling

### Phase 3: Polish (6-8 hours)
**Week 5**

- [ ] Day 9-10: Documentation (6-8h)
  - API docs
  - Usage examples
  - Integration guides

**Total Timeline: 5 weeks (20-30 hours total effort)**

---

## Success Metrics

### Feature Parity Achieved When:

1. **Multi-hop Research** ✅
   - Automatically discovers 2+ levels of relationships
   - Returns complete architectural flows
   - <5 second response time

2. **MCP Integration** ✅
   - All 4 tools exposed via MCP
   - Works with LLM agents
   - Integrated into AGENTS.md workflow

3. **Incremental Indexing** ✅
   - Detects changed files accurately
   - 10x faster than full re-index
   - Persistent hash cache

4. **Production Scale** ✅
   - Handles 1,000+ file codebases
   - Memory usage <2GB for 10,000 chunks
   - Search latency <200ms

5. **Documentation** ✅
   - API reference complete
   - 5+ usage examples
   - Integration guides published

---

## Alternative: Migrate to Serena MCP

Since ChunkHound is being replaced by Serena MCP, consider this path:

### Pros
- ✅ More advanced than ChunkHound (LSP-based)
- ✅ Already integrated into OpenCode ecosystem
- ✅ Actively maintained

### Cons
- ❌ Different architecture (language server vs AST)
- ❌ Less control over implementation
- ❌ May not support portable .mv2 storage

### Recommendation
**Complete PCI to parity**, then evaluate Serena MCP integration as a complementary tool rather than replacement. PCI's portable storage is a unique advantage.

---

## Conclusion

**To achieve ChunkHound feature parity, PCI needs:**

1. ✅ **Multi-hop code research** (8-12h) - CRITICAL
2. ✅ **MCP server integration** (4-6h) - HIGH PRIORITY
3. ✅ **Incremental indexing** (6-8h) - MEDIUM PRIORITY
4. ✅ **Production hardening** (12-16h) - MEDIUM PRIORITY
5. ✅ **Documentation** (6-8h) - LOW PRIORITY

**Total effort: 20-30 hours over 5 weeks**

Given PCI is already 95% complete with superior storage architecture, completing these features is the recommended path forward. ChunkHound is being deprecated anyway, so building PCI to production quality positions it as the superior replacement.

---

**Next Action:** Implement Priority 1 (Multi-hop Research) to unlock ChunkHound's killer feature.

**Status:** Ready to begin implementation  
**Updated:** 2026-01-11
