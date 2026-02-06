"""Tests for sqlite-vec backend (FTS5 + sqlite-vec)."""

import numpy as np
import pytest

from sia_code.core.models import Chunk
from sia_code.core.types import ChunkType, FilePath, Language, LineNumber
from sia_code.storage.sqlite_vec_backend import SqliteVecBackend


@pytest.fixture
def backend(tmp_path):
    """Create a temporary backend for testing."""
    test_path = tmp_path / "test_index.sia-code"
    backend = SqliteVecBackend(test_path, embedding_enabled=False, ndim=3)
    backend.create_index()
    yield backend
    backend.close()


def _make_chunks():
    return [
        Chunk(
            symbol="alpha_func",
            start_line=LineNumber(1),
            end_line=LineNumber(3),
            code="def alpha():\n    return 1",
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("alpha.py"),
        ),
        Chunk(
            symbol="beta_func",
            start_line=LineNumber(5),
            end_line=LineNumber(7),
            code="def beta():\n    return 2",
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("beta.py"),
        ),
    ]


def test_create_index(backend):
    assert backend.conn is not None


def test_store_and_search_lexical(backend):
    chunk_ids = backend.store_chunks_batch(_make_chunks())
    assert len(chunk_ids) == 2

    results = backend.search_lexical("alpha", k=1)
    assert results
    assert results[0].chunk.symbol == "alpha_func"


def test_semantic_search_fallback(tmp_path, monkeypatch):
    """Validate fallback vector search works without sqlite-vec."""

    class DummyEmbedder:
        def encode(self, texts, **kwargs):
            def _vec(text):
                return np.array([1.0, 0.0, 0.0], dtype=np.float32) if "alpha" in text else np.array(
                    [0.0, 1.0, 0.0], dtype=np.float32
                )

            if isinstance(texts, list):
                return np.vstack([_vec(text) for text in texts])
            return _vec(texts)

    backend = SqliteVecBackend(tmp_path / "vec_index.sia-code", embedding_enabled=True, ndim=3)
    monkeypatch.setattr(backend, "_load_vec_extension", lambda *_: False)
    backend.create_index()
    backend._get_embedder = lambda: DummyEmbedder()
    backend._get_embed_batch_size = lambda: 1

    backend.store_chunks_batch(_make_chunks())
    results = backend.search_semantic("alpha", k=1)

    assert results
    assert results[0].chunk.symbol == "alpha_func"
    backend.close()
