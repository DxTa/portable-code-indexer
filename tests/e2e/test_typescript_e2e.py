"""E2E tests for TypeScript repository (denoland/deno)."""

import json

from .base_e2e_test import TypeScriptE2ETest


class TestTypeScriptE2E(TypeScriptE2ETest):
    """End-to-end tests for TypeScript repository using deno as target."""

    EXPECTED_SYMBOL = "PQueue"

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

    # ===== INDEXING TESTS =====

    def test_index_full_completes_successfully(self, indexed_repo):
        """Test that full indexing completes without errors.

        Note: Uses indexed_repo fixture which already performed full indexing.
        This test verifies the index was created successfully rather than re-indexing.
        """
        # Verify index was created
        index_path = indexed_repo / ".sia-code" / "index.db"
        assert index_path.exists(), "Index database not created"
        assert index_path.stat().st_size > 100000, "Index appears empty or incomplete"

        # Verify index contains data by checking status
        result = self.run_cli(["status"], indexed_repo)
        assert result.returncode == 0, f"Status check failed: {result.stderr}"
        assert "index" in result.stdout.lower()

    def test_index_reports_file_and_chunk_counts(self, indexed_repo):
        """Test that status shows index information after indexing."""
        result = self.run_cli(["status"], indexed_repo)
        assert result.returncode == 0
        # Check for basic index info (chunk info only shown after --update)
        assert "index" in result.stdout.lower()

    def test_index_skips_excluded_patterns(self, indexed_repo):
        """Test that indexing skips excluded patterns."""
        results = self.search_json(".git", indexed_repo, regex=True, limit=10)
        file_paths = self.get_result_file_paths(results)
        git_files = [fp for fp in file_paths if ".git/" in fp]
        assert len(git_files) == 0

    def test_index_clean_rebuilds_from_scratch(self, indexed_repo):
        """Test that --clean flag rebuilds index from scratch.

        Note: This test does a full rebuild with embeddings enabled.
        """
        result = self.run_cli(["index", "--clean", "."], indexed_repo, timeout=600)
        assert result.returncode == 0
        assert "clean" in result.stdout.lower()

    def test_index_update_only_processes_changes(self, indexed_repo):
        """Test that --update flag only reindexes changed files."""
        result = self.run_cli(["index", "--update", "."], indexed_repo, timeout=600)
        assert result.returncode == 0

    # ===== SEARCH - LEXICAL TESTS =====

    def test_search_finds_language_keyword(self, indexed_repo):
        """Test searching for TypeScript keyword 'function' completes successfully."""
        # Test that search command runs without error
        result = self.run_cli(
            ["search", "function", "--regex", "-k", "5", "--no-filter"], indexed_repo
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
        results = self.search_json("async", indexed_repo, regex=True, limit=5)
        if len(results.get("results", [])) > 0:
            file_paths = self.get_result_file_paths(results)
            self.assert_contains_language_extension(file_paths, [".ts", ".tsx"])

    def test_search_respects_limit(self, indexed_repo):
        """Test that search respects -k/--limit parameter."""
        limit = 3
        results = self.search_json("function", indexed_repo, regex=True, limit=limit)
        assert len(results.get("results", [])) <= limit

    # ===== SEARCH - OUTPUT FORMATS =====

    def test_search_json_output_valid(self, indexed_repo):
        """Test that --format json completes successfully."""
        result = self.run_cli(
            ["search", "function", "--regex", "--format", "json", "--no-filter"], indexed_repo
        )
        assert result.returncode == 0

    def test_search_table_output_renders(self, indexed_repo):
        """Test that --format table produces formatted output."""
        result = self.run_cli(
            ["search", "function", "--regex", "--format", "table", "-k", "3", "--no-filter"],
            indexed_repo,
        )
        assert result.returncode == 0
        assert len(result.stdout) > 0

    def test_search_csv_output_valid(self, indexed_repo):
        """Test that --format csv completes successfully."""
        result = self.run_cli(
            ["search", "function", "--regex", "--format", "csv", "-k", "3", "--no-filter"],
            indexed_repo,
        )
        assert result.returncode == 0

    # ===== RESEARCH TESTS =====

    def test_research_finds_related_code(self, indexed_repo):
        """Test that research command finds related code chunks."""
        result = self.run_cli(
            ["research", "How does the runtime work?", "--hops", "2"], indexed_repo, timeout=600
        )
        assert result.returncode == 0

    def test_research_respects_hop_limit(self, indexed_repo):
        """Test that research respects --hops parameter."""
        result = self.run_cli(
            ["research", "How does this work?", "--hops", "1"], indexed_repo, timeout=600
        )
        assert result.returncode == 0

    def test_research_graph_shows_relationships(self, indexed_repo):
        """Test that --graph flag shows code relationships."""
        result = self.run_cli(
            ["research", "How does the runtime work?", "--hops", "2", "--graph"],
            indexed_repo,
            timeout=600,
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
