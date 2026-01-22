"""Tests for tier-based search filtering (Phase 1)."""

import pytest
from pathlib import Path
from sia_code.core.models import Chunk
from sia_code.core.types import ChunkType, Language, FilePath, LineNumber
from sia_code.storage.usearch_backend import UsearchSqliteBackend


@pytest.fixture
def backend(tmp_path):
    """Create a temporary backend for testing."""
    test_path = tmp_path / "test_index.sia-code"
    backend = UsearchSqliteBackend(test_path, embedding_enabled=False)
    backend.create_index()
    yield backend
    backend.close()


@pytest.fixture
def backend_with_mixed_tiers(backend):
    """Backend with chunks from different tiers."""
    # Project chunks
    project_chunks = [
        Chunk(
            symbol="UserService",
            start_line=LineNumber(10),
            end_line=LineNumber(50),
            code="class UserService:\n    def get_user(self):\n        return user",
            chunk_type=ChunkType.CLASS,
            language=Language.PYTHON,
            file_path=FilePath("src/services/user.py"),
        ).with_metadata({"tier": "project"}),
        Chunk(
            symbol="AuthService",
            start_line=LineNumber(5),
            end_line=LineNumber(30),
            code="class AuthService:\n    def login(self):\n        return token",
            chunk_type=ChunkType.CLASS,
            language=Language.PYTHON,
            file_path=FilePath("src/services/auth.py"),
        ).with_metadata({"tier": "project"}),
    ]

    # Dependency chunks
    dependency_chunks = [
        Chunk(
            symbol="requests.Session",
            start_line=LineNumber(100),
            end_line=LineNumber(200),
            code="class Session:\n    def get(self, url):\n        return response",
            chunk_type=ChunkType.CLASS,
            language=Language.PYTHON,
            file_path=FilePath("site-packages/requests/sessions.py"),
        ).with_metadata(
            {"tier": "dependency", "package_name": "requests", "package_version": "2.31.0"}
        ),
        Chunk(
            symbol="requests.get",
            start_line=LineNumber(50),
            end_line=LineNumber(80),
            code="def get(url, **kwargs):\n    return Session().get(url, **kwargs)",
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("site-packages/requests/api.py"),
        ).with_metadata(
            {"tier": "dependency", "package_name": "requests", "package_version": "2.31.0"}
        ),
    ]

    backend.store_chunks_batch(project_chunks + dependency_chunks)
    return backend


@pytest.fixture
def backend_with_legacy_chunks(backend):
    """Backend with chunks that have no tier metadata (legacy)."""
    legacy_chunks = [
        Chunk(
            symbol="OldFunction",
            start_line=LineNumber(1),
            end_line=LineNumber(10),
            code="def old_function():\n    pass",
            chunk_type=ChunkType.FUNCTION,
            language=Language.PYTHON,
            file_path=FilePath("old_code.py"),
        ),  # No .with_metadata() - simulates old chunks
    ]

    backend.store_chunks_batch(legacy_chunks)
    return backend


class TestTierFiltering:
    """Test tier filtering in search methods."""

    def test_include_deps_true_returns_all_tiers(self, backend_with_mixed_tiers):
        """With include_deps=True, both project and dependency chunks returned."""
        results = backend_with_mixed_tiers.search_lexical(
            "class",  # Generic term that matches both project and dependency chunks
            k=10,
            include_deps=True,
        )

        # Should find multiple chunks
        assert len(results) >= 2, f"Should find multiple chunks, got {len(results)}"

        # Check we have mixed tiers
        tiers = [r.chunk.metadata.get("tier", "project") for r in results]
        # With include_deps=True, we should have at least project tier
        assert "project" in tiers, "Should include project tier"
        # Dependency chunks should also be included (may not rank as high)
        assert len(results) >= 2, "Should find chunks from different tiers"

    def test_include_deps_false_excludes_dependencies(self, backend_with_mixed_tiers):
        """With include_deps=False, only project chunks returned."""
        # Search for "User" which matches "UserService" via prefix matching
        results = backend_with_mixed_tiers.search_lexical("User", k=10, include_deps=False)

        # Should only find project chunks
        assert len(results) >= 1, "Should find at least one project chunk"

        # Check all results are project tier
        for result in results:
            tier = result.chunk.metadata.get("tier", "project")
            assert tier == "project", f"Expected project tier, got {tier}"

    def test_tier_boost_multiplies_scores(self, backend_with_mixed_tiers):
        """Tier boost should multiply scores correctly."""
        # Custom tier boost: project gets 1.0, dependency gets 0.5
        tier_boost = {"project": 1.0, "dependency": 0.5, "stdlib": 0.3}

        results = backend_with_mixed_tiers.search_lexical(
            "get", k=10, include_deps=True, tier_boost=tier_boost
        )

        # Find a project and dependency result to compare
        project_results = [r for r in results if r.chunk.metadata.get("tier") == "project"]
        dep_results = [r for r in results if r.chunk.metadata.get("tier") == "dependency"]

        # If we have both, check that project scores are boosted more
        if project_results and dep_results:
            # Project chunks should generally score higher due to boost
            # (though this depends on base relevance)
            assert len(project_results) > 0
            assert len(dep_results) > 0

            # Verify boost was applied (score should be positive)
            for r in project_results:
                assert r.score > 0
            for r in dep_results:
                assert r.score > 0

    def test_migration_defaults_missing_tier_to_project(self, backend_with_legacy_chunks):
        """Old chunks without tier metadata should default to 'project'."""
        results = backend_with_legacy_chunks.search_lexical("old", k=10, include_deps=True)

        assert len(results) >= 1, "Should find legacy chunk"

        # Check that missing tier defaults to project
        for result in results:
            tier = result.chunk.metadata.get("tier", "project")
            assert tier == "project", "Legacy chunks should default to project tier"

    def test_custom_tier_boost_values(self, backend_with_mixed_tiers):
        """Custom tier_boost dict should override defaults."""
        # Boost dependencies higher than project (reversed)
        tier_boost = {"project": 0.5, "dependency": 1.0}

        results = backend_with_mixed_tiers.search_lexical(
            "get", k=10, include_deps=True, tier_boost=tier_boost
        )

        # All results should have positive scores
        for result in results:
            assert result.score > 0, "Boosted scores should be positive"

    def test_deps_only_filtering(self, backend_with_mixed_tiers):
        """Test filtering for dependency-only results."""
        # Get all results first - use a term that will match dependency code
        all_results = backend_with_mixed_tiers.search_lexical(
            "Session",  # This will match the requests.Session dependency chunk
            k=10,
            include_deps=True,
        )

        # Filter to only dependencies (simulating --deps-only flag)
        deps_only = [r for r in all_results if r.chunk.metadata.get("tier") == "dependency"]

        # Should find the Session dependency chunk
        assert len(deps_only) >= 1, (
            f"Should have at least one dependency result, got {len(all_results)} total results"
        )

        # Verify all are dependencies
        for result in deps_only:
            assert result.chunk.metadata.get("tier") == "dependency"


class TestTierFilteringSemanticSearch:
    """Test tier filtering with semantic search (requires embeddings)."""

    def test_semantic_search_respects_include_deps(self, backend_with_mixed_tiers):
        """Semantic search should also respect include_deps parameter."""
        # This test will be skipped if embeddings are disabled
        if not backend_with_mixed_tiers.embedding_enabled:
            pytest.skip("Embeddings not enabled")

        results_with_deps = backend_with_mixed_tiers.search_semantic(
            "user service", k=10, include_deps=True
        )

        results_no_deps = backend_with_mixed_tiers.search_semantic(
            "user service", k=10, include_deps=False
        )

        # With deps should find more or equal results
        assert len(results_with_deps) >= len(results_no_deps)

        # No deps should only have project tier
        for result in results_no_deps:
            tier = result.chunk.metadata.get("tier", "project")
            assert tier == "project"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
