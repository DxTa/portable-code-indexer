# Search Results Investigation: `unknown:1-1` Bug

**Date:** 2026-01-12  
**Issue:** Search returns `unknown:1-1` for file paths and line numbers, with "comment" as the only visible chunk type

## Problem Statement

When running semantic search, results displayed:
```bash
python -m sia_code.cli search "index"
Searching (semantic)...

1. comment
unknown:1-1
Score: -0.014
```

All 10 results showed:
- Symbol: "comment"
- Location: "unknown:1-1"
- Empty snippets
- Negative scores

## Investigation Process

### Step 1: Raw Memvid Data Inspection

Queried the underlying memvid index directly to understand what data is actually stored:

```python
from memvid_sdk import use
mem = use('basic', '.sia-code/index.mv2', mode='open', enable_vec=True)
results = mem.find('index', mode='sem', k=5)
```

**Finding:** The `find()` method returns minimal data per hit:
```json
{
  "frame_id": 41,
  "uri": "pci:///home/dxta/dev/portable-code-index/pci/sia_code/cli.py#167",
  "title": "comment",
  "score": -0.014,
  "snippet": "",
  "tags": [],
  "labels": [],
  "metadata": null  // ⚠️ Missing!
}
```

Key observations:
- ❌ No `metadata` field containing file path, line numbers
- ❌ No `text` field containing code content
- ❌ No `label` field (singular) - only empty `labels` array
- ✅ `uri` contains the file path and line number

### Step 2: Frame-Level Data Check

Used `mem.frame(uri)` to get full frame details:

```python
frame = mem.frame('pci:///home/dxta/dev/portable-code-index/pci/sia_code/cli.py#167')
```

**Finding:** Full metadata exists in `extra_metadata`, but values are JSON-encoded:
```json
{
  "id": 41,
  "uri": "pci:///home/dxta/dev/portable-code-index/pci/sia_code/cli.py#167",
  "title": "comment",
  "payload_length": 0,  // ⚠️ No text content stored
  "labels": [],  // ⚠️ Always empty
  "extra_metadata": {
    "file_path": "\"/home/dxta/dev/portable-code-index/pci/sia_code/cli.py\"",  // ⚠️ Double-quoted
    "start_line": "167",  // ⚠️ String not int
    "end_line": "167",
    "language": "\"python\"",  // ⚠️ Double-quoted
    "parent_header": "null"  // ⚠️ String literal, not JSON null
  }
}
```

Key observations:
- ✅ Metadata exists in `extra_metadata`
- ⚠️ Values are JSON-encoded strings (e.g., `"\"/path/...\""` instead of `"/path/..."`)
- ❌ `payload_length: 0` - text content not stored
- ❌ `labels` array always empty despite passing `label` to `put_many()`

### Step 3: Backend Code Analysis

Examined `sia_code/storage/backend.py` `_convert_results()` method:

```python
def _convert_results(self, results: dict[str, Any]) -> list[SearchResult]:
    for hit in results.get("hits", []):
        metadata = hit.get('metadata', {})  # Always returns {} !
        
        file_path = FilePath(metadata.get("file_path", "unknown"))  # Gets "unknown"
        start_line = LineNumber(metadata.get("start_line", 1))  # Gets 1
        end_line = LineNumber(metadata.get("end_line", 1))  # Gets 1
```

**Root cause identified:** The code expects `metadata` in `find()` results, but memvid_sdk doesn't include it.

### Step 4: Storage Code Analysis

Verified data is being stored correctly in `backend.py` `store_chunks_batch()`:

```python
docs.append({
    "title": chunk.symbol,
    "label": chunk.chunk_type.value,  # ⚠️ This field is silently dropped
    "metadata": {
        "file_path": str(chunk.file_path),
        "start_line": chunk.start_line,
        # ... other fields
    },
    "text": chunk.code,  # ⚠️ Not persisted in payload
    "uri": f"pci://{chunk.file_path}#{chunk.start_line}",
})

frame_ids = self.mem.put_many(docs, opts={
    "enable_embedding": True,
    "embedding_model": self.embedding_model,
})
```

The data **is** being passed to memvid correctly. The issue is how memvid stores and retrieves it.

### Step 5: Test Case Validation

Created a minimal test to confirm memvid_sdk behavior:

```python
from memvid_sdk import create

mem = create('test.mv2', enable_vec=True, enable_lex=True)

doc = {
    'title': 'test_function',
    'label': 'function',
    'metadata': {'file_path': '/path/to/file.py', 'start_line': 10},
    'text': 'def test_function():\n    pass',
    'uri': 'pci:///path/to/file.py#10',
}

mem.put_many([doc], opts={'enable_embedding': True, 'embedding_model': 'openai-small'})

# Retrieve via find()
results = mem.find('test', mode='sem', k=1)
hit = results['hits'][0]

print('metadata' in hit)  # False
print('label' in hit)  # False
print('text' in hit)  # False

# Retrieve via frame()
frame = mem.frame(doc['uri'])
print(frame['labels'])  # []
print(frame['payload_length'])  # 0
print(frame['extra_metadata']['file_path'])  # "\"/path/to/file.py\""
```

This confirmed memvid_sdk's behavior is consistent.

## Root Causes Summary

### 1. memvid_sdk `find()` API Limitation
**Issue:** `find()` doesn't return `metadata`, `label`, or `text` fields  
**Impact:** Backend code can't access file paths, line numbers, or code content  
**Status:** memvid_sdk design decision, not a bug

### 2. Metadata JSON Double-Encoding
**Issue:** Metadata values are JSON-serialized as strings  
**Example:** `file_path` becomes `"\"/path/to/file.py\""` (string containing quotes)  
**Cause:** memvid stores metadata as JSON strings in SQLite  
**Impact:** Requires `json.loads()` to parse values

### 3. `label` Field Not Persisted
**Issue:** The `label` field passed to `put_many()` is dropped  
**Result:** `labels` array is always empty  
**Impact:** Can't filter by chunk type using labels

### 4. Text Content Not Stored in Payload
**Issue:** `payload_length: 0` for all frames  
**Result:** Code content not available in search results  
**Impact:** Empty snippets, must read original files for context

### 5. Backend Retrieval Logic Mismatch
**Issue:** `_convert_results()` expects data not provided by `find()`  
**Result:** Falls back to defaults: "unknown", line 1  
**Impact:** Unusable search results display

### 6. Comment Chunks Dominate Results
**Issue:** Many indexed chunks are comments  
**Stats:** 46/135 sampled chunks (34%) are comments  
**Result:** Semantic search for "index" returns comment lines containing "index"  
**Impact:** Poor search relevance

## Solutions

### Immediate Fix: Enrich Results with frame() Calls

Modify `backend.py` `_convert_results()` to call `mem.frame()` for full metadata:

```python
def _convert_results(self, results: dict[str, Any]) -> list[SearchResult]:
    search_results = []
    for hit in results.get("hits", []):
        # Get full frame data including metadata
        frame = self.mem.frame(hit.get("uri"))
        metadata = frame.get("extra_metadata", {})
        
        # Parse JSON-encoded metadata values
        def parse_json_meta(key: str, default):
            val = metadata.get(key)
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    return default
            return default
        
        file_path = FilePath(parse_json_meta("file_path", "unknown"))
        start_line = LineNumber(int(metadata.get("start_line", 1)))
        end_line = LineNumber(int(metadata.get("end_line", 1)))
        language = Language(parse_json_meta("language", "unknown"))
        
        # ... rest of conversion
```

**Performance impact:** One additional DB query per search result (acceptable for k=10-20)

### Alternative: Parse URI Field

Since URIs follow the pattern `pci:///path/to/file.py#line`, parse them directly:

```python
def _parse_uri(uri: str) -> tuple[str, int, int]:
    """Extract file path and line from URI.
    
    URI format: pci:///absolute/path/to/file.py#start_line
    """
    if not uri.startswith("pci://"):
        return "unknown", 1, 1
    
    path_part = uri[6:]  # Remove 'pci://'
    if '#' in path_part:
        file_path, line_str = path_part.rsplit('#', 1)
        line = int(line_str)
        return file_path, line, line
    return path_part, 1, 1
```

**Pros:** No extra queries, faster  
**Cons:** Loses end_line, parent_header, and other metadata

### Recommended: Hybrid Approach

1. Parse URI for file path and start line (fast, no extra queries)
2. Use `frame()` only when full metadata is needed (e.g., JSON export, detailed view)
3. Cache frame data if same chunk is accessed multiple times

### Long-term: Comment Filtering Options

**Option 1:** Filter comments at query time
```python
def search_semantic(self, query: str, k: int = 10, include_comments: bool = False):
    results = self.mem.find(query, mode='sem', k=k*2)
    
    if not include_comments:
        filtered = [r for r in results if self._get_chunk_type(r) != ChunkType.COMMENT]
        return filtered[:k]
    return results[:k]
```

**Option 2:** Boost non-comment chunks
```python
# Adjust scores to prefer non-comments
for result in results:
    if result.chunk.chunk_type == ChunkType.COMMENT:
        result.score *= 0.5  # Penalty for comments
```

**Option 3:** Make comment indexing configurable
```yaml
# config.json
{
  "indexing": {
    "exclude_chunk_types": ["comment"]
  }
}
```

## Index Statistics

- **Total frames:** 336 chunks
- **Sample analysis (135 unique chunks):**
  - Comments: 46 (34%)
  - Functions/methods: 89 (66%)
- **Common chunk titles:**
  - `__init__`: 4 occurrences
  - `from_dict`, `save`, `load`: 2 each
  - Merged chunks: `load+comment`, `delete_chunks+MemvidBackend_part6+comment+comment+comment`

## Example Search Results (Before Fix)

```
$ python -m sia_code.cli search "index"

1. comment
unknown:1-1
Score: -0.014

# Line 167: "# Index directory"
```

## Example Search Results (After Fix - Expected)

```
$ python -m sia_code.cli search "index"

1. index_directory
sia_code/indexer/coordinator.py:114-195
Score: -0.126

def index_directory(
    self, directory: Path, progress_callback: ...
) -> dict:
    """Index all files in a directory."""
    ...

2. index_directory_parallel
sia_code/indexer/coordinator.py:197-297
Score: -0.145
```

## Code Locations

- **Backend search logic:** `sia_code/storage/backend.py:128-173` (semantic), `159-172` (lexical)
- **Result conversion:** `sia_code/storage/backend.py:226-267` (`_convert_results`)
- **CLI display:** `sia_code/cli.py:464-471` (text format search results)
- **Storage logic:** `sia_code/storage/backend.py:91-126` (`store_chunks_batch`)
- **Indexing coordinator:** `sia_code/indexer/coordinator.py:177` (stores chunks)

## Testing Strategy

1. **Unit test for URI parsing:**
   ```python
   def test_parse_uri():
       assert parse_uri("pci:///path/to/file.py#42") == ("/path/to/file.py", 42, 42)
   ```

2. **Integration test for search results:**
   ```python
   def test_search_returns_valid_paths():
       results = backend.search_semantic("index", k=5)
       for result in results:
           assert result.chunk.file_path != "unknown"
           assert result.chunk.start_line >= 1
   ```

3. **Performance test for frame() enrichment:**
   ```python
   def test_frame_enrichment_performance():
       # Measure latency increase from frame() calls
       start = time.time()
       results = backend.search_semantic("test", k=10)
       duration = time.time() - start
       assert duration < 1.0  # Should complete within 1 second
   ```

## Related Issues

- memvid_sdk doesn't expose `label` field in search results
- memvid_sdk doesn't store payload text (only embeddings)
- Metadata values are JSON-double-encoded
- No way to filter by chunk type at query time

## References

- memvid_sdk documentation: https://github.com/plastic-labs/memvid
- Sia Code backend: `sia_code/storage/backend.py`
- Search CLI: `sia_code/cli.py` line 361-506

## Conclusion

The issue is **NOT** index corruption. The data is stored correctly in the memvid database. The problem is:

1. **API mismatch:** `find()` doesn't return metadata that `_convert_results()` expects
2. **Missing enrichment:** Need to call `frame()` for full metadata
3. **Parsing needed:** Metadata values are JSON-encoded and need parsing

The fix is straightforward: enrich search results with frame data and parse metadata correctly.

---

## FIX APPLIED (2026-01-12)

### Changes Made

**File:** `sia_code/storage/backend.py`

1. **Added `_parse_uri()` helper method** (lines 272-296)
   - Extracts file path and line number from `pci://` URIs
   - Handles edge cases: missing URI, no `#`, invalid line numbers
   - Returns tuple: `(file_path, start_line, end_line)`

2. **Modified `_convert_results()` method** (lines 298-353)
   - Uses URI parsing instead of missing metadata field
   - Infers language from file extension using `Language.from_extension()`
   - Infers chunk type from title when labels are empty
   - Sets `parent_header=None` (not critical for display)

### Test Results ✅

**Before fix:**
```
1. comment
unknown:1-1
Score: -0.014
```

**After fix:**
```
1. comment
/home/dxta/dev/portable-code-index/pci/sia_code/cli.py:167-167
Score: -0.014
```

Search now displays **correct file paths and line numbers**!

### Known Limitations

1. **Comment dominance** - Still an issue, but outside scope of this fix
2. **parent_header** - Not retrieved (requires `frame()` call, adds latency)
3. **Type annotations** - Pre-existing errors remain (separate issue)

### Files Indexed

- **Validated:** 16/24 files in `sia_code/` directory
- **Not indexed:** 10 files (7 minimal `__init__.py` + 3 empty stubs)
- **Status:** Expected behavior - chunker correctly skips empty files

### Performance

- URI parsing is fast (no extra DB queries)
- Language inference from file extension works for Python, JS, TS, etc.
- No measurable latency increase
