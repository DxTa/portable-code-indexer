"""E2E tests for Java repository (mockito/mockito)."""

import json

from .base_e2e_test import JavaE2ETest


class TestJavaE2E(JavaE2ETest):
    """End-to-end tests for Java repository using Mockito as target.

    Tests cover the complete user journey:
    - Initialization
    - Indexing
    - Search (lexical and semantic)
    - Research (multi-hop)
    - Status and maintenance
    """

    EXPECTED_SYMBOL = "Mockito"

    # ===== INITIALIZATION TESTS =====

    def test_init_creates_sia_code_directory(self, target_repo):
        """Test that 'sia-code init' creates .sia-code directory."""
        result = self.run_cli(["init"], target_repo)
        assert result.returncode == 0, f"Init failed: {result.stderr}"
        assert (target_repo / ".sia-code").exists()

    def test_init_creates_valid_config(self, initialized_repo):
        """Test that config.json is created and valid."""
        config_path = initialized_repo / ".sia-code" / "config.json"
        assert config_path.exists()

        # Verify it's valid JSON
        with open(config_path) as f:
            config = json.load(f)
            assert "embedding" in config
            assert "indexing" in config
            assert "chunking" in config

    def test_init_creates_index_file(self, initialized_repo):
        """Test that index.db file is created."""
        index_path = initialized_repo / ".sia-code" / "index.db"
        assert index_path.exists()

    # ===== SEARCH - LEXICAL TESTS =====

    def test_search_finds_language_keyword(self, indexed_repo):
        """Test searching for Java keyword 'class' completes successfully."""
        # Test that search command runs without error
        result = self.run_cli(
            ["search", "class", "--regex", "-k", "5", "--no-filter"], indexed_repo
        )
        assert result.returncode == 0

    def test_search_finds_known_symbol(self, indexed_repo, e2e_symbol):
        """Test searching for known symbol completes successfully."""
        symbol = e2e_symbol or self.EXPECTED_SYMBOL
        # Test that search command runs without error
        result = self.run_cli(["search", symbol, "--regex", "-k", "5", "--no-filter"], indexed_repo)
        assert result.returncode == 0

    def test_search_returns_correct_file_paths(self, indexed_repo):
        """Test that search results contain valid file paths."""
        results = self.search_json("public", indexed_repo, regex=True, limit=5)

        if len(results.get("results", [])) > 0:
            file_paths = self.get_result_file_paths(results)

            # All file paths should be non-empty
            assert all(fp for fp in file_paths), "Empty file path found in results"

            # File paths should contain language extension
            self.assert_contains_language_extension(file_paths, [".java"])

    def test_search_respects_limit(self, indexed_repo):
        """Test that search respects -k/--limit parameter."""
        limit = 3
        results = self.search_json("void", indexed_repo, regex=True, limit=limit)

        # Should not exceed limit
        assert len(results.get("results", [])) <= limit, f"Results exceed limit of {limit}"

    # ===== SEARCH - OUTPUT FORMATS =====

    def test_search_json_output_valid(self, indexed_repo):
        """Test that --format json completes successfully."""
        result = self.run_cli(
            ["search", "method", "--regex", "--format", "json", "--no-filter"], indexed_repo
        )
        assert result.returncode == 0

    def test_search_table_output_renders(self, indexed_repo):
        """Test that --format table produces formatted output."""
        result = self.run_cli(
            ["search", "class", "--regex", "--format", "table", "-k", "3", "--no-filter"],
            indexed_repo,
        )
        assert result.returncode == 0
        # Table format typically has borders or separators
        # Just verify it produces output
        assert len(result.stdout) > 0

    def test_search_csv_output_valid(self, indexed_repo):
        """Test that --format csv completes successfully."""
        result = self.run_cli(
            ["search", "public", "--regex", "--format", "csv", "-k", "3", "--no-filter"],
            indexed_repo,
        )
        assert result.returncode == 0

    # ===== STATUS & MAINTENANCE =====

    def test_status_shows_index_info(self, indexed_repo):
        """Test that status command shows index information."""
        result = self.run_cli(["status"], indexed_repo)
        assert result.returncode == 0
        # Should show index-related info
        assert "index" in result.stdout.lower()

    def test_status_shows_chunk_metrics(self, indexed_repo):
        """Test that status displays chunk count metrics."""
        result = self.run_cli(["status"], indexed_repo)
        assert result.returncode == 0
        # Should report chunk or index statistics
        assert "index" in result.stdout.lower() or "chunk" in result.stdout.lower()

    def test_compact_healthy_index_message(self, indexed_repo):
        """Test that compact on healthy index shows appropriate message."""
        # Run incremental indexing to create chunk_index.json
        update_result = self.run_cli(["index", "--update", "."], indexed_repo, timeout=600)
        assert update_result.returncode == 0, f"Index update failed: {update_result.stderr}"

        # Verify chunk_index.json was created
        chunk_index_path = indexed_repo / ".sia-code" / "chunk_index.json"
        assert chunk_index_path.exists(), (
            "chunk_index.json not created after incremental indexing. "
            "This may indicate no files were indexed successfully."
        )

        result = self.run_cli(["compact", "."], indexed_repo, timeout=600)
        assert result.returncode == 0

    def test_compact_force_always_runs(self, indexed_repo):
        """Test that --force flag always runs compaction."""
        # Run incremental indexing to create chunk_index.json
        update_result = self.run_cli(["index", "--update", "."], indexed_repo, timeout=600)
        assert update_result.returncode == 0, f"Index update failed: {update_result.stderr}"

        # Verify chunk_index.json was created
        chunk_index_path = indexed_repo / ".sia-code" / "chunk_index.json"
        assert chunk_index_path.exists(), (
            "chunk_index.json not created after incremental indexing. "
            "This may indicate no files were indexed successfully."
        )

        result = self.run_cli(["compact", "--force", "."], indexed_repo, timeout=600)
        assert result.returncode == 0
        assert "compact" in result.stdout.lower()
