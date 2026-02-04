"""Unit tests for indexing chunk buffering."""

import math
from pathlib import Path

from sia_code.config import Config
from sia_code.indexer.coordinator import IndexingCoordinator
from sia_code.storage.usearch_backend import UsearchSqliteBackend


def _write_file(directory: Path, name: str, content: str) -> Path:
    path = directory / name
    path.write_text(content)
    return path


def test_indexing_buffers_chunk_writes(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()

    _write_file(repo, "a.py", "def alpha():\n    return 1\n")
    _write_file(repo, "b.py", "def beta():\n    return 2\n")
    _write_file(repo, "c.py", "def gamma():\n    return 3\n")

    config = Config()
    config.indexing.chunk_batch_size = 2
    config.embedding.enabled = False

    backend = UsearchSqliteBackend(
        path=tmp_path / ".sia-code",
        embedding_enabled=False,
        ndim=4,
        dtype="f32",
    )
    backend.create_index()

    call_count = 0
    original_store = backend.store_chunks_batch

    def wrapped_store(chunks):
        nonlocal call_count
        call_count += 1
        return original_store(chunks)

    monkeypatch.setattr(backend, "store_chunks_batch", wrapped_store)

    coordinator = IndexingCoordinator(config, backend)
    stats = coordinator.index_directory(repo)

    expected_calls = math.ceil(stats["total_chunks"] / config.indexing.chunk_batch_size)
    assert call_count == expected_calls

    backend.close()
