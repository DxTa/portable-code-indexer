"""Tests for sqlite-vec backend (FTS5 + sqlite-vec)."""

import numpy as np
import pytest
import sqlite3

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
                return (
                    np.array([1.0, 0.0, 0.0], dtype=np.float32)
                    if "alpha" in text
                    else np.array([0.0, 1.0, 0.0], dtype=np.float32)
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


def test_mem_put_uses_uri_when_metadata_missing(tmp_path):
    backend = SqliteVecBackend(tmp_path / "uri_parse.sia-code", embedding_enabled=False, ndim=3)
    captured = []
    backend.store_chunks_batch = lambda chunks: captured.extend(chunks) or []

    backend.mem.put(
        title="from_uri",
        label=ChunkType.FUNCTION.value,
        metadata={},
        text="def from_uri(): pass",
        uri="pci:///tmp/example.py#10-20",
    )

    assert captured
    assert str(captured[0].file_path) == "/tmp/example.py"
    assert captured[0].start_line == 10
    assert captured[0].end_line == 20


def test_store_chunks_batch_keeps_stable_id_on_upsert(tmp_path, monkeypatch):
    backend = SqliteVecBackend(tmp_path / "upsert.sia-code", embedding_enabled=False, ndim=3)

    monkeypatch.setattr("sia_code.storage.sqlite_runtime.get_sqlite_module", lambda: sqlite3)

    def create_tables_without_fts(self):
        cursor = self.conn.cursor()
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
        self.conn.commit()

    monkeypatch.setattr(backend, "_create_tables", create_tables_without_fts.__get__(backend))
    backend.create_index()

    chunk = Chunk(
        symbol="stable",
        start_line=LineNumber(1),
        end_line=LineNumber(2),
        code="def stable():\n    return 1",
        chunk_type=ChunkType.FUNCTION,
        language=Language.PYTHON,
        file_path=FilePath("stable.py"),
    )

    first_id = backend.store_chunks_batch([chunk])[0]
    second_id = backend.store_chunks_batch([chunk])[0]

    assert first_id == second_id
    backend.close()
