"""Memvid storage backend for PCI."""

import os
from pathlib import Path
from typing import Any, Set

from memvid_sdk import create, use

from ..core.models import Chunk, SearchResult
from ..core.types import ChunkId, ChunkType, Language, FilePath, LineNumber


class MemvidBackend:
    """Storage backend using Memvid."""

    def __init__(
        self,
        path: Path,
        valid_chunks: Set[str] | None = None,
        embedding_enabled: bool = True,
        embedding_model: str = "openai-small",
        api_key_env: str = "OPENAI_API_KEY",
    ):
        """Initialize Memvid backend.

        Args:
            path: Path to .mv2 file
            valid_chunks: Optional set of valid chunk IDs for filtering stale chunks
            embedding_enabled: Whether to enable embeddings
            embedding_model: Embedding model to use (openai-small, openai-large, bge-small)
            api_key_env: Environment variable containing API key
        """
        self.path = path
        self.mem = None
        self.valid_chunks = valid_chunks  # For query-time filtering
        self.embedding_enabled = embedding_enabled
        self.embedding_model = embedding_model
        self.api_key_env = api_key_env
        self._embedder = None  # Lazy-loaded embedder for batch processing

        # Check if API key is available when OpenAI models are used
        if embedding_enabled and "openai" in embedding_model.lower():
            api_key = os.getenv(api_key_env)
            if not api_key:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Embedding enabled but {api_key_env} not found. "
                    "Embeddings will be disabled for this session."
                )
                self.embedding_enabled = False

    def create_index(self) -> None:
        """Create new index with vector and lexical search enabled."""
        self.mem = create(
            str(self.path),
            enable_vec=self.embedding_enabled,
            enable_lex=True,
        )

    def open_index(self) -> None:
        """Open existing index."""
        self.mem = use("basic", str(self.path), mode="open", enable_vec=self.embedding_enabled)

    def _get_embedder(self):
        """Get or create embedder instance for batch processing.

        Returns:
            EmbeddingProvider instance or None if embeddings are disabled.
        """
        if not self.embedding_enabled:
            return None

        if self._embedder is not None:
            return self._embedder

        # Lazy import to avoid dependency if not using embeddings
        from memvid_sdk.embeddings import OpenAIEmbeddings

        api_key = os.getenv(self.api_key_env)
        if not api_key:
            return None

        # Map our model names to OpenAI SDK model names
        model_map = {
            "openai-small": "text-embedding-3-small",
            "openai-large": "text-embedding-3-large",
        }

        openai_model = model_map.get(self.embedding_model, "text-embedding-3-small")

        try:
            self._embedder = OpenAIEmbeddings(api_key=api_key, model=openai_model)
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to create embedder: {e}")
            return None

        return self._embedder

    def store_chunk(self, chunk: Chunk) -> ChunkId:
        """Store a code chunk in Memvid.

        Args:
            chunk: Code chunk to store

        Returns:
            Chunk ID from Memvid
        """
        # Build metadata including chunk's custom metadata
        metadata = {
            "file_path": str(chunk.file_path),
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "language": chunk.language.value,
            "parent_header": chunk.parent_header,
            **chunk.metadata,  # Include tier and other custom metadata
        }

        result = self.mem.put(
            title=chunk.symbol,
            label=chunk.chunk_type.value,
            metadata=metadata,
            text=chunk.code,
            uri=f"pci://{chunk.file_path}#{chunk.start_line}",
            enable_embedding=self.embedding_enabled,
            embedding_model=self.embedding_model,
        )
        # Memvid returns frame_id directly or in a dict
        if isinstance(result, dict):
            return ChunkId(str(result.get("frame_id", "")))
        else:
            return ChunkId(str(result))

    def store_chunks_batch(self, chunks: list[Chunk]) -> list[ChunkId]:
        """Store multiple chunks in a batch.

        Args:
            chunks: List of chunks to store

        Returns:
            List of chunk IDs
        """
        docs = []
        for chunk in chunks:
            # Build metadata including chunk's custom metadata
            metadata = {
                "file_path": str(chunk.file_path),
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "language": chunk.language.value,
                "parent_header": chunk.parent_header,
                **chunk.metadata,  # Include tier and other custom metadata
            }

            docs.append(
                {
                    "title": chunk.symbol,
                    "label": chunk.chunk_type.value,
                    "metadata": metadata,
                    "text": chunk.code,
                    "uri": f"pci://{chunk.file_path}#{chunk.start_line}-{chunk.end_line}",
                }
            )

        # Use embedder parameter for batch processing (10-15x faster than opts)
        embedder = self._get_embedder()

        if embedder:
            # Batch embedding mode - much faster
            frame_ids = self.mem.put_many(docs, embedder=embedder)
        else:
            # No embeddings or embedder unavailable - use opts fallback
            frame_ids = self.mem.put_many(
                docs,
                opts={
                    "enable_embedding": False,
                    "embedding_model": self.embedding_model,
                },
            )
        return [ChunkId(str(fid)) for fid in frame_ids]

    def _search_with_tier_boost(
        self,
        query: str,
        mode: str,
        k: int = 10,
        include_deps: bool = True,
        tier_boost: dict[str, float] | None = None,
    ) -> list[SearchResult]:
        """Unified search implementation with tier-aware ranking.

        Args:
            query: Search query
            mode: Search mode - "sem" (semantic), "lex" (lexical), or "auto" (hybrid)
            k: Number of results
            include_deps: Whether to include dependency tier
            tier_boost: Score multipliers per tier

        Returns:
            List of search results (filtered and boosted by tier)
        """
        # Default boost values
        if tier_boost is None:
            tier_boost = {"project": 1.0, "dependency": 0.7, "stdlib": 0.5}

        # Fetch more to account for filtering/reranking
        fetch_k = k * 3 if include_deps else k * 2
        if self.valid_chunks:
            fetch_k = max(fetch_k, k * 2)

        # Perform search with fallback for semantic/hybrid modes
        try:
            results = self.mem.find(query, mode=mode, k=fetch_k, snippet_chars=200)
            converted = self._convert_and_filter_results(results, fetch_k)
        except Exception as e:
            # Fall back to lexical search if vector search fails
            if mode != "lex" and (
                "VecIndexDisabledError" in str(type(e)) or "not enabled" in str(e)
            ):
                import logging

                logger = logging.getLogger(__name__)
                mode_name = "Semantic" if mode == "sem" else "Hybrid"
                logger.warning(
                    f"{mode_name} search failed (vector index disabled). "
                    "Falling back to lexical search. "
                    "Set OPENAI_API_KEY or use --regex for lexical search."
                )
                return self._search_with_tier_boost(query, "lex", k, include_deps, tier_boost)
            # Re-raise other exceptions
            raise

        # Apply tier boosting with migration handling
        for result in converted:
            tier = result.chunk.metadata.get("tier", "project")
            result.score *= tier_boost.get(tier, 1.0)

        # Filter by tier if needed
        if not include_deps:
            converted = [
                r for r in converted if r.chunk.metadata.get("tier", "project") == "project"
            ]

        # Re-sort by boosted score
        converted.sort(key=lambda r: r.score, reverse=True)

        return converted[:k]

    def search_semantic(
        self,
        query: str,
        k: int = 10,
        include_deps: bool = True,
        tier_boost: dict[str, float] | None = None,
    ) -> list[SearchResult]:
        """Perform semantic search with tier-aware ranking.

        Args:
            query: Search query
            k: Number of results
            include_deps: Whether to include dependency tier (default True)
            tier_boost: Score multipliers per tier (default: project=1.0, dep=0.7, stdlib=0.5)

        Returns:
            List of search results (filtered and boosted by tier)
        """
        return self._search_with_tier_boost(query, "sem", k, include_deps, tier_boost)

    def search_lexical(
        self,
        query: str,
        k: int = 10,
        include_deps: bool = True,
        tier_boost: dict[str, float] | None = None,
    ) -> list[SearchResult]:
        """Perform lexical (BM25) search with tier-aware ranking.

        Args:
            query: Search query
            k: Number of results
            include_deps: Whether to include dependency tier
            tier_boost: Score multipliers per tier

        Returns:
            List of search results (filtered and boosted by tier)
        """
        return self._search_with_tier_boost(query, "lex", k, include_deps, tier_boost)

    def search_hybrid(
        self,
        query: str,
        k: int = 10,
        include_deps: bool = True,
        tier_boost: dict[str, float] | None = None,
    ) -> list[SearchResult]:
        """Perform hybrid search (semantic + lexical) with tier-aware ranking.

        Args:
            query: Search query
            k: Number of results
            include_deps: Whether to include dependency tier
            tier_boost: Score multipliers per tier

        Returns:
            List of search results (filtered and boosted by tier)
        """
        return self._search_with_tier_boost(query, "auto", k, include_deps, tier_boost)

    def _convert_and_filter_results(
        self, results: dict[str, Any], target_k: int
    ) -> list[SearchResult]:
        """Convert Memvid results and filter out stale chunks.

        Args:
            results: Raw results from Memvid
            target_k: Target number of results after filtering

        Returns:
            Filtered search results
        """
        all_results = self._convert_results(results)

        # If no filtering, return as-is
        if not self.valid_chunks:
            return all_results[:target_k]

        # Filter to only valid chunks
        filtered = [r for r in all_results if str(r.chunk.id) in self.valid_chunks]

        return filtered[:target_k]

    def _parse_uri(self, uri: str) -> tuple[str, int, int]:
        """Extract file path and line numbers from pci:// URI.

        Args:
            uri: URI in format pci:///absolute/path/to/file.py#start_line-end_line

        Returns:
            Tuple of (file_path, start_line, end_line)
        """
        if not uri or not uri.startswith("pci://"):
            return "unknown", 1, 1

        # Remove 'pci://' prefix
        path_part = uri[6:]

        # Extract file path and line numbers
        if "#" in path_part:
            file_path, line_str = path_part.rsplit("#", 1)
            try:
                # Check if line_str contains a range (start-end)
                if "-" in line_str:
                    start_str, end_str = line_str.split("-", 1)
                    start_line = int(start_str)
                    end_line = int(end_str)
                    return file_path, start_line, end_line
                else:
                    # Single line number (legacy format)
                    line = int(line_str)
                    return file_path, line, line
            except ValueError:
                return file_path, 1, 1

        return path_part, 1, 1

    def _convert_results(self, results: dict[str, Any]) -> list[SearchResult]:
        """Convert Memvid results to SearchResult objects."""
        search_results = []

        # Cache file contents to avoid repeated reads
        file_cache: dict[str, list[str]] = {}

        for hit in results.get("hits", []):
            # Extract file path and line from URI (fast, no extra queries)
            uri = hit.get("uri", "")
            file_path, start_line, end_line = self._parse_uri(uri)

            # Get code text
            # Semantic search doesn't populate snippets in Memvid, so we reconstruct from file
            code = hit.get("snippet", "")  # Try snippet first (works for lexical search)

            if not code:
                # Reconstruct from source file using line numbers (with caching)
                try:
                    if file_path and file_path != "unknown":
                        from pathlib import Path

                        # Check cache first
                        if file_path not in file_cache:
                            source_path = Path(file_path)
                            if source_path.exists():
                                with open(source_path, "r", encoding="utf-8", errors="ignore") as f:
                                    file_cache[file_path] = f.readlines()

                        # Get from cache
                        if file_path in file_cache:
                            lines = file_cache[file_path]
                            # Line numbers are 1-based, array is 0-based
                            if start_line > 0 and end_line > 0:
                                code_lines = lines[start_line - 1 : end_line]
                                code = "".join(code_lines).rstrip()
                except Exception:
                    pass

            if not code:
                code = "# No content"

            # Parse chunk type from title (since labels are always empty)
            # The title contains the actual chunk type in many cases
            chunk_type_str = hit.get("label", "unknown")
            if chunk_type_str == "unknown" or not chunk_type_str:
                # Try to infer from title
                title = hit.get("title", "")
                if title == "comment":
                    chunk_type = ChunkType.COMMENT
                else:
                    chunk_type = ChunkType.UNKNOWN
            else:
                try:
                    chunk_type = ChunkType(chunk_type_str)
                except ValueError:
                    chunk_type = ChunkType.UNKNOWN

            # For language, we can optionally call frame() if needed
            # For now, try to infer from file extension
            language = Language.UNKNOWN
            if file_path != "unknown":
                try:
                    from pathlib import Path

                    language = Language.from_extension(Path(file_path).suffix)
                except (ValueError, AttributeError):
                    language = Language.UNKNOWN

            # Extract metadata (includes tier, package info, etc.)
            # Memvid's find() doesn't return metadata, need to fetch frame by URI
            metadata = {}
            if uri:
                try:
                    frame_data = self.mem.frame(uri)
                    if frame_data and isinstance(frame_data.get("extra_metadata"), dict):
                        # Memvid stores metadata in extra_metadata with JSON-encoded values
                        import json as json_lib

                        extra_meta = frame_data["extra_metadata"]
                        for key, value in extra_meta.items():
                            # Skip internal keys
                            if key in (
                                "file_path",
                                "start_line",
                                "end_line",
                                "language",
                                "parent_header",
                                "extractous_metadata",
                            ):
                                continue
                            # Parse JSON-encoded values
                            if isinstance(value, str):
                                try:
                                    metadata[key] = json_lib.loads(value)
                                except (json_lib.JSONDecodeError, ValueError):
                                    metadata[key] = value
                            else:
                                metadata[key] = value
                except Exception:
                    # If fetching frame fails, continue without metadata
                    pass

            chunk = Chunk(
                symbol=hit.get("title", "unknown"),
                start_line=LineNumber(start_line),
                end_line=LineNumber(end_line),
                code=code,
                chunk_type=chunk_type,
                language=language,
                file_path=FilePath(file_path),
                parent_header=None,  # Not available without frame() call
                id=ChunkId(str(hit.get("frame_id", ""))),
                metadata=metadata,
            )
            search_results.append(
                SearchResult(
                    chunk=chunk,
                    score=hit.get("score", 0.0),
                    snippet=hit.get("snippet"),
                )
            )
        return search_results

    def delete_chunks(self, chunk_ids: list[ChunkId]) -> int:
        """Delete chunks by their IDs.

        Args:
            chunk_ids: List of chunk IDs to delete

        Returns:
            Number of chunks deleted
        """
        # Note: Memvid doesn't have direct delete API
        # In production, would need to track deletions and rebuild index
        # For now, this is a placeholder
        return 0

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        # Memvid doesn't expose stats directly, return placeholder
        return {
            "path": str(self.path),
            "exists": self.path.exists(),
        }

    def close(self) -> None:
        """Close the index."""
        if self.mem:
            self.mem = None
