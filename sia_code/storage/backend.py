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
        result = self.mem.put(
            title=chunk.symbol,
            label=chunk.chunk_type.value,
            metadata={
                "file_path": str(chunk.file_path),
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "language": chunk.language.value,
                "parent_header": chunk.parent_header,
            },
            text=chunk.code,
            uri=f"pci://{chunk.file_path}#{chunk.start_line}",
            enable_embedding=self.embedding_enabled,
            embedding_model=self.embedding_model,
        )
        return ChunkId(str(result.get("frame_id", "")))

    def store_chunks_batch(self, chunks: list[Chunk]) -> list[ChunkId]:
        """Store multiple chunks in a batch.

        Args:
            chunks: List of chunks to store

        Returns:
            List of chunk IDs
        """
        docs = []
        for chunk in chunks:
            docs.append(
                {
                    "title": chunk.symbol,
                    "label": chunk.chunk_type.value,
                    "metadata": {
                        "file_path": str(chunk.file_path),
                        "start_line": chunk.start_line,
                        "end_line": chunk.end_line,
                        "language": chunk.language.value,
                        "parent_header": chunk.parent_header,
                    },
                    "text": chunk.code,
                    "uri": f"pci://{chunk.file_path}#{chunk.start_line}",
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

    def search_semantic(self, query: str, k: int = 10) -> list[SearchResult]:
        """Perform semantic search.

        Args:
            query: Search query
            k: Number of results

        Returns:
            List of search results (filtered if valid_chunks is set)
        """
        # Fetch more results if filtering is enabled
        fetch_k = k * 2 if self.valid_chunks else k

        try:
            results = self.mem.find(query, mode="sem", k=fetch_k, snippet_chars=200)
            return self._convert_and_filter_results(results, k)
        except Exception as e:
            # Fall back to lexical search if semantic fails (e.g., embeddings disabled)
            if "VecIndexDisabledError" in str(type(e)) or "not enabled" in str(e):
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    "Semantic search failed (vector index disabled). "
                    "Falling back to lexical search. "
                    "Set OPENAI_API_KEY or use --regex for lexical search."
                )
                return self.search_lexical(query, k)
            # Re-raise other exceptions
            raise

    def search_lexical(self, query: str, k: int = 10) -> list[SearchResult]:
        """Perform lexical (BM25) search.

        Args:
            query: Search query
            k: Number of results

        Returns:
            List of search results (filtered if valid_chunks is set)
        """
        # Fetch more results if filtering is enabled
        fetch_k = k * 2 if self.valid_chunks else k
        results = self.mem.find(query, mode="lex", k=fetch_k, snippet_chars=200)
        return self._convert_and_filter_results(results, k)

    def search_hybrid(self, query: str, k: int = 10) -> list[SearchResult]:
        """Perform hybrid search (semantic + lexical).

        Args:
            query: Search query
            k: Number of results

        Returns:
            List of search results (filtered if valid_chunks is set)
        """
        # Fetch more results if filtering is enabled
        fetch_k = k * 2 if self.valid_chunks else k

        try:
            results = self.mem.find(query, mode="auto", k=fetch_k, snippet_chars=200)
            return self._convert_and_filter_results(results, k)
        except Exception as e:
            # Fall back to lexical search if hybrid fails (e.g., embeddings disabled)
            if "VecIndexDisabledError" in str(type(e)) or "not enabled" in str(e):
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    "Hybrid search failed (vector index disabled). Falling back to lexical search."
                )
                return self.search_lexical(query, k)
            # Re-raise other exceptions
            raise

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
            uri: URI in format pci:///absolute/path/to/file.py#line

        Returns:
            Tuple of (file_path, start_line, end_line)
        """
        if not uri or not uri.startswith("pci://"):
            return "unknown", 1, 1

        # Remove 'pci://' prefix
        path_part = uri[6:]

        # Extract file path and line number
        if "#" in path_part:
            file_path, line_str = path_part.rsplit("#", 1)
            try:
                line = int(line_str)
                return file_path, line, line
            except ValueError:
                return file_path, 1, 1

        return path_part, 1, 1

    def _convert_results(self, results: dict[str, Any]) -> list[SearchResult]:
        """Convert Memvid results to SearchResult objects."""
        import json

        search_results = []
        for hit in results.get("hits", []):
            # Extract file path and line from URI (fast, no extra queries)
            uri = hit.get("uri", "")
            file_path, start_line, end_line = self._parse_uri(uri)

            # Get code text
            code = hit.get("text", "") or hit.get("snippet", "") or "# No content"

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
