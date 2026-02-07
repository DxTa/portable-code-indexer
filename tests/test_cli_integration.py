"""Integration test for Sia Code CLI."""

import pytest
import subprocess
import sys
from pathlib import Path
import os
import shutil


@pytest.fixture
def test_project(tmp_path):
    """Create a temporary project directory for testing."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create some sample Python files
    (project_dir / "main.py").write_text('''
"""Main module for testing."""

def hello_world():
    """Print hello world."""
    print("Hello, World!")

def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

class Calculator:
    """Simple calculator class."""
    
    def multiply(self, a: int, b: int) -> int:
        """Multiply two numbers."""
        return a * b
''')

    (project_dir / "utils.py").write_text('''
"""Utility functions."""

def format_string(s: str) -> str:
    """Format a string."""
    return s.strip().lower()

def validate_input(value: int) -> bool:
    """Validate input is positive."""
    return value > 0
''')

    yield project_dir

    # Cleanup
    if project_dir.exists():
        shutil.rmtree(project_dir)


def run_cli(args: list, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run the CLI with given arguments."""
    env = os.environ.copy()
    repo_root = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = f"{repo_root}:{env.get('PYTHONPATH', '')}"
    return subprocess.run(
        [sys.executable, "-m", "sia_code.cli"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


class TestCLIInit:
    """Test 'sia-code init' command."""

    def test_init_creates_directory(self, test_project):
        """Test init creates .sia-code directory."""
        result = run_cli(["init"], cwd=test_project)

        assert result.returncode == 0
        assert (test_project / ".sia-code").exists()
        assert (test_project / ".sia-code" / "config.json").exists()
        assert (test_project / ".sia-code" / "index.db").exists()

    def test_init_already_initialized(self, test_project):
        """Test init when already initialized."""
        # First init
        run_cli(["init"], cwd=test_project)

        # Second init should warn
        result = run_cli(["init"], cwd=test_project)
        assert "already initialized" in result.stdout.lower()


class TestCLIStatus:
    """Test 'sia-code status' command."""

    def test_status_not_initialized(self, test_project):
        """Test status when not initialized."""
        result = run_cli(["status"], cwd=test_project)

        assert result.returncode != 0
        assert "not initialized" in result.stdout.lower() or "error" in result.stderr.lower()

    def test_status_after_init(self, test_project):
        """Test status after initialization."""
        run_cli(["init"], cwd=test_project)
        result = run_cli(["status"], cwd=test_project)

        assert result.returncode == 0
        assert "index" in result.stdout.lower()


class TestCLIIndex:
    """Test 'sia-code index' command."""

    def test_index_not_initialized(self, test_project):
        """Test index when not initialized."""
        result = run_cli(["index", "."], cwd=test_project)

        assert result.returncode != 0

    def test_index_basic(self, test_project):
        """Test basic indexing."""
        run_cli(["init"], cwd=test_project)
        result = run_cli(["index", "."], cwd=test_project)

        assert result.returncode == 0
        assert "indexing complete" in result.stdout.lower()

    def test_index_clean(self, test_project):
        """Test clean indexing."""
        run_cli(["init"], cwd=test_project)
        run_cli(["index", "."], cwd=test_project)

        result = run_cli(["index", "--clean", "."], cwd=test_project)

        assert result.returncode == 0
        assert "clean" in result.stdout.lower()

    def test_index_clean_removes_legacy_usearch_file(self, test_project):
        """Test clean indexing removes legacy vectors.usearch to allow sqlite-vec migration."""
        run_cli(["init"], cwd=test_project)

        legacy_vectors = test_project / ".sia-code" / "vectors.usearch"
        legacy_vectors.write_text("legacy")

        result = run_cli(["index", "--clean", "."], cwd=test_project)

        assert result.returncode == 0
        assert not legacy_vectors.exists()


class TestCLISearch:
    """Test 'sia-code search' command."""

    def test_search_not_initialized(self, test_project):
        """Test search when not initialized."""
        result = run_cli(["search", "hello"], cwd=test_project)

        assert result.returncode != 0

    def test_search_lexical(self, test_project):
        """Test lexical search."""
        run_cli(["init"], cwd=test_project)
        run_cli(["index", "."], cwd=test_project)

        result = run_cli(["search", "hello", "--regex", "--no-filter"], cwd=test_project)

        assert result.returncode == 0

    def test_search_with_limit(self, test_project):
        """Test search with result limit."""
        run_cli(["init"], cwd=test_project)
        run_cli(["index", "."], cwd=test_project)

        result = run_cli(
            ["search", "def", "--regex", "--no-filter", "--limit", "3"], cwd=test_project
        )

        assert result.returncode == 0

    def test_search_json_format(self, test_project):
        """Test search with JSON output format."""
        run_cli(["init"], cwd=test_project)
        run_cli(["index", "."], cwd=test_project)

        result = run_cli(
            ["search", "class", "--regex", "--no-filter", "--format", "json"], cwd=test_project
        )

        assert result.returncode == 0
        # Should contain JSON structure
        assert "{" in result.stdout or "No results" in result.stdout

    def test_search_table_format(self, test_project):
        """Test search with table output format."""
        run_cli(["init"], cwd=test_project)
        run_cli(["index", "."], cwd=test_project)

        result = run_cli(
            ["search", "multiply", "--regex", "--no-filter", "--format", "table"], cwd=test_project
        )

        assert result.returncode == 0


class TestCLIConfig:
    """Test 'sia-code config' commands."""

    def test_config_show(self, test_project):
        """Test config show command."""
        run_cli(["init"], cwd=test_project)
        result = run_cli(["config", "show"], cwd=test_project)

        assert result.returncode == 0
        assert "embedding" in result.stdout.lower()
        assert "chunking" in result.stdout.lower()

    def test_config_path(self, test_project):
        """Test config path command."""
        run_cli(["init"], cwd=test_project)
        result = run_cli(["config", "path"], cwd=test_project)

        assert result.returncode == 0
        # Output may have line wrapping, so normalize it
        output = result.stdout.replace("\n", "")
        assert "config.json" in output


class TestCLICompact:
    """Test 'sia-code compact' command."""

    def test_compact_not_initialized(self, test_project):
        """Test compact when not initialized."""
        result = run_cli(["compact", "."], cwd=test_project)

        assert result.returncode != 0

    def test_compact_healthy_index(self, test_project):
        """Test compact on healthy index."""
        run_cli(["init"], cwd=test_project)
        run_cli(["index", "."], cwd=test_project)

        # Need to run incremental index first to create chunk_index.json
        run_cli(["index", "--update", "."], cwd=test_project)

        result = run_cli(["compact", "."], cwd=test_project)

        # Should either compact or say not needed
        assert result.returncode == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
