"""Unit tests for backend batching behavior."""

import numpy as np
from pathlib import Path

from sia_code.core.models import Chunk
from sia_code.core.types import ChunkType, Language
from sia_code.storage.usearch_backend import UsearchSqliteBackend


class DummyEmbedder:
    """Simple embedder that records encode calls."""

    def __init__(self, ndim: int = 4):
        self.ndim = ndim
        self.calls = []

    def encode(self, texts, batch_size=None, show_progress_bar=False, convert_to_numpy=True, **_):
        self.calls.append(texts)
        if isinstance(texts, list):
            vectors = [self._encode_text(text) for text in texts]
            return np.array(vectors, dtype=np.float32)
        return np.array(self._encode_text(texts), dtype=np.float32)

    def _encode_text(self, text: str):
        base = float(sum(ord(ch) for ch in text) % 10)
        return [base + i for i in range(self.ndim)]


def _make_chunks():
    return [
        Chunk(
            symbol="alpha",
            start_line=1,
            end_line=2,
            code="def alpha():\n    return 1",
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=Path("alpha.py"),
        ),
        Chunk(
            symbol="beta",
            start_line=1,
            end_line=2,
            code="def beta():\n    return 2",
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=Path("beta.py"),
        ),
    ]


def test_store_chunks_uses_batch_embedding(tmp_path):
    backend = UsearchSqliteBackend(
        path=tmp_path / ".sia-code",
        embedding_enabled=True,
        embedding_model="dummy",
        ndim=4,
        dtype="f32",
    )
    backend.create_index()

    dummy = DummyEmbedder(ndim=4)
    backend._embedder = dummy
    backend._get_embedder = lambda: dummy

    backend.store_chunks_batch(_make_chunks())

    assert len(dummy.calls) == 1
    assert isinstance(dummy.calls[0], list)
    assert len(dummy.calls[0]) == 2

    backend.close()


def test_store_chunks_respects_embed_batch_size(tmp_path):
    backend = UsearchSqliteBackend(
        path=tmp_path / ".sia-code",
        embedding_enabled=True,
        embedding_model="dummy",
        ndim=4,
        dtype="f32",
    )
    dummy = DummyEmbedder(ndim=4)
    backend._embedder = dummy
    backend._get_embedder = lambda: dummy
    backend._get_embed_batch_size = lambda: 1

    texts = [f"{chunk.symbol}\n\n{chunk.code}" for chunk in _make_chunks()]
    backend._embed_batch(texts)

    assert len(dummy.calls) == 2
    assert all(isinstance(call, list) for call in dummy.calls)
    assert all(len(call) == 1 for call in dummy.calls)


def test_search_lexical_avoids_get_chunk(tmp_path, monkeypatch):
    backend = UsearchSqliteBackend(
        path=tmp_path / ".sia-code",
        embedding_enabled=False,
        ndim=4,
        dtype="f32",
    )
    backend.create_index()
    backend.store_chunks_batch(_make_chunks())

    monkeypatch.setattr(backend, "get_chunk", lambda *_: (_ for _ in ()).throw(AssertionError))

    results = backend.search_lexical("alpha", k=1)
    assert results
    assert results[0].chunk.symbol == "alpha"

    backend.close()


def test_search_semantic_avoids_get_chunk(tmp_path, monkeypatch):
    backend = UsearchSqliteBackend(
        path=tmp_path / ".sia-code",
        embedding_enabled=True,
        embedding_model="dummy",
        ndim=4,
        dtype="f32",
    )
    backend.create_index()

    dummy = DummyEmbedder(ndim=4)
    backend._embedder = dummy
    backend._get_embedder = lambda: dummy

    backend.store_chunks_batch(_make_chunks())

    monkeypatch.setattr(backend, "get_chunk", lambda *_: (_ for _ in ()).throw(AssertionError))

    results = backend.search_semantic("alpha", k=1)
    assert results
    assert results[0].chunk.symbol == "alpha"

    backend.close()
