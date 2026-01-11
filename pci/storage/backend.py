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
        self.mem = use("basic", str(self.path), mode="open")

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

        # Use configured embedding settings
        frame_ids = self.mem.put_many(
            docs,
            opts={
                "enable_embedding": self.embedding_enabled,
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
        results = self.mem.find(query, mode="sem", k=fetch_k, snippet_chars=200)
        return self._convert_and_filter_results(results, k)

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
        results = self.mem.find(query, mode="auto", k=fetch_k, snippet_chars=200)
        return self._convert_and_filter_results(results, k)

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

    def _convert_results(self, results: dict[str, Any]) -> list[SearchResult]:
        """Convert Memvid results to SearchResult objects."""
        search_results = []
        for hit in results.get("hits", []):
            metadata = hit.get("metadata", {})

            # Get code text
            code = hit.get("text", "")
            if not code:
                # Fallback to snippet if text is empty
                code = hit.get("snippet", "# No content")

            # Parse chunk type
            chunk_type_str = hit.get("label", "unknown")
            try:
                chunk_type = ChunkType(chunk_type_str)
            except ValueError:
                chunk_type = ChunkType.UNKNOWN

            # Parse language
            language_str = metadata.get("language", "unknown")
            try:
                language = Language(language_str)
            except ValueError:
                language = Language.UNKNOWN

            chunk = Chunk(
                symbol=hit.get("title", "unknown"),
                start_line=LineNumber(metadata.get("start_line", 1)),
                end_line=LineNumber(metadata.get("end_line", 1)),
                code=code,
                chunk_type=chunk_type,
                language=language,
                file_path=FilePath(metadata.get("file_path", "unknown")),
                parent_header=metadata.get("parent_header"),
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
