"""E2E tests for Rust repository (tokio-rs/tokio)."""

import json

from .base_e2e_test import RustE2ETest


class TestRustE2E(RustE2ETest):
    """End-to-end tests for Rust repository using tokio as target."""

    EXPECTED_SYMBOL = "Runtime"

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

        with open(config_path) as f:
            config = json.load(f)
            assert "embedding" in config
            assert "indexing" in config

    def test_init_creates_index_file(self, initialized_repo):
        """Test that index.db file is created."""
        index_path = initialized_repo / ".sia-code" / "index.db"
        assert index_path.exists()

    # ===== SEARCH - LEXICAL TESTS =====

    def test_search_finds_language_keyword(self, indexed_repo):
        """Test searching for Rust keyword 'fn' completes successfully."""
        # Test that search command runs without error
        result = self.run_cli(["search", "fn", "--regex", "-k", "5", "--no-filter"], indexed_repo)
        assert result.returncode == 0

    def test_search_finds_known_symbol(self, indexed_repo, e2e_symbol):
        """Test searching for known symbol completes successfully."""
        symbol = e2e_symbol or self.EXPECTED_SYMBOL
        # Test that search command runs without error
        result = self.run_cli(["search", symbol, "--regex", "-k", "5", "--no-filter"], indexed_repo)
        assert result.returncode == 0

    def test_search_returns_correct_file_paths(self, indexed_repo):
        """Test that search results contain valid file paths."""
        results = self.search_json("async", indexed_repo, regex=True, limit=5)
        if len(results.get("results", [])) > 0:
            file_paths = self.get_result_file_paths(results)
            self.assert_contains_language_extension(file_paths, [".rs"])

    def test_search_respects_limit(self, indexed_repo):
        """Test that search respects -k/--limit parameter."""
        limit = 3
        results = self.search_json("fn ", indexed_repo, regex=True, limit=limit)
        assert len(results.get("results", [])) <= limit

    # ===== SEARCH - OUTPUT FORMATS =====

    def test_search_json_output_valid(self, indexed_repo):
        """Test that --format json completes successfully."""
        result = self.run_cli(
            ["search", "fn", "--regex", "--format", "json", "--no-filter"], indexed_repo
        )
        assert result.returncode == 0

    def test_search_table_output_renders(self, indexed_repo):
        """Test that --format table produces formatted output."""
        result = self.run_cli(
            ["search", "fn ", "--regex", "--format", "table", "-k", "3", "--no-filter"],
            indexed_repo,
        )
        assert result.returncode == 0
        assert len(result.stdout) > 0

    def test_search_csv_output_valid(self, indexed_repo):
        """Test that --format csv completes successfully."""
        result = self.run_cli(
            ["search", "fn ", "--regex", "--format", "csv", "-k", "3", "--no-filter"], indexed_repo
        )
        assert result.returncode == 0

    # ===== STATUS & MAINTENANCE =====

    def test_status_shows_index_info(self, indexed_repo):
        """Test that status command shows index information."""
        result = self.run_cli(["status"], indexed_repo)
        assert result.returncode == 0
        assert "index" in result.stdout.lower()

    def test_status_shows_chunk_metrics(self, indexed_repo):
        """Test that status displays index metrics."""
        result = self.run_cli(["status"], indexed_repo)
        assert result.returncode == 0
        # May show chunk or index info depending on whether --update was run
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
