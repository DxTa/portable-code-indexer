"""Base test class for E2E tests with common utilities."""

import json
import subprocess
from pathlib import Path
from typing import Any


class BaseE2ETest:
    """Base class providing common E2E test utilities.

    Subclasses should override:
    - LANGUAGE: str - Language being tested (e.g., "python", "java")
    - EXPECTED_KEYWORD: str - Language-specific keyword (e.g., "def", "class", "func")
    - EXPECTED_SYMBOL: str - Known symbol in the repository (e.g., "Session", "Router")
    """

    LANGUAGE: str = "unknown"
    EXPECTED_KEYWORD: str = ""
    EXPECTED_SYMBOL: str = ""

    def run_cli(
        self, args: list[str], cwd: Path, timeout: int = 300
    ) -> subprocess.CompletedProcess:
        """Run sia-code CLI command.

        Args:
            args: CLI arguments (e.g., ["search", "query"])
            cwd: Working directory
            timeout: Command timeout in seconds (default: 5 min)

        Returns:
            CompletedProcess with stdout, stderr, returncode
        """
        return subprocess.run(
            ["sia-code"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def search_json(
        self, query: str, cwd: Path, regex: bool = True, limit: int = 10
    ) -> dict[str, Any]:
        """Run search command and parse JSON output.

        Args:
            query: Search query
            cwd: Working directory
            regex: Use regex/lexical search (default: True)
            limit: Maximum results (default: 10)

        Returns:
            Parsed JSON dict with "query", "mode", "results" keys
        """
        args = ["search", query, "--format", "json", "-k", str(limit), "--no-filter"]
        if regex:
            args.append("--regex")

        result = self.run_cli(args, cwd)

        if result.returncode != 0:
            return {"query": query, "mode": "lexical" if regex else "semantic", "results": []}

        # Handle "No results found" message
        if "no results" in result.stdout.lower():
            return {"query": query, "mode": "lexical" if regex else "semantic", "results": []}

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"query": query, "mode": "lexical" if regex else "semantic", "results": []}

    def get_result_symbols(self, results: dict[str, Any]) -> list[str]:
        """Extract symbol names from search results.

        Args:
            results: Parsed JSON search results

        Returns:
            List of symbol names
        """
        return [r["chunk"]["symbol"] for r in results.get("results", [])]

    def get_result_file_paths(self, results: dict[str, Any]) -> list[str]:
        """Extract file paths from search results.

        Args:
            results: Parsed JSON search results

        Returns:
            List of file paths
        """
        return [r["chunk"]["file_path"] for r in results.get("results", [])]

    def assert_contains_language_extension(self, file_paths: list[str], extensions: list[str]):
        """Assert that at least one file has a language-specific extension.

        Args:
            file_paths: List of file paths from results
            extensions: Expected file extensions (e.g., [".py", ".java"])
        """
        assert any(any(fp.endswith(ext) for ext in extensions) for fp in file_paths), (
            f"No files with extensions {extensions} found in results: {file_paths}"
        )


class PythonE2ETest(BaseE2ETest):
    """Python-specific E2E test base."""

    LANGUAGE = "python"
    EXPECTED_KEYWORD = "def"


class JavaScriptE2ETest(BaseE2ETest):
    """JavaScript-specific E2E test base."""

    LANGUAGE = "javascript"
    EXPECTED_KEYWORD = "function"


class TypeScriptE2ETest(BaseE2ETest):
    """TypeScript-specific E2E test base."""

    LANGUAGE = "typescript"
    EXPECTED_KEYWORD = "function"


class GoE2ETest(BaseE2ETest):
    """Go-specific E2E test base."""

    LANGUAGE = "go"
    EXPECTED_KEYWORD = "func"


class RustE2ETest(BaseE2ETest):
    """Rust-specific E2E test base."""

    LANGUAGE = "rust"
    EXPECTED_KEYWORD = "fn"


class JavaE2ETest(BaseE2ETest):
    """Java-specific E2E test base."""

    LANGUAGE = "java"
    EXPECTED_KEYWORD = "class"


class CppE2ETest(BaseE2ETest):
    """C++-specific E2E test base."""

    LANGUAGE = "cpp"
    EXPECTED_KEYWORD = "class"


class CSharpE2ETest(BaseE2ETest):
    """C#-specific E2E test base."""

    LANGUAGE = "csharp"
    EXPECTED_KEYWORD = "class"


class RubyE2ETest(BaseE2ETest):
    """Ruby-specific E2E test base."""

    LANGUAGE = "ruby"
    EXPECTED_KEYWORD = "def"


class PhpE2ETest(BaseE2ETest):
    """PHP-specific E2E test base."""

    LANGUAGE = "php"
    EXPECTED_KEYWORD = "function"
