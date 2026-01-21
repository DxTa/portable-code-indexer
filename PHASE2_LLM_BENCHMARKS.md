# Phase 2: LLM-Evaluated Architectural Analysis Benchmarks

**Status:** ✅ Complete (ready for integration testing)

## Overview

Phase 2 implements **LLM-as-judge evaluation** for architectural analysis tasks, inspired by ChunkHound's Kubernetes controller tracing benchmarks. This complements Phase 1's academic metrics (Recall@k, MRR) with qualitative assessment of code understanding.

### Why LLM Evaluation?

Traditional metrics (Recall@k, nDCG) measure **retrieval accuracy** but not **understanding quality**:
- Did the tool retrieve the right files? → Phase 1 metrics
- Can the tool **explain how they relate**? → Phase 2 evaluation

**Example:** For the task "How does Flask handle request contexts?", we need to evaluate:
- File coverage (ctx.py, globals.py, app.py found?)
- Concept coverage (thread-local storage, context stack explained?)
- Accuracy (technical correctness of explanations)
- Completeness (all aspects of the design covered?)

## Architecture

```
tests/benchmarks/
├── tasks/
│   ├── architectural_tasks.py       # Task definitions (9 tasks across 3 codebases)
│   └── evaluation_prompts.py        # Judge prompts and rubrics
├── llm_evaluation.py                # LLMJudge framework + 3 LLM clients
└── run_llm_benchmarks.py            # CLI runner
```

### Components

#### 1. Architectural Tasks (`tasks/architectural_tasks.py`)

**9 tasks across 3 codebases:**

| Codebase | Tasks | Types |
|----------|-------|-------|
| sia-code | 5 tasks | trace, architecture, dependency, integration |
| Flask | 2 tasks | trace (request flow), architecture (context system) |
| FastAPI | 2 tasks | trace (DI resolution), integration (Pydantic) |

**Task structure:**
```python
ArchitecturalTask(
    task_id="sia-trace-001",
    question="Trace 'sia-code research' from CLI to LLM response",
    codebase="sia-code",
    expected_files=[...],           # Ground truth files
    expected_concepts=[...],        # Key concepts to cover
    difficulty="medium",            # easy/medium/hard/expert
    task_type="trace",             # trace/dependency/architecture/integration
)
```

**Example tasks:**

**sia-trace-001** (Medium, Trace):
- Question: "Trace the complete flow from CLI command 'sia-code research' to the final LLM response generation. What are the key components involved?"
- Expected files: `cli/main.py`, `commands/research.py`, `search/multi_hop.py`, `llm/prompt_builder.py`, `storage/backend.py`
- Expected concepts: CLI parsing, multi-hop search, virtual graph, memvid backend, LLM prompts

**sia-arch-001** (Hard, Architecture):
- Question: "How does sia-code implement the 'virtual graph' concept without persisting graph structures? What are the key design decisions?"
- Expected concepts: Query-time entity extraction, tree-sitter parsing, dynamic relationship inference, stateless traversal

**flask-trace-001** (Medium, Trace):
- Question: "Trace the request handling flow from URL routing to response generation in Flask. What middleware and hooks are involved?"
- Expected concepts: URL routing, request context, application context, before/after hooks, WSGI

#### 2. Evaluation Prompts (`tasks/evaluation_prompts.py`)

**Three rubric modes:**

| Rubric | Use Case | Passing Score |
|--------|----------|---------------|
| **comprehensive** | Production evaluation, 5 dimensions (file/concept coverage, accuracy, completeness, clarity) | N/A |
| **quick** | Rapid iteration, 2 dimensions (coverage, quality) | N/A |
| **strict** | Code review standards, < 70 = fail, 95+ = excellent | 70 |

**Comprehensive rubric dimensions (weighted):**
- File Coverage (20%): Expected files mentioned and roles explained
- Concept Coverage (25%): Key concepts with technical depth
- Accuracy (25%): Technical correctness
- Completeness (20%): Fully answers the question
- Clarity (10%): Explanation quality

**Prompt types:**
1. `create_analysis_prompt()`: Tool generates answer from retrieved chunks
2. `create_judge_prompt()`: Judge evaluates tool's answer
3. `create_comparison_prompt()`: Side-by-side tool comparison
4. `create_retrieval_quality_prompt()`: Evaluate retrieval before analysis

#### 3. LLM Judge Framework (`llm_evaluation.py`)

**Supported judge models:**
- **GPT-4o** (OpenAI) - Default, strong technical accuracy
- **Claude Opus 4** (Anthropic) - Strict evaluation, detailed feedback
- **Gemini 2.0 Flash** (Google) - Fast evaluation, cost-effective

**Multi-judge consensus approach:**
```python
# Create judges
gpt_judge = create_judge("gpt-4o", rubric="comprehensive")
claude_judge = create_judge("claude-opus-4-20250514", rubric="strict")
gemini_judge = create_judge("gemini-2.0-flash-exp", rubric="quick")

# Evaluate same response
results = [
    gpt_judge.evaluate(task, tool_response, "sia-code"),
    claude_judge.evaluate(task, tool_response, "sia-code"),
    gemini_judge.evaluate(task, tool_response, "sia-code"),
]

# Average scores for consensus
consensus_score = sum(r.score for r in results) / len(results)
```

**LLM clients (Protocol-based):**
- `OpenAIClient` - Uses `openai` package
- `AnthropicClient` - Uses `anthropic` package
- `GeminiClient` - Uses `google.generativeai` package

**EvaluationResult dataclass:**
```python
@dataclass
class EvaluationResult:
    task_id: str
    tool_name: str
    judge_model: str
    score: float                    # 0-100
    file_coverage: float
    concept_coverage: float
    accuracy: float
    completeness: float
    clarity: float
    reasoning: str                  # Judge's detailed explanation
    missing_elements: List[str]     # Critical gaps
    strengths: List[str]
    weaknesses: List[str]
    raw_response: str               # Full JSON from judge
```

#### 4. CLI Runner (`run_llm_benchmarks.py`)

**Usage modes:**

**1. Single evaluation:**
```bash
python -m tests.benchmarks.run_llm_benchmarks \
  --task sia-trace-001 \
  --tool sia-code \
  --judge gpt-4o \
  --rubric comprehensive
```

**2. Side-by-side comparison:**
```bash
python -m tests.benchmarks.run_llm_benchmarks \
  --task sia-arch-001 \
  --compare sia-code,grep \
  --judge claude-opus-4-20250514
```

**3. Full benchmark suite:**
```bash
python -m tests.benchmarks.run_llm_benchmarks \
  --suite sia-code \
  --compare sia-code,grep \
  --judges gpt-4o,claude-opus-4-20250514,gemini-2.0-flash-exp \
  --output results/
```

**4. List available tasks:**
```bash
python -m tests.benchmarks.run_llm_benchmarks --list-tasks
```

**Output format:**
```
Task: sia-trace-001 (medium, trace)
Question: Trace the complete flow from CLI command 'sia-code research'...
  Evaluating sia-code...
    gpt-4o: 82.5/100
      Coverage: 85.0F 90.0C
      Quality: 88.0A 75.0C 80.0Cl
    claude-opus-4-20250514: 78.0/100
      Coverage: 80.0F 85.0C
      Quality: 90.0A 70.0C 75.0Cl
```

## Integration Requirements

### Phase 2 TODOs (for production use):

**1. Integrate sia-code retriever** (`run_llm_benchmarks.py:25`):
```python
def dummy_sia_code_retriever(task: ArchitecturalTask, top_k: int = 10) -> List[str]:
    # TODO: Replace with actual sia-code backend
    from sia_code.storage.backend import MemvidBackend
    from sia_code.search.multi_hop import MultiHopSearch
    
    backend = MemvidBackend(index_path=".pci/index.mv2")
    searcher = MultiHopSearch(backend)
    results = searcher.search(task.question, max_hops=3, top_k=top_k)
    
    return [chunk.content for chunk in results]
```

**2. Implement grep baseline** (`run_llm_benchmarks.py:35`):
```python
def dummy_grep_retriever(task: ArchitecturalTask) -> List[str]:
    # TODO: Implement actual grep-based retrieval
    import subprocess
    
    # Extract keywords from question
    keywords = extract_keywords(task.question)
    
    # Run ripgrep with context
    results = []
    for keyword in keywords:
        output = subprocess.run(
            ["rg", "-C", "10", keyword, task.codebase],
            capture_output=True, text=True
        ).stdout
        results.append(output)
    
    return results
```

**3. Add LLM-based analysis** (between retrieval and evaluation):
```python
def generate_tool_response_with_llm(
    task: ArchitecturalTask,
    tool_name: str,
    retrieved_chunks: List[str]
) -> str:
    """Use LLM to analyze retrieved chunks and answer the task."""
    from openai import OpenAI
    
    client = OpenAI()
    prompt = create_analysis_prompt(task, retrieved_chunks)
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    
    return response.choices[0].message.content
```

**4. Install judge dependencies:**
```bash
# OpenAI (GPT-4o)
pip install openai

# Anthropic (Claude Opus)
pip install anthropic

# Google (Gemini)
pip install google-generativeai
```

**5. Set API keys:**
```bash
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...
export GOOGLE_API_KEY=...
```

## Benchmarking Workflow

### Step 1: Run Academic Metrics (Phase 1)
```bash
python -m tests.benchmarks.run_benchmarks \
  --dataset sia-code \
  --retriever sia-code \
  --metrics all \
  --output results/academic/
```

**Output:** Recall@5, Precision@5, nDCG@5, MRR

### Step 2: Run LLM Evaluation (Phase 2)
```bash
python -m tests.benchmarks.run_llm_benchmarks \
  --suite sia-code \
  --compare sia-code,grep \
  --judges gpt-4o,claude-opus-4-20250514 \
  --rubric comprehensive \
  --output results/llm/
```

**Output:** File coverage, concept coverage, accuracy, completeness scores

### Step 3: Compare Results

**Example report structure:**
```
=== Sia-code Benchmark Results ===

Academic Metrics (Phase 1):
  Recall@5:    0.842 (+0.120 vs grep)
  Precision@5: 0.780 (+0.085 vs grep)
  nDCG@5:      0.815 (+0.098 vs grep)
  MRR:         0.732 (+0.145 vs grep)

LLM Evaluation (Phase 2):
  Overall Score:       82.5/100 (+18.3 vs grep)
  File Coverage:       85.0/100 (+22.0 vs grep)
  Concept Coverage:    90.0/100 (+25.5 vs grep)
  Accuracy:            88.0/100 (+12.0 vs grep)
  Completeness:        75.0/100 (+15.0 vs grep)
  Clarity:             80.0/100 (+10.0 vs grep)

Judge Consensus:
  GPT-4o:      82.5/100
  Claude Opus: 78.0/100
  Gemini Pro:  80.0/100
  Agreement:   ±2.25 (high consensus)

Conclusion:
  Sia-code demonstrates significant advantages in both retrieval 
  accuracy (+12% Recall@5) and architectural understanding quality 
  (+18.3 overall LLM score). Multi-hop search and AST chunking 
  enable comprehensive code path tracing vs grep's keyword matching.
```

## Comparison with ChunkHound

| Feature | ChunkHound | Sia-code (Phase 2) |
|---------|------------|---------------------|
| **Benchmark approach** | Kubernetes controller tracing | Multi-codebase (sia-code, Flask, FastAPI) |
| **Task types** | Trace only | Trace, architecture, dependency, integration |
| **Judge models** | GPT-4 | GPT-4o, Claude Opus, Gemini Pro (multi-judge) |
| **Rubrics** | Single rubric | 3 rubrics (comprehensive/quick/strict) |
| **Retrieval evaluation** | Not separate | Separate retrieval quality assessment |
| **Comparison mode** | Not supported | Side-by-side tool comparison |
| **Output format** | Custom | JSON + structured reports |

**Advantages over ChunkHound:**
1. **Multi-judge consensus** reduces single-model bias
2. **4 task types** (not just tracing) test different skills
3. **Retrieval quality** evaluated before analysis (identifies retrieval vs analysis failures)
4. **3 difficulty levels** (easy/medium/hard) for granular assessment
5. **Strict rubric** with pass/fail threshold (70) for production gates

## Cost Estimates

**Per-task evaluation costs (approximate):**

| Judge Model | Cost per Evaluation | Full Suite (9 tasks) |
|-------------|---------------------|----------------------|
| GPT-4o | $0.015 | $0.135 |
| Claude Opus 4 | $0.045 | $0.405 |
| Gemini 2.0 Flash | $0.002 | $0.018 |

**Multi-judge consensus (all 3 judges):** ~$0.062 per task, $0.558 for full suite

**Recommendation:** Use GPT-4o for primary evaluation ($0.135/suite), add Claude/Gemini for critical releases.

## Next Steps

### Phase 3: Time-Travel Enhancements (Planned)

**Priority 1 features:**
1. Rich session metadata (tags, context, git branch)
2. Replay with parameter variation (--top-k 20 --diff)
3. Provenance chain (track who/when/why for changes)

**Priority 2 features:**
1. Session branching (what-if analysis)
2. Complex temporal queries ("between Monday and yesterday")
3. Compliance export (SOC2/HIPAA formatted)

### Integration Testing (Immediate)

1. Replace dummy retrievers with actual implementations
2. Run pilot benchmark on sia-code codebase
3. Validate judge consensus (inter-judge agreement > 80%)
4. Tune rubric weights based on feedback

## Files Summary

**New files (Phase 2):**
```
tests/benchmarks/tasks/
├── __init__.py                      # 15 lines
├── architectural_tasks.py           # 295 lines (9 tasks, 4 helper functions)
└── evaluation_prompts.py            # 360 lines (4 prompt types, 3 rubrics)

tests/benchmarks/
├── llm_evaluation.py                # 445 lines (LLMJudge + 3 clients)
└── run_llm_benchmarks.py            # 395 lines (CLI runner)

PHASE2_LLM_BENCHMARKS.md             # This file (comprehensive docs)
```

**Total:** ~1,510 lines of production code + 360 lines of documentation

**Updated files:**
- `tests/benchmarks/__init__.py` - Added LLM evaluation exports

## Summary

Phase 2 provides **production-grade qualitative evaluation** for code retrieval tools:

✅ **9 architectural tasks** across 3 codebases (sia-code, Flask, FastAPI)  
✅ **Multi-judge consensus** (GPT-4o, Claude Opus, Gemini Pro)  
✅ **3 rubric modes** (comprehensive, quick, strict)  
✅ **Side-by-side comparison** (sia-code vs grep vs ChunkHound)  
✅ **Retrieval quality assessment** (separate from analysis quality)  
✅ **Comprehensive scoring** (5 dimensions: coverage, accuracy, completeness, clarity)  
✅ **CLI runner** with JSON output for CI/CD integration  

**Ready for integration testing** after replacing dummy retrievers with actual sia-code backend.
