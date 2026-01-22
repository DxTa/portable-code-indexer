# Research Papers Informing sia-code Multi-Language Enhancements

This document lists the academic papers that informed the design of sia-code's multi-language code understanding features, including dependency indexing, documentation linking, and adaptive search strategies.

## Core Papers

### 1. COSAL - Multi-Modal Code Search
- **arXiv:** [2106.09173](https://arxiv.org/abs/2106.09173)
- **Title:** "COSAL: A Multi-modal Approach to Code Search with Non-dominated Ranking"
- **Key Finding:** Multi-modal search using token, AST, and behavioral similarity achieves **64% MRR** vs 37% for GitHub search.
- **Application:** 
  - Single-language projects use weighted ranking (faster)
  - Multi-language projects use non-dominated ranking (more accurate)
  - Similarity correlations are stronger within single language (|r| up to 0.68) than cross-language (|r| < 0.41)

### 2. Language Agnostic Code Embeddings
- **arXiv:** [2310.16803](https://arxiv.org/abs/2310.16803)
- **Title:** "Language Agnostic Code Embeddings"
- **Key Finding:** Removing language-specific components from embeddings improves cross-language retrieval by **+17 MRR**.
- **Application:** Language-agnostic embedding transformation for multi-language projects (future enhancement).

### 3. GraphGen4Code - Code Knowledge Graphs
- **arXiv:** [2002.09440](https://arxiv.org/abs/2002.09440)
- **Title:** "GraphGen4Code: A Toolkit for Creating Code Knowledge Graphs"
- **Key Finding:** Knowledge graphs linking code to documentation enable better code understanding. Built 2 billion triples from 1.3M Python files.
- **Application:** Documentation linking design - creating edges between code chunks and documentation.

### 4. DocPrompting - Documentation Retrieval for Code Generation
- **arXiv:** [2207.05987](https://arxiv.org/abs/2207.05987)
- **Title:** "DocPrompting: Generating Code by Retrieving the Docs"
- **Key Finding:** Retrieving relevant documentation for code generation yields **+52% relative gain** in pass@1.
- **Application:** Validates the importance of linking documentation to code context.

### 5. Semantic Code Graph for Dependency Comprehension
- **arXiv:** [2310.02128](https://arxiv.org/abs/2310.02128)
- **Title:** "Semantic Code Graph for Dependency Comprehension"
- **Key Finding:** Better than Call Graph and Class Collaboration Network for understanding dependencies.
- **Application:** Informed the dependency graph structure with typed relationships.

### 6. Static Analysis of Multilanguage Software Systems
- **arXiv:** [1906.00815](https://arxiv.org/abs/1906.00815)
- **Title:** "Static Analysis of Multilanguage Software Systems"
- **Key Finding:** Multi-language systems have hidden dependencies created by frameworks (e.g., Java ↔ JavaScript in JEE).
- **Application:** Use ecosystem tools (pip, npm, cargo) for accurate dependency discovery instead of manual parsing.

### 7. DependEval - Dependency Understanding Benchmark
- **arXiv:** [2503.06689](https://arxiv.org/abs/2503.06689)
- **Title:** "DependEval: Evaluating LLMs on Dependency Understanding"
- **Key Finding:** LLMs have substantial performance gaps in understanding dependencies across 8 programming languages.
- **Application:** Validates the need for explicit dependency indexing rather than relying on LLM inference.

### 8. UAST - Unified Abstract Syntax Tree
- **arXiv:** [2205.00424](https://arxiv.org/abs/2205.00424)
- **Title:** "UAST: A Unified AST Representation for Cross-Language Code Analysis"
- **Key Finding:** Unified AST schema enables cross-language structural comparison.
- **Application:** Future enhancement - unified AST normalization layer for structural similarity.

### 9. Prometheus - Code Knowledge Graphs
- **arXiv:** [2507.19942](https://arxiv.org/abs/2507.19942)
- **Title:** "Prometheus: A Code Knowledge Graph with Typed Edges"
- **Key Finding:** Knowledge graphs with 5 typed edges (data_flow, control_flow, calls, imports, inheritance) improve multi-language code understanding.
- **Application:** Future enhancement - typed relationship edges in the code graph.

### 10. Breaking-Good - Dependency Update Analysis
- **arXiv:** [2407.03880](https://arxiv.org/abs/2407.03880)
- **Title:** "Breaking-Good: Explaining Breaking Dependency Updates"
- **Key Finding:** Root cause identification in dependency trees helps understand breaking changes.
- **Application:** Track package versions in metadata for dependency analysis.

## Summary of Applications

| Feature | Papers Applied |
|---------|----------------|
| **Tiered Indexing** | COSAL, DependEval |
| **Dependency Discovery** | Multi-language Analysis, DependEval, Breaking-Good |
| **Documentation Linking** | GraphGen4Code, DocPrompting |
| **Auto-Detection** | COSAL (single vs multi-language) |
| **Search Ranking** | COSAL (non-dominated vs weighted) |
| **Future: Unified AST** | UAST, Prometheus |
| **Future: Language-Agnostic Embeddings** | Language Agnostic Embeddings |

## References

1. COSAL (2106.09173) - https://arxiv.org/abs/2106.09173
2. Language Agnostic Embeddings (2310.16803) - https://arxiv.org/abs/2310.16803
3. GraphGen4Code (2002.09440) - https://arxiv.org/abs/2002.09440
4. DocPrompting (2207.05987) - https://arxiv.org/abs/2207.05987
5. Semantic Code Graph (2310.02128) - https://arxiv.org/abs/2310.02128
6. Multi-language Analysis (1906.00815) - https://arxiv.org/abs/1906.00815
7. DependEval (2503.06689) - https://arxiv.org/abs/2503.06689
8. UAST (2205.00424) - https://arxiv.org/abs/2205.00424
9. Prometheus (2507.19942) - https://arxiv.org/abs/2507.19942
10. Breaking-Good (2407.03880) - https://arxiv.org/abs/2407.03880
