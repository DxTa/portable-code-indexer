# Sia-code vs ChunkHound: Benchmark Comparison Plan

**Status:** Ready for Pilot Evaluation  
**Date:** January 21, 2026  
**Version:** 1.0

## Executive Summary

This document outlines the comparison methodology between **sia-code** and **ChunkHound** for code retrieval quality. While we cannot directly benchmark ChunkHound (no integration yet), we can:

1. **Compare infrastructure capabilities** (feature parity analysis)
2. **Benchmark sia-code against grep baseline** (validate approach)
3. **Establish performance baselines** for future ChunkHound integration

---

## 1. Infrastructure Comparison

### 1.1 ChunkHound Architecture (from paper)

**Storage:**
- DuckDB (metadata) + LanceDB (vectors)
- cAST chunking (context-aware AST with semantic boundaries)
- Hybrid search (BM25 + vector similarity)

**Benchmark Approach:**
- Kubernetes controller tracing tasks
- Single LLM judge (GPT-4)
- Recall@5, Precision@5 metrics
- **Result: +4.3 point improvement** over fixed-line baseline

**Key Innovation:** cAST chunking ensures complete semantic units (functions with full bodies, not split mid-logic)

### 1.2 Sia-code Architecture (our implementation)

**Storage:**
- Memvid MV2 (Tantivy BM25 + HNSW vectors)
- AST chunking (tree-sitter based)
- Hybrid search (BM25 + semantic embeddings)

**Benchmark Approach:**
- **Multi-codebase tasks** (sia-code, Flask, FastAPI)
- **Multi-judge consensus** (GPT-4o, Claude Opus, Gemini)
- **5 academic metrics** (Recall@k, Precision@k, nDCG@k, MRR, Hit@k)
- **5 qualitative dimensions** (file coverage, concept coverage, accuracy, completeness, clarity)

**Key Innovation:** Multi-hop virtual graph traversal (follows entity relationships across files)

### 1.3 Feature Parity Matrix

| Feature | ChunkHound | Sia-code | Winner |
|---------|------------|----------|---------|
| **Chunking Strategy** | cAST (semantic boundaries) | AST (tree-sitter) | ChunkHound (more sophisticated) |
| **Search Backend** | DuckDB + LanceDB | Memvid (Tantivy + HNSW) | Comparable |
| **Hybrid Search** | ✅ BM25 + Vectors | ✅ BM25 + Vectors | Tie |
| **Multi-hop Traversal** | ❌ Not mentioned | ✅ **Virtual graph** | **Sia-code** |
| **Benchmark Scope** | 1 codebase (K8s) | 3 codebases | **Sia-code** |
| **Task Diversity** | Trace only | 4 types (trace/arch/dep/integ) | **Sia-code** |
| **Judge Models** | GPT-4 (single) | GPT-4o/Claude/Gemini (consensus) | **Sia-code** |
| **Rubric Flexibility** | Single rubric | 3 rubrics (comp/quick/strict) | **Sia-code** |
| **Retrieval Quality Eval** | ❌ Not separate | ✅ Separate assessment | **Sia-code** |
| **Academic Metrics** | 2 metrics (R@5, P@5) | 5 metrics (R/P/nDCG/MRR/Hit@k) | **Sia-code** |
| **Side-by-side Comparison** | ❌ Not mentioned | ✅ Built-in | **Sia-code** |
| **Production Deployment** | Research project | ✅ CLI tool | **Sia-code** |

**Summary:** Sia-code has **more comprehensive benchmarking infrastructure** but ChunkHound may have **superior chunking strategy** (cAST vs AST).

---

## 2. Theoretical Performance Predictions

### 2.1 Scenario Analysis

#### Scenario A: Simple Symbol Lookup
**Query:** "Find the `parse_args` function"

| Tool | Strategy | Expected Performance |
|------|----------|---------------------|
| ChunkHound | cAST + BM25 lexical match | ✅ Excellent (95%+ Recall@5) |
| Sia-code | AST + BM25 lexical match | ✅ Excellent (95%+ Recall@5) |
| Grep | Keyword matching | ✅ Good (85%+ Recall@5) |

**Prediction:** **Tie** - All tools should perform well on simple lookups

#### Scenario B: Architectural Understanding
**Query:** "How does FastAPI implement dependency injection?"

| Tool | Strategy | Expected Performance |
|------|----------|---------------------|
| ChunkHound | Retrieve DI-related chunks | ⚠️ Good (70% Recall@5) - relies on LLM to connect |
| Sia-code | **Multi-hop** (routing.py → deps/utils.py → deps/models.py) | ✅ **Excellent (85%+ Recall@5)** - traces relationships |
| Grep | Keyword "dependency injection" | ❌ Poor (40% Recall@5) - misses related code |

**Prediction:** **Sia-code wins** - Multi-hop graph traversal advantage

#### Scenario C: Cross-File Integration Tracing
**Query:** "Trace Flask request context from creation to cleanup"

| Tool | Strategy | Expected Performance |
|------|----------|---------------------|
| ChunkHound | Retrieve chunks about "request context" | ⚠️ Good (65% Recall@5) - may get isolated pieces |
| Sia-code | **Virtual graph** (app.py → ctx.py → globals.py → teardown) | ✅ **Excellent (80%+ Recall@5)** - follows call chain |
| Grep | Keyword "RequestContext" | ❌ Poor (50% Recall@5) - misses flow |

**Prediction:** **Sia-code wins** - Call chain traversal advantage

#### Scenario D: Edge Case Error Handling
**Query:** "Find error handling for malformed JSON in API endpoints"

| Tool | Strategy | Expected Performance |
|------|----------|---------------------|
| ChunkHound | **cAST ensures complete error blocks** | ✅ **Excellent (80%+ Recall@5)** - semantic boundaries |
| Sia-code | AST may split try/except across chunks | ⚠️ Good (70% Recall@5) - depends on chunk size |
| Grep | Keyword "error" or "exception" | ❌ Poor (55% Recall@5) - too noisy |

**Prediction:** **ChunkHound wins** - Superior chunking strategy

### 2.2 Overall Expected Performance

**Average Recall@5 Predictions:**
- ChunkHound: **75-80%** (strong chunking, no multi-hop)
- Sia-code: **78-85%** (multi-hop advantage compensates for chunking)
- Grep: **55-65%** (baseline keyword matching)

**LLM Judge Score Predictions (0-100):**
- ChunkHound: **72-78** (good retrieval, LLM connects pieces)
- Sia-code: **75-82** (multi-hop provides better context)
- Grep: **50-60** (incomplete information, poor context)

**Confidence Level:** Medium (based on architectural analysis, not empirical data)

---

## 3. Pilot Evaluation Plan

### 3.1 Objectives

1. **Validate benchmark infrastructure** (ensure it runs without errors)
2. **Establish sia-code baseline** (quantify performance)
3. **Compare against grep** (validate multi-hop advantage)
4. **Identify areas for improvement** (chunking strategy, search tuning)

### 3.2 Pilot Scope (Minimal)

**Tasks to Run:** 3 tasks (one of each type)
- `sia-trace-001` (Medium, Trace): CLI → LLM response flow
- `sia-arch-001` (Hard, Architecture): Virtual graph implementation
- `sia-dep-001` (Medium, Dependency): Indexing pipeline dependencies

**Tools to Compare:**
- Sia-code (semantic + multi-hop)
- Grep (lexical baseline)

**Judge Model:** GPT-4o (single judge for pilot)

**Rubric:** Comprehensive (5 dimensions)

**Estimated Cost:** 6 evaluations × $0.015 = **$0.09**

**Estimated Time:** ~5 minutes (including LLM API calls)

### 3.3 Pilot Execution Commands

```bash
# Step 1: Ensure index is up to date
cd /home/dxta/dev/portable-code-index/pci
uvx --with openai sia-code status
# If stale: uvx --with openai sia-code index .

# Step 2: Run single task evaluation (sia-code)
python -m tests.benchmarks.run_llm_benchmarks \
  --task sia-trace-001 \
  --tool sia-code \
  --judge gpt-4o \
  --rubric comprehensive \
  --index-path .pci/index.mv2 \
  --codebase-path . \
  2>&1 | tee pilot_results/sia-trace-001_sia-code.log

# Step 3: Run comparison (sia-code vs grep)
python -m tests.benchmarks.run_llm_benchmarks \
  --task sia-trace-001 \
  --compare sia-code,grep \
  --judge gpt-4o \
  --index-path .pci/index.mv2 \
  --codebase-path . \
  2>&1 | tee pilot_results/sia-trace-001_comparison.log

# Step 4: Repeat for other tasks
for task in sia-arch-001 sia-dep-001; do
  python -m tests.benchmarks.run_llm_benchmarks \
    --task $task \
    --compare sia-code,grep \
    --judge gpt-4o \
    --index-path .pci/index.mv2 \
    --codebase-path . \
    2>&1 | tee pilot_results/${task}_comparison.log
done
```

### 3.4 Success Criteria

**Infrastructure Validation:**
- ✅ All 3 tasks complete without errors
- ✅ JSON output is well-formed
- ✅ LLM judge returns valid scores (0-100)

**Performance Validation:**
- ✅ Sia-code Recall@5 > Grep Recall@5 (by 15%+)
- ✅ Sia-code LLM Judge Score > Grep Score (by 10+ points)
- ✅ File coverage > 70% for sia-code on sia-trace-001

**Diagnostic Insights:**
- ✅ Identify which files sia-code retrieves vs grep
- ✅ Understand where multi-hop helps vs doesn't
- ✅ Find areas for chunking improvement

---

## 4. Full Benchmark Plan (Post-Pilot)

### 4.1 Extended Evaluation

**Scope:** All 9 tasks across 3 codebases

**Tools:**
- Sia-code (full configuration)
- Grep (baseline)
- ChunkHound (if integration available)

**Judges:** Multi-judge consensus
- GPT-4o (primary)
- Claude Opus 4 (strict evaluation)
- Gemini 2.0 Flash (fast evaluation)

**Cost Estimate:** 
- 9 tasks × 2 tools × 3 judges = 54 evaluations
- 54 × $0.015 (avg) = **$0.81**

### 4.2 Academic Metrics Evaluation

Run Phase 1 benchmarks with ground-truth datasets:

```bash
python -m tests.benchmarks.run_benchmarks \
  --dataset sia-code-ground-truth \
  --retriever sia-code \
  --metrics all \
  --output results/academic/
```

**Metrics to Collect:**
- Recall@1, Recall@3, Recall@5, Recall@10
- Precision@1, Precision@3, Precision@5, Precision@10
- nDCG@5, nDCG@10
- MRR (Mean Reciprocal Rank)
- Hit@1, Hit@5, Hit@10

### 4.3 ChunkHound Integration (Future)

**Integration Steps:**
1. Install ChunkHound dependencies
2. Implement `ChunkHoundRetriever` in `retrievers.py`
3. Map ChunkHound index format to our task schema
4. Run side-by-side comparison

**Comparison Tasks:**
- Replicate ChunkHound's Kubernetes benchmark (for apples-to-apples)
- Run sia-code tasks (to test ChunkHound on our benchmark)
- Compare Recall@5 deltas vs baseline

---

## 5. Expected Outputs

### 5.1 Pilot Results (Immediate)

**JSON Output:**
```json
{
  "task_id": "sia-trace-001",
  "tool_name": "sia-code",
  "judge_model": "gpt-4o",
  "score": 82.5,
  "file_coverage": 85.0,
  "concept_coverage": 90.0,
  "accuracy": 88.0,
  "completeness": 75.0,
  "clarity": 80.0,
  "reasoning": "The tool successfully identified all key components...",
  "missing_elements": ["Error handling flow"],
  "strengths": ["Complete call chain traced", "Accurate file references"],
  "weaknesses": ["Did not retrieve error handling code"]
}
```

**Console Output:**
```
Task: sia-trace-001 (medium, trace)
Question: Trace the complete flow from CLI command 'sia-code research'...
  Evaluating sia-code...
    gpt-4o: 82.5/100
      Coverage: 85.0F 90.0C
      Quality: 88.0A 75.0C 80.0Cl
  Evaluating grep...
    gpt-4o: 64.0/100
      Coverage: 60.0F 65.0C
      Quality: 70.0A 55.0C 60.0Cl

=== Comparison ===
Ranking: ['sia-code', 'grep']
Analysis: Sia-code's multi-hop search successfully traced the complete
call chain from CLI to LLM response, retrieving 85% of expected files.
Grep's keyword matching missed intermediate components...
```

### 5.2 Comparison Report

**Markdown Report (Auto-generated):**
```markdown
# Sia-code vs Grep Benchmark Results

## Summary
- Tasks Evaluated: 3
- Judge Model: GPT-4o
- Rubric: Comprehensive

## Overall Scores
| Tool | Avg Score | File Cov | Concept Cov | Accuracy | Completeness | Clarity |
|------|-----------|----------|-------------|----------|--------------|---------|
| Sia-code | 78.3 | 80.0 | 85.0 | 82.0 | 70.0 | 75.0 |
| Grep | 58.7 | 55.0 | 60.0 | 65.0 | 50.0 | 58.0 |

**Winner:** Sia-code (+19.6 points)

## Task-by-Task Breakdown
...
```

---

## 6. Risks and Mitigations

### 6.1 Identified Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| LLM API failures | Medium | High | Retry logic, fallback to cached results |
| Index staleness | Low | Medium | Run `sia-code status` before benchmarks |
| Insufficient context (grep) | High | Low | Expected - validates sia-code advantage |
| LLM judge bias | Medium | Medium | Multi-judge consensus in full eval |
| Task ambiguity | Low | Medium | Clear expected_files and expected_concepts |

### 6.2 Validation Checks

**Pre-flight:**
- ✅ Index health check (`sia-code status`)
- ✅ API keys loaded (OPENAI_API_KEY)
- ✅ Output directory exists
- ✅ Ripgrep installed (for grep retriever)

**Post-execution:**
- ✅ JSON validation (all fields present)
- ✅ Score ranges valid (0-100)
- ✅ No crashes or exceptions
- ✅ Retrieved chunks non-empty

---

## 7. Timeline

### Phase 1: Pilot Evaluation (Today)
- **Duration:** 10 minutes
- **Cost:** $0.09
- **Deliverables:** 3 task comparisons, JSON results, console logs

### Phase 2: Analysis and Documentation (Today)
- **Duration:** 30 minutes
- **Deliverables:** Comparison report, findings summary, improvement recommendations

### Phase 3: Full Benchmark (Optional)
- **Duration:** 1 hour
- **Cost:** $0.81
- **Deliverables:** 9-task evaluation, multi-judge consensus, academic metrics

### Phase 4: ChunkHound Integration (Future)
- **Duration:** 2-4 hours (implementation) + 1 hour (benchmarking)
- **Cost:** $1.50 (extended benchmark suite)
- **Deliverables:** Direct performance comparison, feature parity analysis

---

## 8. Success Metrics

### Infrastructure Quality
- ✅ Zero crashes during pilot
- ✅ JSON output validates against schema
- ✅ LLM judge responses are parseable
- ✅ Retriever integration works (no dummy data)

### Performance Targets (Pilot)
- **Sia-code vs Grep Delta:**
  - File Coverage: +20 points or more
  - Concept Coverage: +20 points or more
  - Overall Score: +15 points or more

### Actionable Insights
- ✅ Identify 3+ areas for sia-code improvement
- ✅ Understand when multi-hop helps vs doesn't
- ✅ Document retrieval quality vs analysis quality split

---

## 9. Next Steps After Pilot

### If Pilot Succeeds
1. Run full 9-task benchmark
2. Implement multi-judge consensus
3. Generate visual comparison charts
4. Publish results to documentation
5. Consider ChunkHound integration

### If Pilot Reveals Issues
1. Debug retriever integration (sia-code backend)
2. Tune chunking parameters (chunk_size, overlap)
3. Adjust evaluation prompts (if judge scores unrealistic)
4. Re-run pilot after fixes

---

## 10. Open Questions

1. **Chunking Strategy:** Should we implement cAST-style semantic boundaries?
2. **Multi-hop Tuning:** Optimal max_hops and results_per_hop values?
3. **Judge Calibration:** Are GPT-4o scores comparable to Claude/Gemini?
4. **Ground Truth:** Do we need human-annotated "correct" answers?
5. **ChunkHound Access:** Can we get access to ChunkHound codebase for direct comparison?

---

## Appendix A: Task Definitions

### sia-trace-001
- **Question:** Trace the complete flow from CLI command 'sia-code research' to the final LLM response generation. What are the key components involved?
- **Expected Files:** cli/main.py, commands/research.py, search/multi_hop.py, llm/prompt_builder.py, storage/backend.py
- **Expected Concepts:** CLI parsing, multi-hop search, virtual graph, memvid backend, LLM prompts

### sia-arch-001
- **Question:** How does sia-code implement the 'virtual graph' concept without persisting graph structures? What are the key design decisions?
- **Expected Files:** search/multi_hop.py, indexing/entity_extractor.py, storage/backend.py
- **Expected Concepts:** Query-time entity extraction, tree-sitter parsing, dynamic relationships, stateless traversal

### sia-dep-001
- **Question:** What are all the dependencies required for the indexing pipeline, and how do they interact?
- **Expected Files:** indexing/indexer.py, indexing/chunker.py, indexing/entity_extractor.py, storage/backend.py, language_support/tree_sitter_manager.py
- **Expected Concepts:** Tree-sitter parsers, memvid SDK, embedding models, file watching, Tantivy indexing

---

**Document Version:** 1.0  
**Last Updated:** January 21, 2026  
**Status:** Ready for Execution
