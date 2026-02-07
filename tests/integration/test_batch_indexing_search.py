"""Integration test for batched indexing and lexical search."""


from sia_code.config import Config
from sia_code.indexer.coordinator import IndexingCoordinator
from sia_code.storage.usearch_backend import UsearchSqliteBackend


def test_batched_indexing_enables_search(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    source = repo / "math_utils.py"
    source.write_text(
        "\n".join(
            [
                "def add(a, b):",
                "    return a + b",
                "",
                "def multiply(a, b):",
                "    return a * b",
                "",
            ]
        )
    )

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

    coordinator = IndexingCoordinator(config, backend)
    stats = coordinator.index_directory(repo)

    assert stats["total_chunks"] > 0

    results = backend.search_lexical("multiply", k=1)
    assert results
    assert results[0].chunk.file_path.name == "math_utils.py"

    backend.close()
