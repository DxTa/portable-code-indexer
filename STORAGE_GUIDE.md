# PCI Storage Guide

## Where Does PCI Store Data?

PCI uses a **local-first** approach - all data is stored in the **current directory** where you run the commands.

### Directory Structure

When you run `pci init`, it creates a hidden `.pci/` directory:

```
your-project/              ← Your codebase
├── src/
│   └── main.py
├── tests/
├── README.md
└── .pci/                  ← PCI storage (created here)
    ├── config.json        ← Configuration file
    ├── index.mv2          ← Memvid storage (ALL your indexed code)
    └── cache/
        └── file_hashes.json  ← For incremental indexing
```

### The .mv2 File

**Everything** is stored in the single `index.mv2` file:
- Code chunks
- Embeddings (if enabled)
- Search indexes (lexical + vector)
- Metadata

**File format:** Memvid v2 (custom binary format)  
**Size:** ~71 KB empty, grows with indexed code  
**Portable:** Can copy/move the file anywhere

---

## Current Project Structure

As of now, we have TWO `.pci` directories:

### 1. Test Project (from testing)
```
/home/dxta/dev/portable-code-index/pci/test_project/.pci/
├── config.json (577 bytes)
├── index.mv2 (71 KB)
└── cache/
```

### 2. PCI Source Directory (just created)
```
/home/dxta/dev/portable-code-index/pci/.pci/
├── config.json (577 bytes)
├── index.mv2 (71 KB)
└── cache/
```

---

## How to Use Storage

### Example 1: Index Your Own Project

```bash
# Navigate to your project
cd /path/to/your/project

# Initialize PCI
python -m pci.cli init

# This creates:
# /path/to/your/project/.pci/
```

### Example 2: Index the PCI Source Code

```bash
# Navigate to PCI source
cd /home/dxta/dev/portable-code-index/pci

# Initialize (already done)
python -m pci.cli init

# Future: Index the code (when parser is ready)
python -m pci.cli index

# Search
python -m pci.cli search "storage backend"
```

### Example 3: Multiple Projects

You can have PCI in multiple projects:

```bash
# Project A
cd ~/projects/webapp
pci init
# Creates ~/projects/webapp/.pci/

# Project B  
cd ~/projects/api
pci init
# Creates ~/projects/api/.pci/

# Each has its own independent index!
```

---

## File Locations (Current State)

### Where to Find Your .mv2 Files

```bash
# List all .mv2 files
find /home/dxta/dev/portable-code-index -name "*.mv2"

# Output:
# ./pci/test_project/.pci/index.mv2
# ./pci/.pci/index.mv2
```

### Check File Sizes

```bash
ls -lh /home/dxta/dev/portable-code-index/pci/.pci/index.mv2
# -rw-rw-r-- 1 dxta dxta 71K Jan 11 11:31 index.mv2
```

### Inspect Contents (via CLI)

```bash
cd /home/dxta/dev/portable-code-index/pci
python -m pci.cli status

# Output:
# ┏━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
# ┃ Property   ┃ Value          ┃
# ┡━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
# │ Index Path │ .pci/index.mv2 │
# │ Exists     │ Yes            │
# └────────────┴────────────────┘
```

---

## Storage Details

### What's in the .mv2 File?

The `index.mv2` file contains:

1. **Header** (4KB)
   - Magic number
   - Version info
   - Capacity settings

2. **WAL (Write-Ahead Log)** (1-64MB)
   - Crash recovery data
   - Embedded in the file

3. **Data Segments**
   - Compressed code chunks
   - Metadata

4. **Indexes**
   - Lexical index (BM25/Tantivy)
   - Vector index (HNSW for semantic search)
   - Time index (chronological)

5. **TOC (Table of Contents)**
   - Segment offsets
   - Fast lookups

### File Format Advantages

✅ **Single file** - Easy to backup/move  
✅ **No sidecar files** - Everything embedded  
✅ **Git-friendly** - Can commit if small  
✅ **Crash-safe** - Built-in WAL  
✅ **Fast** - Optimized indexes  

---

## Storage Commands

### Initialize Storage

```bash
pci init
# Creates .pci/index.mv2
```

### Check Storage Status

```bash
pci status
# Shows: path, exists, size (future)
```

### View Configuration

```bash
pci config --show
# Shows where storage is configured
```

### Clear Storage (Manual)

```bash
# Remove the entire .pci directory
rm -rf .pci/

# Or just the index
rm .pci/index.mv2

# Then re-initialize
pci init
```

---

## Advanced: Direct File Access

### Using Python

```python
from pathlib import Path
from pci.storage.backend import MemvidBackend

# Open existing index
backend = MemvidBackend(Path(".pci/index.mv2"))
backend.open_index()

# Store something manually
backend.mem.put(
    title="test",
    label="function",
    text="def test(): pass",
    metadata={"file": "test.py"}
)

# Search
results = backend.search_lexical("test", k=5)
print(f"Found {len(results)} results")
```

### Using Memvid CLI Directly

```bash
# Install memvid-cli
npm install -g memvid-cli

# Query the index
memvid find .pci/index.mv2 --query "search" --mode lex

# Get statistics
memvid stats .pci/index.mv2
```

---

## Storage Best Practices

### 1. Add .pci to .gitignore

```bash
echo ".pci/" >> .gitignore
```

**Why:** Index files can get large and are project-specific.

### 2. Backup Your Index

```bash
# Backup
cp .pci/index.mv2 .pci/index.mv2.backup

# Restore
cp .pci/index.mv2.backup .pci/index.mv2
```

### 3. Share Indexes (Optional)

If you want to share a pre-built index:

```bash
# Package
tar -czf my-project-index.tar.gz .pci/

# Send to colleague
scp my-project-index.tar.gz user@host:/path/

# Extract
tar -xzf my-project-index.tar.gz
```

---

## Troubleshooting

### "PCI not initialized"

**Problem:** Ran `pci search` but `.pci/` doesn't exist  
**Solution:** Run `pci init` first

### "Cannot find .pci directory"

**Problem:** Wrong directory  
**Solution:** `cd` to your project root where you ran `pci init`

### "Index file corrupted"

**Problem:** Memvid file damaged  
**Solution:** Delete and re-initialize:
```bash
rm -rf .pci/
pci init
pci index  # Re-index (when available)
```

### "File is too large"

**Problem:** `.mv2` file growing too big  
**Solution:** 
- Check exclusion patterns in config.json
- Memvid free tier: 50MB limit
- Use `--vector-compression` (future feature)

---

## FAQ

**Q: Can I use PCI on multiple projects?**  
A: Yes! Each project gets its own `.pci/` directory.

**Q: Is the index portable?**  
A: Yes! Copy the `.pci/` directory anywhere.

**Q: Does it work offline?**  
A: Yes! (Except semantic search needs API on this platform)

**Q: Can I inspect the .mv2 file?**  
A: Use `memvid-cli` or the Python SDK. It's a binary format.

**Q: How big will the index get?**  
A: Roughly 10-20% of your codebase size (with compression).

**Q: Can I commit .pci to Git?**  
A: Not recommended. Add to `.gitignore`.

---

## Summary

**Storage location:** `.pci/index.mv2` in your project directory  
**File format:** Memvid v2 (single-file, portable)  
**Current state:** Empty (71 KB base size)  
**Next step:** Implement parser to populate with code chunks

**Check your storage:**
```bash
cd /home/dxta/dev/portable-code-index/pci
ls -lah .pci/
python -m pci.cli status
```
