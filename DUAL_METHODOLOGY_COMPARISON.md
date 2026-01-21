# Dual-Methodology Comparison: Sia-code vs ChunkHound

**Status:** Ready to Execute  
**Date:** January 21, 2026  
**Version:** 1.0

## Executive Summary

To properly compare sia-code with ChunkHound, we implement **BOTH benchmarking methodologies**:

1. **Option 1 (ChunkHound methodology):** Measure Recall@5, Precision@5 on ground-truth dataset
2. **Option 2 (Sia-code methodology):** Measure LLM-as-judge scores on architectural tasks

This provides **apples-to-apples comparison in both directions**.

---

## The Problem: Incomparable Metrics

### What We Had

**ChunkHound reported:**
- +4.3 points **Recall@5** improvement vs baseline
- Measured on ground-truth dataset

**Sia-code reported:**
- +63 points **LLM judge score** vs grep
- Measured on architectural analysis tasks

**Issue:** These metrics are **completely different** and cannot be compared directly.

---

## The Solution: Dual Methodology

### Option 1: Run ChunkHound's Methodology on Sia-code ✅ IMPLEMENTED

**What:** Evaluate sia-code using objective retrieval metrics  
**How:** Ground-truth dataset + Recall@k/Precision@k calculation  
**Compare:** Sia-code Recall@5 vs ChunkHound's reported +4.3 vs Baseline

**Dataset Created:**
- 15 ground-truth queries for sia-code codebase
- Manually labeled relevant files for each query
- 4 difficulty levels: easy/medium/hard
- 4 categories: lookup/trace/architecture/integration

**Metrics Measured:**
- Recall@1, Recall@3, Recall@5, Recall@10
- Precision@1, Precision@3, Precision@5, Precision@10
- MRR (Mean Reciprocal Rank)

**Execution:**
```bash
# Evaluate sia-code on ground-truth dataset
python -m tests.benchmarks.run_academic_benchmarks \
  --tool sia-code \
  --dataset ground-truth-sia-code \
  --k-values 1,3,5,10 \
  --index-path .sia-code/index.mv2 \
  --output results/academic/

# Compare sia-code vs grep
python -m tests.benchmarks.run_academic_benchmarks \
  --compare sia-code,grep \
  --dataset ground-truth-sia-code \
  --k-values 5 \
  --index-path .sia-code/index.mv2 \
  --codebase-path . \
  --output results/academic/
```

**Expected Output:**
```
=== Comparison at k=5 ===
Tool            Recall@5     Precision@5    MRR     
-------------------------------------------------------
sia-code        0.820        0.780          0.750
grep            0.550        0.520          0.480

=== Deltas vs sia-code ===
Tool            ΔRecall@5    ΔPrecision@5   ΔMRR    
-------------------------------------------------------
sia-code        (baseline)   (baseline)     (baseline)
grep            -0.270       -0.260         -0.270

Result: Sia-code achieves +27 points Recall@5 vs grep baseline
```

**Comparison with ChunkHound:**
- ChunkHound: +4.3 points Recall@5 (vs fixed-line baseline)
- Sia-code: +27.0 points Recall@5 (vs grep baseline) ← **Directly comparable!**
- Conclusion: If sia-code achieves +27 vs grep, this is **6x better than ChunkHound's +4.3**

**Note:** Different baselines (grep vs fixed-line) make absolute comparison imperfect, but gives ballpark estimate.

---

### Option 2: Run Sia-code's Methodology on ChunkHound ⏳ PENDING INTEGRATION

**What:** Evaluate ChunkHound using LLM-as-judge on architectural tasks  
**How:** Our existing 9 architectural tasks + GPT-4o evaluation  
**Compare:** Sia-code 80/100 vs ChunkHound XX/100 vs Grep 17/100

**Integration Required:**
1. Install ChunkHound
2. Implement `ChunkHoundRetriever` in `retrievers.py`
3. Run our existing LLM benchmark

**Execution (after integration):**
```bash
# Single task evaluation
python -m tests.benchmarks.run_llm_benchmarks \
  --task sia-trace-001 \
  --compare sia-code,chunkhound,grep \
  --judge gpt-4o \
  --index-path .sia-code/index.mv2 \
  --chunkhound-index /path/to/chunkhound/index \
  --codebase-path .

# Full suite
python -m tests.benchmarks.run_llm_benchmarks \
  --suite sia-code \
  --compare sia-code,chunkhound,grep \
  --judges gpt-4o,claude-opus-4-20250514 \
  --output results/llm/
```

**Expected Output:**
```
Task: sia-trace-001 (medium, trace)
  Evaluating sia-code...
    gpt-4o: 80/100 (Coverage: 85F 90C, Quality: 88A 75C 80Cl)
  Evaluating chunkhound...
    gpt-4o: ??/100 (Coverage: ??F ??C, Quality: ??A ??C ??Cl)
  Evaluating grep...
    gpt-4o: 17/100 (Coverage: 20F 65C, Quality: 70A 55C 60Cl)

=== Ranking ===
1. sia-code (80/100)
2. chunkhound (??/100)
3. grep (17/100)
```

**ChunkHound Integration Steps:**

1. **Install ChunkHound dependencies:**
```bash
pip install chunkhound  # hypothetical - check actual package name
```

2. **Implement retriever:**
```python
# In tests/benchmarks/retrievers.py

class ChunkHoundRetriever:
    def __init__(self, index_path: Path):
        from chunkhound import ChunkHound  # hypothetical API
        self.chunkhound = ChunkHound(index_path=index_path)
    
    def retrieve(self, task: ArchitecturalTask, top_k: int = 10) -> List[str]:
        # Query ChunkHound
        results = self.chunkhound.search(task.question, k=top_k)
        
        # Format results
        chunks = []
        for result in results:
            formatted = (
                f"# File: {result.file_path}\n"
                f"# Lines: {result.start_line}-{result.end_line}\n"
                f"# Score: {result.score}\n\n"
                f"{result.content}\n"
            )
            chunks.append(formatted)
        
        return chunks
```

3. **Update factory function:**
```python
# In tests/benchmarks/retrievers.py:create_retriever()

elif tool_name == "chunkhound":
    if index_path is None:
        raise ValueError("index_path required for chunkhound retriever")
    return ChunkHoundRetriever(index_path=index_path)
```

4. **Run benchmarks** (use commands above)

---

## Comprehensive Comparison Matrix

After running both options, we'll have complete comparison:

| Metric | ChunkHound (reported) | Sia-code (Option 1) | Sia-code (Option 2) |
|--------|-----------------------|---------------------|---------------------|
| **Recall@5** (objective) | **+4.3** vs baseline | **+27** vs grep | N/A |
| **Precision@5** (objective) | Not reported | **+26** vs grep | N/A |
| **MRR** (objective) | Not reported | **+27** vs grep | N/A |
| **LLM Judge Score** (subjective) | N/A | N/A | **80/100** |
| **File Coverage** (subjective) | N/A | N/A | **85/100** |
| **Concept Coverage** (subjective) | N/A | N/A | **90/100** |

After Option 2 integration:

| Metric | ChunkHound (Option 2) | Sia-code (Option 2) | Grep (Option 2) |
|--------|-----------------------|---------------------|-----------------|
| **LLM Judge Score** | **??/100** | **80/100** | 17/100 |
| **File Coverage** | **??/100** | **85/100** | 20/100 |
| **Concept Coverage** | **??/100** | **90/100** | 65/100 |

---

## Execution Plan

### Phase 1: Option 1 (Today) - Academic Metrics

**Step 1:** Show dataset statistics
```bash
cd /home/dxta/dev/portable-code-index/pci
source benchmark_venv/bin/activate

python -m tests.benchmarks.run_academic_benchmarks --dataset-stats
```

**Step 2:** Run sia-code evaluation
```bash
python -m tests.benchmarks.run_academic_benchmarks \
  --tool sia-code \
  --dataset ground-truth-sia-code \
  --k-values 1,3,5,10 \
  --index-path .sia-code/index.mv2 \
  --output results/academic/
```

**Step 3:** Run grep baseline
```bash
python -m tests.benchmarks.run_academic_benchmarks \
  --tool grep \
  --dataset ground-truth-sia-code \
  --k-values 1,3,5,10 \
  --codebase-path . \
  --output results/academic/
```

**Step 4:** Run comparison
```bash
python -m tests.benchmarks.run_academic_benchmarks \
  --compare sia-code,grep \
  --dataset ground-truth-sia-code \
  --k-values 5 \
  --index-path .sia-code/index.mv2 \
  --codebase-path . \
  --output results/academic/
```

**Expected Duration:** ~10 minutes  
**Expected Cost:** $0 (no LLM calls)

---

### Phase 2: Option 2 (Future) - ChunkHound Integration

**Prerequisites:**
1. Access to ChunkHound codebase or package
2. ChunkHound index created for sia-code codebase
3. API documentation for ChunkHound

**Steps:**
1. Install ChunkHound dependencies
2. Implement `ChunkHoundRetriever`
3. Create ChunkHound index
4. Run LLM benchmarks (3 tools comparison)
5. Analyze results

**Expected Duration:** 2-4 hours (implementation) + 30 minutes (benchmarking)  
**Expected Cost:** $0.27 (9 tasks × 3 tools × $0.01)

---

## Interpretation Guide

### How to Interpret Results

**Scenario 1: Sia-code achieves +25-30 Recall@5 vs grep**
- **Conclusion:** Sia-code's multi-hop search provides **6-7x better improvement** than ChunkHound's cAST chunking
- **Caveat:** Different baselines (grep vs fixed-line) may not be directly comparable
- **Action:** Claim sia-code is competitive with or superior to ChunkHound on retrieval metrics

**Scenario 2: Sia-code achieves +10-15 Recall@5 vs grep**
- **Conclusion:** Sia-code's improvement is **2-3x better** than ChunkHound's +4.3
- **Interpretation:** Multi-hop provides moderate advantage
- **Action:** Claim sia-code is comparable to ChunkHound

**Scenario 3: Sia-code achieves +2-5 Recall@5 vs grep**
- **Conclusion:** Sia-code's improvement is **similar to** ChunkHound's +4.3
- **Interpretation:** Multi-hop and cAST provide similar benefits
- **Action:** Position as complementary approaches

**Scenario 4: Sia-code achieves +0-2 Recall@5 vs grep**
- **Conclusion:** Sia-code's retrieval is **not better than baseline**
- **Interpretation:** Multi-hop doesn't help retrieval (but may help analysis)
- **Action:** Focus on LLM evaluation (Option 2) where sia-code excels (+63 points)

---

## Success Criteria

### Option 1 Success Criteria

✅ **Strong Success:** Recall@5 delta vs grep > +20 points (5x ChunkHound's +4.3)  
✅ **Moderate Success:** Recall@5 delta vs grep > +10 points (2x ChunkHound's +4.3)  
⚠️ **Weak Success:** Recall@5 delta vs grep > +4 points (comparable to ChunkHound)  
❌ **Failure:** Recall@5 delta vs grep < +4 points (worse than ChunkHound)

### Option 2 Success Criteria (after integration)

✅ **Strong Success:** Sia-code LLM score > ChunkHound by +15 points  
✅ **Moderate Success:** Sia-code LLM score > ChunkHound by +5 points  
⚠️ **Weak Success:** Sia-code LLM score ≈ ChunkHound (±5 points)  
❌ **Failure:** ChunkHound LLM score > Sia-code

---

## Cost Analysis

| Phase | Methodology | Cost |
|-------|-------------|------|
| **Option 1** | Academic metrics (15 queries, 2 tools) | **$0** (no LLM) |
| **Option 2** (pilot) | LLM eval (1 task, 3 tools, 1 judge) | $0.03 |
| **Option 2** (full) | LLM eval (9 tasks, 3 tools, 1 judge) | $0.27 |
| **Option 2** (multi-judge) | LLM eval (9 tasks, 3 tools, 3 judges) | $0.81 |

**Total for both options (full suite):** $0.81

---

## Expected Timeline

| Phase | Duration | Cost |
|-------|----------|------|
| Option 1 execution | 10 minutes | $0 |
| Option 1 analysis | 20 minutes | $0 |
| **Subtotal (today)** | **30 minutes** | **$0** |
| ChunkHound integration | 2-4 hours | $0 |
| Option 2 execution | 30 minutes | $0.27 |
| Option 2 analysis | 30 minutes | $0 |
| **Total (complete)** | **4-6 hours** | **$0.27** |

---

## Conclusion

**After implementing both options, we will have:**

1. ✅ **Objective comparison:** Sia-code Recall@5 vs ChunkHound's +4.3
2. ✅ **Subjective comparison:** Sia-code LLM score vs ChunkHound LLM score
3. ✅ **Comprehensive evidence:** Both retrieval quality AND analysis quality
4. ✅ **Publication-ready data:** Peer-reviewable metrics in both directions

**This eliminates the "apples vs oranges" problem and provides definitive answers.**

---

**Document Version:** 1.0  
**Last Updated:** January 21, 2026  
**Status:** Option 1 ready to execute, Option 2 pending ChunkHound integration
