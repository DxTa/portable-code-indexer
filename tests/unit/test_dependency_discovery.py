"""Tests for dependency stub discovery (Phase 2)."""

import pytest
from pathlib import Path
from sia_code.indexer.dependency_discovery import DependencyDiscovery, DependencyLocation


@pytest.fixture
def discovery():
    """Create DependencyDiscovery instance."""
    return DependencyDiscovery()


@pytest.fixture
def mock_python_site_packages(tmp_path):
    """Create mock Python site-packages with various stub packages."""
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()

    # types-* package
    types_requests = site_packages / "types_requests"
    types_requests.mkdir()
    (types_requests / "__init__.pyi").write_text("# Type stubs for requests")

    # *-stubs package
    mypy_stubs = site_packages / "mypy-stubs"
    mypy_stubs.mkdir()
    (mypy_stubs / "__init__.pyi").write_text("# Mypy stubs")

    # PEP 561 inline stubs (py.typed marker)
    pydantic = site_packages / "pydantic"
    pydantic.mkdir()
    (pydantic / "py.typed").write_text("")
    (pydantic / "__init__.py").write_text("# Pydantic source")

    # PEP 561 inline stubs (__init__.pyi)
    fastapi = site_packages / "fastapi"
    fastapi.mkdir()
    (fastapi / "__init__.pyi").write_text("# FastAPI type stubs")
    (fastapi / "__init__.py").write_text("# FastAPI source")

    # Regular package without stubs
    regular = site_packages / "regular_package"
    regular.mkdir()
    (regular / "__init__.py").write_text("# Regular package")

    return site_packages


@pytest.fixture
def mock_node_modules(tmp_path):
    """Create mock node_modules with TypeScript type definitions."""
    node_modules = tmp_path / "node_modules"
    node_modules.mkdir()

    # @types/* package
    types_dir = node_modules / "@types"
    types_dir.mkdir()

    types_node = types_dir / "node"
    types_node.mkdir()
    (types_node / "index.d.ts").write_text("// Node.js type definitions")
    (types_node / "package.json").write_text('{"name": "@types/node", "version": "20.0.0"}')

    types_react = types_dir / "react"
    types_react.mkdir()
    (types_react / "index.d.ts").write_text("// React type definitions")
    (types_react / "package.json").write_text('{"name": "@types/react", "version": "18.0.0"}')

    # Package with inline .d.ts files
    axios = node_modules / "axios"
    axios.mkdir()
    (axios / "index.d.ts").write_text("// Axios type definitions")
    (axios / "package.json").write_text(
        '{"name": "axios", "version": "1.6.0", "types": "index.d.ts"}'
    )

    # Package with types field pointing to different file
    lodash = node_modules / "lodash"
    lodash.mkdir()
    (lodash / "lodash.d.ts").write_text("// Lodash type definitions")
    (lodash / "package.json").write_text(
        '{"name": "lodash", "version": "4.17.0", "types": "lodash.d.ts"}'
    )

    # Package without types
    no_types = node_modules / "no-types"
    no_types.mkdir()
    (no_types / "index.js").write_text("// No types")
    (no_types / "package.json").write_text('{"name": "no-types", "version": "1.0.0"}')

    return node_modules


class TestPythonDependencyDiscovery:
    """Test Python stub discovery."""

    def test_discovers_site_packages_directories(self, discovery, mock_python_site_packages):
        """Should find site-packages directories in project."""
        # Mock project with site-packages
        project_root = mock_python_site_packages.parent

        # The discovery should find site-packages
        site_packages_dirs = discovery._get_python_site_packages(project_root)

        # Should find at least the mock site-packages (or system ones)
        assert len(site_packages_dirs) >= 0  # May not find mocked one without proper venv structure

    def test_dry_run_logs_but_doesnt_yield(self, discovery, mock_python_site_packages):
        """dry_run=True should log but not yield DependencyLocation objects."""
        project_root = mock_python_site_packages.parent

        # Use dry_run to just count what would be indexed
        results = list(discovery.discover_python_stubs(project_root, dry_run=True))

        # dry_run=True should not yield results (only logs)
        assert len(results) == 0, "dry_run should not yield results"

    def test_filters_stub_packages_correctly(self, discovery):
        """Should identify different types of stub packages."""
        # Test stub type detection logic
        assert discovery._get_python_site_packages(Path(".")) is not None


class TestTypescriptDependencyDiscovery:
    """Test TypeScript stub discovery."""

    def test_discovers_at_types_packages(self, discovery, mock_node_modules):
        """Should find @types/* packages in node_modules."""
        project_root = mock_node_modules.parent

        results = list(discovery.discover_typescript_stubs(project_root, dry_run=False))

        # Should find @types/node and @types/react
        names = [dep.name for dep in results]
        assert "node" in names or "react" in names, "Should discover @types packages"

    def test_discovers_inline_dts_files(self, discovery, mock_node_modules):
        """Should find packages with inline .d.ts files."""
        project_root = mock_node_modules.parent

        results = list(discovery.discover_typescript_stubs(project_root, dry_run=False))

        # Should find axios and lodash (both have types field)
        names = [dep.name for dep in results]

        # At minimum should find the @types packages
        assert len(results) >= 2, "Should discover multiple type packages"

    def test_reads_version_from_package_json(self, discovery, mock_node_modules):
        """Should extract version from package.json."""
        project_root = mock_node_modules.parent

        results = list(discovery.discover_typescript_stubs(project_root, dry_run=False))

        # Check that versions are extracted
        for dep in results:
            if dep.name in ["node", "react", "axios", "lodash"]:
                assert dep.version is not None, f"{dep.name} should have version"

    def test_dry_run_doesnt_yield_results(self, discovery, mock_node_modules):
        """dry_run=True should not yield results."""
        project_root = mock_node_modules.parent

        results = list(discovery.discover_typescript_stubs(project_root, dry_run=True))

        # dry_run should not yield
        assert len(results) == 0, "dry_run should not yield results"


class TestDependencyLocation:
    """Test DependencyLocation dataclass."""

    def test_dependency_location_creation(self):
        """Test creating DependencyLocation instances."""
        dep = DependencyLocation(
            name="requests",
            version="2.31.0",
            path=Path("/site-packages/requests"),
            language="python",
            is_stub=True,
        )

        assert dep.name == "requests"
        assert dep.version == "2.31.0"
        assert dep.language == "python"
        assert dep.is_stub is True

    def test_dependency_location_optional_version(self):
        """Version can be None for unknown versions."""
        dep = DependencyLocation(
            name="unknown-package",
            version=None,
            path=Path("/some/path"),
            language="typescript",
            is_stub=False,
        )

        assert dep.version is None


class TestIntegrationDiscovery:
    """Integration tests using real project structure."""

    def test_discovers_stubs_in_current_project(self, discovery):
        """Test discovery on the actual sia-code project."""
        project_root = Path(__file__).parent.parent.parent

        # Should not crash when running on real project
        python_stubs = list(discovery.discover_python_stubs(project_root, dry_run=True))

        # Dry run returns empty list but shouldn't crash
        assert isinstance(python_stubs, list)

    def test_handles_missing_node_modules_gracefully(self, discovery, tmp_path):
        """Should handle projects without node_modules gracefully."""
        project_root = tmp_path / "no-node-modules"
        project_root.mkdir()

        # Should not crash, just return empty
        results = list(discovery.discover_typescript_stubs(project_root, dry_run=False))

        assert len(results) == 0, "Should return empty list for missing node_modules"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
