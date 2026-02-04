"""Shared fixtures for E2E tests across multiple language repositories."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def e2e_repo_url():
    """Get repository URL from environment."""
    return os.environ.get("E2E_REPO_URL", "")


@pytest.fixture(scope="session")
def e2e_sparse_paths():
    """Get sparse checkout paths from environment."""
    return os.environ.get("E2E_SPARSE_PATHS", "")


@pytest.fixture(scope="session")
def e2e_language():
    """Get target language from environment."""
    return os.environ.get("E2E_LANGUAGE", "python")


@pytest.fixture(scope="session")
def e2e_keyword():
    """Get expected language keyword from environment."""
    return os.environ.get("E2E_KEYWORD", "def")


@pytest.fixture(scope="session")
def e2e_symbol():
    """Get expected symbol name from environment."""
    return os.environ.get("E2E_SYMBOL", "main")


@pytest.fixture(scope="session")
def target_repo(tmp_path_factory, e2e_repo_url, e2e_sparse_paths):
    """Clone target repository for testing.

    Uses sparse checkout for large repos if E2E_SPARSE_PATHS is set.
    Falls back to E2E_REPO_PATH if URL not provided.
    """
    # Check if repo path provided directly
    repo_path_env = os.environ.get("E2E_REPO_PATH")
    if repo_path_env:
        repo_path = Path(repo_path_env).resolve()
        if repo_path.exists():
            yield repo_path
            return

    # Clone repository
    if not e2e_repo_url:
        pytest.skip("E2E_REPO_URL not provided")

    tmp_dir = tmp_path_factory.mktemp("repos")
    repo_dir = tmp_dir / "target-repo"

    try:
        if e2e_sparse_paths:
            # Sparse checkout for large repos
            subprocess.run(
                [
                    "git",
                    "clone",
                    "--filter=blob:none",
                    "--sparse",
                    e2e_repo_url,
                    str(repo_dir),
                ],
                check=True,
                capture_output=True,
            )

            # Set sparse checkout paths
            subprocess.run(
                ["git", "sparse-checkout", "set"] + e2e_sparse_paths.split(),
                cwd=repo_dir,
                check=True,
                capture_output=True,
            )
        else:
            # Full shallow clone
            subprocess.run(
                ["git", "clone", "--depth", "1", e2e_repo_url, str(repo_dir)],
                check=True,
                capture_output=True,
            )

        yield repo_dir
    finally:
        # Cleanup
        if repo_dir.exists():
            shutil.rmtree(repo_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def initialized_repo(target_repo):
    """Initialize sia-code in the target repository."""
    result = subprocess.run(
        ["sia-code", "init"],
        cwd=target_repo,
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        pytest.fail(f"Failed to initialize sia-code: {result.stderr}")

    # Verify initialization
    sia_dir = target_repo / ".sia-code"
    assert sia_dir.exists(), ".sia-code directory not created"
    assert (sia_dir / "config.json").exists(), "config.json not created"
    assert (sia_dir / "index.db").exists(), "index.db not created"

    # Use smaller/faster embedding model for CI to avoid CPU timeout
    # bge-small is ~3x faster than bge-base on CPU, still tests full embedding pipeline
    config_path = sia_dir / "config.json"
    with open(config_path) as f:
        ci_config = json.load(f)
    ci_config["embedding"]["model"] = "BAAI/bge-small-en-v1.5"
    ci_config["embedding"]["dimensions"] = 384
    with open(config_path, "w") as f:
        json.dump(ci_config, f, indent=2)

    return target_repo


@pytest.fixture(scope="session")
def indexed_repo(initialized_repo):
    """Index the target repository.

    This fixture indexes the repository once per test session,
    making all subsequent tests faster.

    Uses --clean to recreate index with CI-optimized dimensions (384d bge-small)
    after initialized_repo modifies the config from default (768d bge-base).
    """
    # Check if index already has content (skip re-indexing if it does)
    index_path = initialized_repo / ".sia-code" / "index.db"
    if index_path.exists() and index_path.stat().st_size > 100000:  # >100KB means indexed
        # Index exists and has content, skip re-indexing
        return initialized_repo

    result = subprocess.run(
        ["sia-code", "index", "--clean", "."],
        cwd=initialized_repo,
        capture_output=True,
        text=True,
        timeout=600,  # 10 minute timeout for large repos
    )

    if result.returncode != 0:
        pytest.fail(f"Failed to index repository: {result.stderr}")

    # Verify indexing completed
    assert "complete" in result.stdout.lower() or "indexed" in result.stdout.lower()

    return initialized_repo


def pytest_addoption(parser):
    """Add command line options for E2E tests."""
    parser.addoption(
        "--run-semantic-quality",
        action="store_true",
        default=False,
        help="run semantic quality tests (requires OPENAI_API_KEY)",
    )
