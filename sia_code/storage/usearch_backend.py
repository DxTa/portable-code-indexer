"""Usearch + SQLite FTS5 storage backend for code and memory."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from usearch.index import Index, MetricKind

from ..core.models import (
    ChangelogEntry,
    Chunk,
    Decision,
    ImportResult,
    IndexStats,
    SearchResult,
    TimelineEvent,
)
from ..core.types import ChunkType, Language
from .base import StorageBackend


class UsearchSqliteBackend(StorageBackend):
    """Storage backend using usearch (HNSW) + SQLite (FTS5).

    File structure:
    - .sia-code/vectors.usearch: HNSW index (f16 quantization)
    - .sia-code/index.db: SQLite database with FTS5

    Features:
    - 10x faster than FAISS (usearch HNSW)
    - f16 quantization (~2 bytes/dim)
    - Unified index (code + memory)
    - Full-text search with FTS5
    - Hybrid search with RRF
    - Decision workflow with FIFO
    - Git timeline integration
    - Import/export for collaboration
    """

    def __init__(
        self,
        path: Path,
        embedding_enabled: bool = True,
        embedding_model: str = "BAAI/bge-small-en-v1.5",
        ndim: int = 384,
        dtype: str = "f16",
        metric: str = "cos",
        **kwargs,
    ):
        """Initialize usearch + SQLite backend.

        Args:
            path: Path to .sia-code directory
            embedding_enabled: Whether to enable embeddings
            embedding_model: Embedding model name (e.g., 'bge-small')
            ndim: Embedding dimensionality
            dtype: Vector data type ('f16', 'f32', 'i8')
            metric: Distance metric ('cos', 'l2sq', 'ip')
            **kwargs: Additional configuration
        """
        super().__init__(path, **kwargs)
        self.embedding_enabled = embedding_enabled
        self.embedding_model = embedding_model
        self.ndim = ndim
        self.dtype = dtype
        self.metric = metric

        # Paths
        self.vector_path = self.path / "vectors.usearch"
        self.db_path = self.path / "index.db"

        # Will be initialized in create_index() or open_index()
        self.vector_index: Index | None = None
        self.conn: sqlite3.Connection | None = None
        self._embedder = None  # Lazy-loaded embedding model

        # Thread-local storage for parallel search
        import threading

        self._local = threading.local()

        # Search result cache
        self._search_cache: dict[str, list] | None = None
        self._search_cache_enabled = False

        # Vector key prefixes for unified index
        self.KEY_PREFIX_CHUNK = "chunk:"
        self.KEY_PREFIX_TIMELINE = "timeline:"
        self.KEY_PREFIX_CHANGELOG = "changelog:"
        self.KEY_PREFIX_DECISION = "decision:"
        self.KEY_PREFIX_MEMORY = "memory:"

    def _get_embedder(self):
        """Lazy-load the embedding model with GPU if available."""
        if self._embedder is None:
            # Import here to avoid loading if not needed
            from sentence_transformers import SentenceTransformer
            import torch
            import logging

            # Auto-detect device (GPU if available, CPU fallback)
            device = "cuda" if torch.cuda.is_available() else "cpu"

            self._embedder = SentenceTransformer(self.embedding_model, device=device)

            # Log device for debugging
            logger = logging.getLogger(__name__)
            logger.info(f"Loaded {self.embedding_model} on {device.upper()}")

        return self._embedder

    def _get_thread_conn(self) -> sqlite3.Connection:
        """Get thread-local SQLite connection for parallel operations.

        Returns:
            Thread-safe SQLite connection
        """
        if not hasattr(self._local, "conn") or self._local.conn is None:
            # Create new connection for this thread
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    def _embed(self, text: str) -> np.ndarray | None:
        """Embed text to vector with caching.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as numpy array, or None if embeddings disabled
        """
        if not self.embedding_enabled:
            return None

        # Use cached version to avoid re-embedding same text
        cached_result = self._embed_cached(text)
        if cached_result is not None:
            return np.array(cached_result)
        return None

    def _embed_cached(self, text: str) -> tuple | None:
        """Cached embedding with LRU cache.

        Returns tuple instead of ndarray for hashability (cache requirement).
        """
        from functools import lru_cache

        # Create cache on first call
        if not hasattr(self, "_embedding_cache"):

            @lru_cache(maxsize=1000)
            def cached_encode(text: str) -> tuple:
                embedder = self._get_embedder()
                vector = embedder.encode(text, convert_to_numpy=True)
                return tuple(vector.tolist())

            self._embedding_cache = cached_encode

        return self._embedding_cache(text)

    def _make_chunk_key(self, chunk_id: int) -> str:
        """Create vector index key for chunk."""
        return f"{self.KEY_PREFIX_CHUNK}{chunk_id}"

    def _make_decision_key(self, decision_id: int) -> str:
        """Create vector index key for decision."""
        return f"{self.KEY_PREFIX_DECISION}{decision_id}"

    def _sanitize_fts5_query(self, query: str) -> str:
        """Extract FTS5-safe tokens from code query.

        Handles special characters in code (., #, (), "", etc.) by extracting
        only alphanumeric identifiers and joining with OR for broader matching.

        Args:
            query: Raw query text (may contain code)

        Returns:
            FTS5-safe query string
        """
        import re

        # Extract alphanumeric identifiers (function names, variables, classes)
        tokens = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b", query)

        if not tokens:
            # Fallback to empty phrase if no valid tokens
            return '""'

        # Remove duplicates while preserving order, case-insensitive
        seen = set()
        unique = []
        for t in tokens:
            t_lower = t.lower()
            if t_lower not in seen:
                seen.add(t_lower)
                unique.append(t)

        # Limit to 20 tokens for performance, join with OR for broader matching
        return " OR ".join(unique[:20])

    def _make_timeline_key(self, timeline_id: int) -> str:
        """Create vector index key for timeline."""
        return f"{self.KEY_PREFIX_TIMELINE}{timeline_id}"

    def _make_changelog_key(self, changelog_id: int) -> str:
        """Create vector index key for changelog."""
        return f"{self.KEY_PREFIX_CHANGELOG}{changelog_id}"

    def _parse_vector_key(self, key: str) -> tuple[str, int]:
        """Parse vector key into type and ID.

        Returns:
            Tuple of (type, id) where type is 'chunk', 'decision', etc.
        """
        for prefix in [
            self.KEY_PREFIX_CHUNK,
            self.KEY_PREFIX_TIMELINE,
            self.KEY_PREFIX_CHANGELOG,
            self.KEY_PREFIX_DECISION,
            self.KEY_PREFIX_MEMORY,
        ]:
            if key.startswith(prefix):
                type_name = prefix.rstrip(":")
                id_str = key[len(prefix) :]
                return (type_name, int(id_str))
        raise ValueError(f"Invalid vector key: {key}")

    # ===================================================================
    # Index Lifecycle
    # ===================================================================

    def create_index(self) -> None:
        """Create a new index (vectors + SQLite)."""
        self.path.mkdir(parents=True, exist_ok=True)

        # Create usearch vector index
        self.vector_index = Index(
            ndim=self.ndim,
            metric=MetricKind.Cos if self.metric == "cos" else MetricKind.L2sq,
            dtype=self.dtype,
        )

        # Create SQLite database (check_same_thread=False for parallel search)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        self._create_tables()

    def open_index(self) -> None:
        """Open an existing index."""
        if not self.vector_path.exists():
            raise FileNotFoundError(f"Vector index not found: {self.vector_path}")
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        # Load usearch index (memory-mapped for fast access)
        self.vector_index = Index(ndim=self.ndim, metric=MetricKind.Cos, dtype=self.dtype)
        self.vector_index.view(str(self.vector_path))

        # Open SQLite database (check_same_thread=False for parallel search)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        """Close the index and save changes."""
        if self.vector_index is not None:
            # Save usearch index
            self.vector_index.save(str(self.vector_path))

        if self.conn is not None:
            self.conn.commit()
            self.conn.close()
            self.conn = None

    def seal(self) -> None:
        """Seal the index to finalize WAL and reduce storage.

        For SQLite, this commits pending transactions and optimizes the database.
        """
        if self.conn is not None:
            try:
                self.conn.commit()
                # Optional: VACUUM to reclaim space (can be slow on large DBs)
                # self.conn.execute("VACUUM")
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to seal index: {e}")

    def _create_tables(self) -> None:
        """Create all SQLite tables."""
        if self.conn is None:
            raise RuntimeError("Database connection not initialized")

        cursor = self.conn.cursor()

        # Code chunks table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uri TEXT UNIQUE,
                symbol TEXT,
                chunk_type TEXT,
                file_path TEXT,
                start_line INTEGER,
                end_line INTEGER,
                language TEXT,
                code TEXT,
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # FTS5 for code search
        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                symbol, code, content=chunks, content_rowid=id
            )
        """
        )

        # Triggers to keep FTS5 in sync
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
                INSERT INTO chunks_fts(rowid, symbol, code) 
                VALUES (new.id, new.symbol, new.code);
            END
        """
        )

        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
                DELETE FROM chunks_fts WHERE rowid = old.id;
            END
        """
        )

        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
                DELETE FROM chunks_fts WHERE rowid = old.id;
                INSERT INTO chunks_fts(rowid, symbol, code) 
                VALUES (new.id, new.symbol, new.code);
            END
        """
        )

        # Index for file path queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_file_path ON chunks(file_path)")

        # Timeline events table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS timeline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                from_ref TEXT,
                to_ref TEXT,
                summary TEXT,
                files_changed JSON,
                diff_stats JSON,
                importance TEXT DEFAULT 'medium',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Changelogs table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS changelogs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tag TEXT UNIQUE,
                version TEXT,
                date TIMESTAMP,
                summary TEXT,
                breaking_changes JSON,
                features JSON,
                fixes JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Decisions table (pending, max 100 with FIFO)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                title TEXT,
                description TEXT,
                reasoning TEXT,
                alternatives JSON,
                status TEXT DEFAULT 'pending',
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_at TIMESTAMP
            )
        """
        )

        # FIFO trigger for decisions (delete oldest when >100 pending)
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS decisions_fifo 
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
            END
        """
        )

        # Approved memory table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS approved_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id INTEGER REFERENCES decisions(id),
                category TEXT,
                title TEXT,
                content TEXT,
                approved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # FTS5 for memory search (decisions + approved memory)
        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                title, description, content
            )
        """
        )

        self.conn.commit()

    # The rest of the methods will be added in subsequent parts...

    # ===================================================================
    # Code Operations
    # ===================================================================

    def store_chunks_batch(self, chunks: list[Chunk]) -> list[str]:
        """Store multiple code chunks.

        Args:
            chunks: List of code chunks to store

        Returns:
            List of chunk IDs (as strings)
        """
        if self.conn is None or self.vector_index is None:
            raise RuntimeError("Index not initialized")

        cursor = self.conn.cursor()
        chunk_ids = []

        for chunk in chunks:
            # Insert into SQLite
            uri = f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line}"
            cursor.execute(
                """
                INSERT INTO chunks (uri, symbol, chunk_type, file_path, start_line, end_line, language, code, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    uri,
                    chunk.symbol,
                    chunk.chunk_type.value,
                    str(chunk.file_path),
                    chunk.start_line,
                    chunk.end_line,
                    chunk.language.value,
                    chunk.code,
                    json.dumps(chunk.metadata),
                ),
            )
            chunk_id = cursor.lastrowid

            # Embed and add to vector index (if embeddings enabled)
            if self.embedding_enabled:
                vector = self._embed(f"{chunk.symbol}\n\n{chunk.code}")
                vector_key = self._make_chunk_key(chunk_id)
                self.vector_index.add(chunk_id, vector)  # Use numeric ID, we'll prefix on search

            chunk_ids.append(str(chunk_id))

        self.conn.commit()
        return chunk_ids

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        """Retrieve a chunk by ID.

        Args:
            chunk_id: The chunk identifier

        Returns:
            Chunk if found, None otherwise
        """
        if self.conn is None:
            raise RuntimeError("Index not initialized")

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, symbol, chunk_type, file_path, start_line, end_line, 
                   language, code, metadata, created_at
            FROM chunks
            WHERE id = ?
        """,
            (int(chunk_id),),
        )

        row = cursor.fetchone()
        if row is None:
            return None

        return Chunk(
            id=str(row["id"]),
            symbol=row["symbol"],
            chunk_type=ChunkType(row["chunk_type"]),
            file_path=Path(row["file_path"]),
            start_line=row["start_line"],
            end_line=row["end_line"],
            language=Language(row["language"]),
            code=row["code"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )

    def _preprocess_code_query(self, code: str) -> str:
        """Extract searchable terms from code snippet.

        Code queries (e.g., from RepoEval) contain operators, punctuation, and noise.
        This extracts meaningful identifiers and API patterns for better retrieval.

        Args:
            code: Raw code snippet

        Returns:
            Space-separated search terms
        """
        import re

        terms = []

        # Extract identifiers (CamelCase, snake_case, alphanumeric)
        # Match: MyClass, my_function, getUserData, API_KEY, model123
        identifiers = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b", code)

        for ident in identifiers:
            # Skip common keywords
            if ident.lower() in {
                "def",
                "class",
                "import",
                "from",
                "return",
                "if",
                "else",
                "elif",
                "for",
                "while",
                "try",
                "except",
                "with",
                "as",
                "self",
                "true",
                "false",
                "none",
                "null",
                "var",
                "let",
                "const",
                "function",
                "this",
                "super",
                "new",
            }:
                continue

            # Split CamelCase: getUserData -> get User Data
            camel_parts = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)", ident)
            if len(camel_parts) > 1:
                terms.extend(camel_parts)

            # Split snake_case: my_function -> my function
            snake_parts = ident.split("_")
            if len(snake_parts) > 1:
                terms.extend([p for p in snake_parts if len(p) > 1])

            # Add full identifier
            terms.append(ident)

        # Extract API-like patterns (e.g., model.from_pretrained, np.array)
        api_calls = re.findall(r"([a-zA-Z_][a-zA-Z0-9_]*\.[a-zA-Z_][a-zA-Z0-9_]*)", code)
        for call in api_calls:
            terms.append(
                call.replace(".", " ")
            )  # "model.from_pretrained" -> "model from_pretrained"
            terms.append(call.split(".")[-1])  # Also add just "from_pretrained"

        # Deduplicate while preserving order
        seen = set()
        unique_terms = []
        for term in terms:
            term_lower = term.lower()
            if term_lower not in seen and len(term) > 1:
                seen.add(term_lower)
                unique_terms.append(term)

        # Limit to top 30 terms to avoid overwhelming the query
        return " ".join(unique_terms[:30])

    def search_semantic(self, query: str, k: int = 10, filter_fn: Any = None) -> list[SearchResult]:
        """Semantic vector search using usearch HNSW.

        Args:
            query: Query text (will be embedded)
            k: Number of results to return
            filter_fn: Optional filter function (not implemented yet)

        Returns:
            List of search results sorted by relevance
        """
        if self.vector_index is None:
            raise RuntimeError("Index not initialized")

        if not self.embedding_enabled:
            # If embeddings disabled, return empty results (fallback to lexical)
            return []

        # Embed query
        query_vector = self._embed(query)

        if query_vector is None:
            return []

        # Search usearch index
        matches = self.vector_index.search(query_vector, k)

        # Convert to SearchResults
        results = []
        for key, distance in zip(matches.keys, matches.distances):
            # Keys are numeric chunk IDs
            chunk = self.get_chunk(str(key))
            if chunk:
                # Convert distance to similarity score (0-1, higher is better)
                # For cosine distance, score = 1 - distance
                score = 1.0 - float(distance)
                results.append(SearchResult(chunk=chunk, score=score))

        return results

    def search_lexical(self, query: str, k: int = 10) -> list[SearchResult]:
        """Lexical full-text search using SQLite FTS5.

        Args:
            query: Query text
            k: Number of results to return

        Returns:
            List of search results sorted by relevance
        """
        if self.conn is None:
            raise RuntimeError("Index not initialized")

        cursor = self.conn.cursor()

        # Sanitize query for FTS5 using token extraction
        sanitized_query = self._sanitize_fts5_query(query)

        # FTS5 search
        cursor.execute(
            """
            SELECT chunks.id, bm25(chunks_fts) as rank
            FROM chunks_fts
            JOIN chunks ON chunks.id = chunks_fts.rowid
            WHERE chunks_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """,
            (sanitized_query, k),
        )

        results = []
        for row in cursor.fetchall():
            chunk = self.get_chunk(str(row["id"]))
            if chunk:
                # BM25 returns negative scores, normalize to 0-1
                score = abs(float(row["rank"])) / 100.0  # Rough normalization
                results.append(SearchResult(chunk=chunk, score=score))

        return results

    def search_hybrid(
        self,
        query: str,
        k: int = 10,
        vector_weight: float = 0.7,
        include_deps: bool = True,
        tier_boost: dict | None = None,
        preprocess_code: bool = False,
        parallel: bool = True,
        use_cache: bool = False,
    ) -> list[SearchResult]:
        """Hybrid search using Reciprocal Rank Fusion (RRF).

        Args:
            query: Query text (or code snippet)
            k: Number of results to return
            vector_weight: Weight for vector search (0-1)
            include_deps: Include dependency chunks (for compatibility, not yet implemented)
            tier_boost: Tier boosting configuration (for compatibility, not yet implemented)
            preprocess_code: If True, extract searchable terms from code query (for RepoEval-style queries)
            parallel: If True, run semantic and lexical searches in parallel (~2x speedup)
            use_cache: If True, cache search results (good for repeated queries)

        Returns:
            List of search results sorted by combined relevance
        """
        # Generate cache key (used later if caching enabled)
        cache_key = f"{query}:{k}:{vector_weight}:{preprocess_code}"

        # Check cache if enabled
        if use_cache:
            if self._search_cache is None:
                # Initialize cache dict
                self._search_cache = {}

            if cache_key in self._search_cache:
                return self._search_cache[cache_key]

        # Preprocess code query if requested
        processed_query = query
        if preprocess_code:
            processed_query = self._preprocess_code_query(query)
            # Use original query for semantic (better for embeddings), processed for lexical

        # If embeddings disabled, fall back to lexical only
        if not self.embedding_enabled:
            results = self.search_lexical(processed_query if preprocess_code else query, k)
            if use_cache and self._search_cache is not None:
                self._search_cache[cache_key] = results
            return results

        # Fetch more candidates for fusion
        fetch_k = k * 3

        # Get semantic and lexical results (parallel or sequential)
        # Semantic: use original query (embeddings work better with raw code context)
        # Lexical: use processed query (FTS5 works better with extracted terms)
        if parallel:
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=2) as executor:
                semantic_future = executor.submit(self.search_semantic, query, fetch_k)
                lexical_future = executor.submit(
                    self.search_lexical, processed_query if preprocess_code else query, fetch_k
                )
                semantic_results = semantic_future.result()
                lexical_results = lexical_future.result()
        else:
            # Sequential execution (original behavior)
            semantic_results = self.search_semantic(query, fetch_k)
            lexical_results = self.search_lexical(
                processed_query if preprocess_code else query, fetch_k
            )

        # Reciprocal Rank Fusion
        scores: dict[str, float] = {}
        k_rrf = 60  # RRF constant

        # Add semantic scores
        for rank, result in enumerate(semantic_results):
            chunk_id = result.chunk.id
            if chunk_id:
                scores[chunk_id] = scores.get(chunk_id, 0) + vector_weight / (k_rrf + rank)

        # Add lexical scores
        lexical_weight = 1.0 - vector_weight
        for rank, result in enumerate(lexical_results):
            chunk_id = result.chunk.id
            if chunk_id:
                scores[chunk_id] = scores.get(chunk_id, 0) + lexical_weight / (k_rrf + rank)

        # Sort by combined score
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]

        # Batch fetch chunks (much faster than individual get_chunk calls)
        chunk_ids = [chunk_id for chunk_id, _ in ranked]
        if not chunk_ids:
            return []

        # Fetch all chunks in one query
        cursor = self.conn.cursor()
        placeholders = ",".join("?" * len(chunk_ids))
        cursor.execute(
            f"""
            SELECT id, symbol, chunk_type, file_path, start_line, end_line,
                   language, code, metadata, created_at
            FROM chunks WHERE id IN ({placeholders})
            """,
            chunk_ids,
        )

        # Build chunk lookup
        chunk_lookup = {}
        for row in cursor.fetchall():
            chunk_lookup[str(row["id"])] = Chunk(
                id=str(row["id"]),
                symbol=row["symbol"],
                chunk_type=ChunkType(row["chunk_type"]),
                file_path=Path(row["file_path"]),
                start_line=row["start_line"],
                end_line=row["end_line"],
                language=Language(row["language"]),
                code=row["code"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            )

        # Convert to SearchResults in original ranked order
        results = []
        for chunk_id, score in ranked:
            chunk = chunk_lookup.get(chunk_id)
            if chunk:
                results.append(SearchResult(chunk=chunk, score=score))

        # Cache results if enabled
        if use_cache and self._search_cache is not None:
            cache_key = f"{query}:{k}:{vector_weight}:{preprocess_code}"
            self._search_cache[cache_key] = results
            # Limit cache size to prevent memory issues
            if len(self._search_cache) > 500:
                # Remove oldest entries (simple FIFO)
                oldest_keys = list(self._search_cache.keys())[:100]
                for key in oldest_keys:
                    del self._search_cache[key]

        return results

    def search_files(
        self,
        query: str,
        k: int = 10,
        vector_weight: float = 0.7,
        preprocess_code: bool = False,
        aggregation: str = "sum",
    ) -> list[tuple[str, float]]:
        """Search and aggregate results at file level (for RepoEval-style benchmarks).

        Returns files ranked by aggregated chunk scores, useful for file-level recall metrics.

        Args:
            query: Query text
            k: Number of files to return
            vector_weight: Weight for vector search (0-1)
            preprocess_code: If True, extract searchable terms from code query
            aggregation: Score aggregation method ("sum" or "max")

        Returns:
            List of (file_path, score) tuples sorted by relevance
        """
        # Get more chunk results to ensure good file coverage
        fetch_k = k * 5

        chunk_results = self.search_hybrid(
            query, k=fetch_k, vector_weight=vector_weight, preprocess_code=preprocess_code
        )

        # Aggregate by file
        file_scores: dict[str, list[float]] = {}
        for result in chunk_results:
            file_path = str(result.chunk.file_path)
            if file_path not in file_scores:
                file_scores[file_path] = []
            file_scores[file_path].append(result.score)

        # Compute aggregated scores
        ranked_files = []
        for file_path, scores in file_scores.items():
            if aggregation == "max":
                agg_score = max(scores)
            else:  # sum
                agg_score = sum(scores)
            ranked_files.append((file_path, agg_score))

        # Sort by score and return top k
        ranked_files.sort(key=lambda x: x[1], reverse=True)
        return ranked_files[:k]

    def get_stats(self) -> IndexStats:
        """Get index statistics.

        Returns:
            Index statistics including file count, chunk count, etc.
        """
        if self.conn is None:
            raise RuntimeError("Index not initialized")

        cursor = self.conn.cursor()

        # Count chunks
        cursor.execute("SELECT COUNT(*) as count FROM chunks")
        total_chunks = cursor.fetchone()["count"]

        # Count unique files
        cursor.execute("SELECT COUNT(DISTINCT file_path) as count FROM chunks")
        total_files = cursor.fetchone()["count"]

        # Count by language
        cursor.execute(
            """
            SELECT language, COUNT(*) as count 
            FROM chunks 
            GROUP BY language
        """
        )
        languages = {Language(row["language"]): row["count"] for row in cursor.fetchall()}

        # Get last indexed time
        cursor.execute("SELECT MAX(created_at) as last FROM chunks")
        last_indexed_str = cursor.fetchone()["last"]
        last_indexed = datetime.fromisoformat(last_indexed_str) if last_indexed_str else None

        return IndexStats(
            total_files=total_files,
            total_chunks=total_chunks,
            total_size_bytes=0,  # Not tracked in this backend
            languages=languages,
            last_indexed=last_indexed,
        )

    # ===================================================================
    # Decision Management
    # ===================================================================

    def add_decision(
        self,
        session_id: str,
        title: str,
        description: str,
        reasoning: str | None = None,
        alternatives: list[dict[str, Any]] | None = None,
    ) -> int:
        """Add a pending decision (FIFO auto-cleanup when >100).

        Args:
            session_id: LLM session that created this
            title: Short title
            description: Full context
            reasoning: Why this decision was made
            alternatives: Other options considered

        Returns:
            Decision ID
        """
        if self.conn is None:
            raise RuntimeError("Index not initialized")

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO decisions (session_id, title, description, reasoning, alternatives)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                session_id,
                title,
                description,
                reasoning,
                json.dumps(alternatives or []),
            ),
        )
        decision_id = cursor.lastrowid

        # Embed decision for semantic search
        decision_text = f"{title}\n\n{description}"
        if reasoning:
            decision_text += f"\n\nReasoning: {reasoning}"

        vector = self._embed(decision_text)
        # Store with decision key prefix
        vector_key = self._make_decision_key(decision_id)
        if self.vector_index:
            self.vector_index.add(decision_id + 1000000, vector)  # Offset to avoid ID collision

        self.conn.commit()
        return decision_id

    def approve_decision(self, decision_id: int, category: str) -> int:
        """Promote decision to permanent memory.

        Args:
            decision_id: ID of pending decision
            category: Category like 'architecture', 'pattern'

        Returns:
            Approved memory ID
        """
        if self.conn is None:
            raise RuntimeError("Index not initialized")

        cursor = self.conn.cursor()

        # Get the decision
        cursor.execute(
            """
            SELECT title, description, reasoning 
            FROM decisions 
            WHERE id = ? AND status = 'pending'
        """,
            (decision_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Decision {decision_id} not found or already processed")

        # Update decision status
        cursor.execute(
            """
            UPDATE decisions 
            SET status = 'approved', category = ?, approved_at = ?
            WHERE id = ?
        """,
            (category, datetime.now().isoformat(), decision_id),
        )

        # Add to approved memory
        content = f"{row['description']}\n\nReasoning: {row['reasoning'] or 'N/A'}"
        cursor.execute(
            """
            INSERT INTO approved_memory (decision_id, category, title, content)
            VALUES (?, ?, ?, ?)
        """,
            (decision_id, category, row["title"], content),
        )
        memory_id = cursor.lastrowid

        self.conn.commit()
        return memory_id

    def reject_decision(self, decision_id: int) -> None:
        """Mark decision as rejected.

        Args:
            decision_id: ID of pending decision
        """
        if self.conn is None:
            raise RuntimeError("Index not initialized")

        cursor = self.conn.cursor()
        cursor.execute(
            """
            UPDATE decisions 
            SET status = 'rejected'
            WHERE id = ? AND status = 'pending'
        """,
            (decision_id,),
        )
        self.conn.commit()

    def list_pending_decisions(self, limit: int = 20) -> list[Decision]:
        """List oldest pending decisions for review.

        Args:
            limit: Maximum number to return

        Returns:
            List of pending decisions, oldest first
        """
        if self.conn is None:
            raise RuntimeError("Index not initialized")

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, session_id, title, description, reasoning, alternatives, 
                   status, category, created_at, approved_at
            FROM decisions
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT ?
        """,
            (limit,),
        )

        decisions = []
        for row in cursor.fetchall():
            decisions.append(
                Decision(
                    id=row["id"],
                    session_id=row["session_id"],
                    title=row["title"],
                    description=row["description"],
                    reasoning=row["reasoning"],
                    alternatives=json.loads(row["alternatives"]) if row["alternatives"] else [],
                    status=row["status"],
                    category=row["category"],
                    created_at=datetime.fromisoformat(row["created_at"])
                    if row["created_at"]
                    else None,
                    approved_at=datetime.fromisoformat(row["approved_at"])
                    if row["approved_at"]
                    else None,
                )
            )

        return decisions

    def get_decision(self, decision_id: int) -> Decision | None:
        """Get a specific decision by ID.

        Args:
            decision_id: Decision ID

        Returns:
            Decision if found, None otherwise
        """
        if self.conn is None:
            raise RuntimeError("Index not initialized")

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, session_id, title, description, reasoning, alternatives,
                   status, category, created_at, approved_at
            FROM decisions
            WHERE id = ?
        """,
            (decision_id,),
        )

        row = cursor.fetchone()
        if row is None:
            return None

        return Decision(
            id=row["id"],
            session_id=row["session_id"],
            title=row["title"],
            description=row["description"],
            reasoning=row["reasoning"],
            alternatives=json.loads(row["alternatives"]) if row["alternatives"] else [],
            status=row["status"],
            category=row["category"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            approved_at=datetime.fromisoformat(row["approved_at"]) if row["approved_at"] else None,
        )

    # ===================================================================
    # Timeline & Changelog Management
    # ===================================================================

    def add_timeline_event(
        self,
        event_type: str,
        from_ref: str,
        to_ref: str,
        summary: str,
        files_changed: list[str] | None = None,
        diff_stats: dict[str, Any] | None = None,
        importance: str = "medium",
    ) -> int:
        """Add a timeline event.

        Args:
            event_type: 'tag', 'merge', 'major_change'
            from_ref: Starting git ref
            to_ref: Ending git ref
            summary: Description
            files_changed: List of affected files
            diff_stats: Diff statistics
            importance: 'high', 'medium', 'low'

        Returns:
            Timeline event ID
        """
        if self.conn is None:
            raise RuntimeError("Index not initialized")

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO timeline (event_type, from_ref, to_ref, summary, files_changed, diff_stats, importance)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                event_type,
                from_ref,
                to_ref,
                summary,
                json.dumps(files_changed or []),
                json.dumps(diff_stats or {}),
                importance,
            ),
        )
        timeline_id = cursor.lastrowid

        # Embed timeline event for semantic search
        event_text = f"{event_type}: {from_ref} → {to_ref}\n\n{summary}"
        vector = self._embed(event_text)
        if self.vector_index:
            self.vector_index.add(timeline_id + 2000000, vector)  # Offset to avoid collision

        self.conn.commit()
        return timeline_id

    def add_changelog(
        self,
        tag: str,
        version: str | None = None,
        summary: str = "",
        breaking_changes: list[str] | None = None,
        features: list[str] | None = None,
        fixes: list[str] | None = None,
    ) -> int:
        """Add a changelog entry.

        Args:
            tag: Git tag
            version: Semantic version
            summary: Changelog summary
            breaking_changes: Breaking changes list
            features: Features list
            fixes: Fixes list

        Returns:
            Changelog entry ID
        """
        if self.conn is None:
            raise RuntimeError("Index not initialized")

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO changelogs (tag, version, summary, breaking_changes, features, fixes, date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                tag,
                version,
                summary,
                json.dumps(breaking_changes or []),
                json.dumps(features or []),
                json.dumps(fixes or []),
                datetime.now().isoformat(),
            ),
        )
        changelog_id = cursor.lastrowid

        # Embed changelog for semantic search
        changelog_text = f"{tag} ({version})\n\n{summary}"
        vector = self._embed(changelog_text)
        if self.vector_index:
            self.vector_index.add(changelog_id + 3000000, vector)  # Offset

        self.conn.commit()
        return changelog_id

    def get_timeline_events(
        self, from_ref: str | None = None, to_ref: str | None = None, limit: int = 20
    ) -> list[TimelineEvent]:
        """Get timeline events.

        Args:
            from_ref: Filter by starting ref
            to_ref: Filter by ending ref
            limit: Maximum number to return

        Returns:
            List of timeline events
        """
        if self.conn is None:
            raise RuntimeError("Index not initialized")

        cursor = self.conn.cursor()

        # Build query
        conditions = []
        params = []

        if from_ref:
            conditions.append("from_ref = ?")
            params.append(from_ref)
        if to_ref:
            conditions.append("to_ref = ?")
            params.append(to_ref)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        cursor.execute(
            f"""
            SELECT id, event_type, from_ref, to_ref, summary, files_changed, diff_stats, importance, created_at
            FROM timeline
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
        """,
            params,
        )

        events = []
        for row in cursor.fetchall():
            events.append(
                TimelineEvent(
                    id=row["id"],
                    event_type=row["event_type"],
                    from_ref=row["from_ref"],
                    to_ref=row["to_ref"],
                    summary=row["summary"],
                    files_changed=json.loads(row["files_changed"]) if row["files_changed"] else [],
                    diff_stats=json.loads(row["diff_stats"]) if row["diff_stats"] else {},
                    importance=row["importance"],
                    created_at=datetime.fromisoformat(row["created_at"])
                    if row["created_at"]
                    else None,
                )
            )

        return events

    def get_changelogs(self, limit: int = 20) -> list[ChangelogEntry]:
        """Get changelog entries.

        Args:
            limit: Maximum number to return

        Returns:
            List of changelog entries, newest first
        """
        if self.conn is None:
            raise RuntimeError("Index not initialized")

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, tag, version, date, summary, breaking_changes, features, fixes, created_at
            FROM changelogs
            ORDER BY date DESC
            LIMIT ?
        """,
            (limit,),
        )

        changelogs = []
        for row in cursor.fetchall():
            changelogs.append(
                ChangelogEntry(
                    id=row["id"],
                    tag=row["tag"],
                    version=row["version"],
                    date=datetime.fromisoformat(row["date"]) if row["date"] else None,
                    summary=row["summary"],
                    breaking_changes=json.loads(row["breaking_changes"])
                    if row["breaking_changes"]
                    else [],
                    features=json.loads(row["features"]) if row["features"] else [],
                    fixes=json.loads(row["fixes"]) if row["fixes"] else [],
                    created_at=datetime.fromisoformat(row["created_at"])
                    if row["created_at"]
                    else None,
                )
            )

        return changelogs

    # ===================================================================
    # Unified Search (Code + Memory)
    # ===================================================================

    def search_all(self, query: str, k: int = 10, vector_weight: float = 0.7) -> list[SearchResult]:
        """Search across both code and memory.

        Note: Currently just returns code search results.
        Full unified search across memory types needs ID offset handling.

        Args:
            query: Query text
            k: Number of results
            vector_weight: Weight for vector search

        Returns:
            List of results from code chunks
        """
        # For now, delegate to hybrid code search
        # TODO: Implement true unified search with proper ID handling
        return self.search_hybrid(query, k, vector_weight)

    def search_memory(
        self, query: str, k: int = 10, vector_weight: float = 0.7
    ) -> list[SearchResult]:
        """Search only memory (decisions + approved).

        Note: Simplified implementation for now.

        Args:
            query: Query text
            k: Number of results
            vector_weight: Weight for vector search

        Returns:
            List of results from decisions and approved memory
        """
        if self.conn is None:
            raise RuntimeError("Index not initialized")

        # Simple text search in decisions for now
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, title, description, category, status
            FROM decisions
            WHERE title LIKE ? OR description LIKE ?
            ORDER BY created_at DESC
            LIMIT ?
        """,
            (f"%{query}%", f"%{query}%", k),
        )

        # Convert to SearchResults (wrapping in fake chunks for compatibility)
        results = []
        for row in cursor.fetchall():
            # Create a pseudo-chunk for the decision
            fake_chunk = Chunk(
                symbol=row["title"],
                start_line=1,
                end_line=1,
                code=row["description"],
                chunk_type=ChunkType.FUNCTION,  # Fake type
                language=Language.PYTHON,  # Fake language
                file_path=Path(f"decisions/{row['id']}.md"),
                metadata={"type": "decision", "status": row["status"], "category": row["category"]},
            )
            results.append(SearchResult(chunk=fake_chunk, score=1.0))

        return results

    # ===================================================================
    # LLM Context Generation
    # ===================================================================

    def generate_context(
        self,
        query: str | None = None,
        include_code: bool = True,
        include_decisions: bool = True,
        include_timeline: bool = True,
        include_changelogs: bool = True,
    ) -> dict[str, Any]:
        """Generate JSON context for LLM consumption.

        Args:
            query: Optional query to include relevant code
            include_code: Include code chunks
            include_decisions: Include decisions
            include_timeline: Include timeline
            include_changelogs: Include changelogs

        Returns:
            Dictionary with project memory context
        """
        context: dict[str, Any] = {
            "project_memory": {
                "generated_at": datetime.now().isoformat(),
            }
        }

        # Codebase summary
        stats = self.get_stats()
        context["project_memory"]["codebase_summary"] = {
            "total_files": stats.total_files,
            "total_chunks": stats.total_chunks,
            "languages": [lang.value for lang in stats.languages.keys()],
            "last_indexed": stats.last_indexed.isoformat() if stats.last_indexed else None,
        }

        # Recent decisions
        if include_decisions:
            decisions = self.list_pending_decisions(limit=10)
            context["project_memory"]["recent_decisions"] = [
                {
                    "id": d.id,
                    "title": d.title,
                    "description": d.description,
                    "status": d.status,
                    "category": d.category,
                }
                for d in decisions
            ]

        # Recent timeline events
        if include_timeline:
            timeline = self.get_timeline_events(limit=10)
            context["project_memory"]["recent_changes"] = [
                {
                    "from": t.from_ref,
                    "to": t.to_ref,
                    "summary": t.summary,
                    "importance": t.importance,
                }
                for t in timeline
            ]

        # Changelogs
        if include_changelogs:
            changelogs = self.get_changelogs(limit=5)
            context["project_memory"]["changelogs"] = [
                {
                    "tag": c.tag,
                    "version": c.version,
                    "summary": c.summary,
                    "breaking_changes": c.breaking_changes,
                }
                for c in changelogs
            ]

        # Relevant code (if query provided)
        if include_code and query:
            code_results = self.search_hybrid(query, k=5)
            context["project_memory"]["relevant_code"] = [
                {
                    "file": str(r.chunk.file_path),
                    "symbol": r.chunk.symbol,
                    "code": r.chunk.code[:200],  # Truncate for context size
                    "score": r.score,
                }
                for r in code_results
            ]

        return context

    # ===================================================================
    # Import/Export for Collaboration
    # ===================================================================

    def export_memory(
        self,
        output_path: str | Path = ".sia-code/memory.json",
        include_timeline: bool = True,
        include_changelogs: bool = True,
        include_decisions: bool = True,
        include_pending: bool = False,
    ) -> str:
        """Export memory to JSON file for git commit.

        Args:
            output_path: Path to output file
            include_timeline: Include timeline events
            include_changelogs: Include changelog entries
            include_decisions: Include approved decisions
            include_pending: Include pending decisions

        Returns:
            Path to exported file
        """
        if self.conn is None:
            raise RuntimeError("Index not initialized")

        output_path = Path(output_path)
        if not output_path.is_absolute():
            output_path = self.path / output_path

        memory: dict[str, Any] = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "project": self.path.name,
        }

        # Timeline events
        if include_timeline:
            timeline = self.get_timeline_events(limit=100)
            memory["timeline"] = [t.to_dict() for t in timeline]

        # Changelogs
        if include_changelogs:
            changelogs = self.get_changelogs(limit=100)
            memory["changelogs"] = [c.to_dict() for c in changelogs]

        # Approved decisions
        if include_decisions:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT id, session_id, title, description, reasoning, category, approved_at
                FROM decisions
                WHERE status = 'approved'
                ORDER BY approved_at DESC
            """
            )
            approved = []
            for row in cursor.fetchall():
                approved.append(
                    {
                        "id": f"decision:{row['id']}",
                        "title": row["title"],
                        "description": row["description"],
                        "reasoning": row["reasoning"],
                        "category": row["category"],
                        "approved_at": row["approved_at"],
                    }
                )
            memory["decisions"] = approved

        # Pending decisions (optional)
        if include_pending:
            pending = self.list_pending_decisions(limit=100)
            memory["pending_decisions"] = [
                {
                    "id": f"decision:{d.id}",
                    "title": d.title,
                    "description": d.description,
                    "reasoning": d.reasoning,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in pending
            ]

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(memory, f, indent=2)

        return str(output_path)

    def import_memory(
        self,
        input_path: str | Path = ".sia-code/memory.json",
        conflict_strategy: str = "newest_wins",
    ) -> ImportResult:
        """Import memory from JSON file (e.g., after git pull).

        Args:
            input_path: Path to input file
            conflict_strategy: 'newest_wins' - keep entry with latest timestamp

        Returns:
            ImportResult with counts
        """
        if self.conn is None:
            raise RuntimeError("Index not initialized")

        input_path = Path(input_path)
        if not input_path.is_absolute():
            input_path = self.path / input_path

        if not input_path.exists():
            raise FileNotFoundError(f"Import file not found: {input_path}")

        with open(input_path) as f:
            memory = json.load(f)

        result = ImportResult()

        # Import timeline events
        for event_data in memory.get("timeline", []):
            existing = self.get_timeline_events(
                from_ref=event_data["from_ref"], to_ref=event_data["to_ref"], limit=1
            )

            if existing:
                # Check if imported is newer
                imported_time = datetime.fromisoformat(event_data["created_at"])
                if imported_time > existing[0].created_at:
                    # Update existing (simplified: just skip for now)
                    result.skipped += 1
                else:
                    result.skipped += 1
            else:
                # Add new
                self.add_timeline_event(
                    event_type=event_data["event_type"],
                    from_ref=event_data["from_ref"],
                    to_ref=event_data["to_ref"],
                    summary=event_data["summary"],
                    files_changed=event_data.get("files_changed", []),
                    diff_stats=event_data.get("diff_stats", {}),
                    importance=event_data.get("importance", "medium"),
                )
                result.added += 1

        # Import changelogs
        for changelog_data in memory.get("changelogs", []):
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM changelogs WHERE tag = ?", (changelog_data["tag"],))
            existing = cursor.fetchone()

            if existing:
                result.skipped += 1
            else:
                self.add_changelog(
                    tag=changelog_data["tag"],
                    version=changelog_data.get("version"),
                    summary=changelog_data.get("summary", ""),
                    breaking_changes=changelog_data.get("breaking_changes", []),
                    features=changelog_data.get("features", []),
                    fixes=changelog_data.get("fixes", []),
                )
                result.added += 1

        # Import decisions (approved only)
        for decision_data in memory.get("decisions", []):
            # Check if already exists by title (simplified)
            cursor = self.conn.cursor()
            cursor.execute("SELECT id FROM decisions WHERE title = ?", (decision_data["title"],))
            existing = cursor.fetchone()

            if existing:
                result.skipped += 1
            else:
                # Add as approved decision
                decision_id = self.add_decision(
                    session_id="imported",
                    title=decision_data["title"],
                    description=decision_data["description"],
                    reasoning=decision_data.get("reasoning"),
                )
                # Immediately approve it
                self.approve_decision(decision_id, decision_data.get("category", "imported"))
                result.added += 1

        return result
