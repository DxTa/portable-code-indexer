"""Discover type stubs and dependency locations for indexing.

Uses ecosystem tools (pip list, npm ls) for accurate discovery instead of
manual filesystem scanning.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Iterator
import subprocess
import json
import sys
import logging

logger = logging.getLogger(__name__)


@dataclass
class DependencyLocation:
    """Location of a dependency's type stubs or source."""

    name: str
    version: str | None
    path: Path
    language: str
    is_stub: bool  # True for .pyi/.d.ts, False for source


@dataclass
class DiscoveryStats:
    """Statistics from dependency discovery."""

    packages_found: int = 0
    stubs_found: int = 0
    errors: list[str] = field(default_factory=list)


class DependencyDiscovery:
    """Discovers installed dependencies and their type stubs.

    Uses ecosystem tools (pip list, npm ls) for accurate discovery
    instead of manual filesystem scanning.
    """

    def __init__(self):
        # Cache for pip/npm results (avoid repeated subprocess calls)
        self._pip_packages: dict[str, str] | None = None
        self._npm_packages: dict[str, dict] | None = None

    # ========== Python ==========

    def discover_python_stubs(
        self,
        project_root: Path,
        dry_run: bool = False,
    ) -> Iterator[DependencyLocation]:
        """Find Python .pyi stubs using pip list (cached).

        Args:
            project_root: Project root directory
            dry_run: If True, just log what would be indexed

        Yields:
            DependencyLocation for each stub package found
        """
        # Get all installed packages (cached)
        packages = self._get_pip_packages(project_root)

        if packages is None:
            logger.warning("Could not get pip packages list")
            return

        # Find site-packages directories
        site_packages_dirs = self._get_python_site_packages(project_root)

        for sp in site_packages_dirs:
            if not sp.exists():
                continue

            # Look for stub packages: types-* and *-stubs
            for pkg_dir in sp.iterdir():
                if not pkg_dir.is_dir():
                    continue

                name = pkg_dir.name
                is_stub = False
                target_name = name

                if name.startswith("types_") or name.startswith("types-"):
                    is_stub = True
                    target_name = name.replace("types_", "").replace("types-", "")
                elif name.endswith("-stubs") or name.endswith("_stubs"):
                    is_stub = True
                    target_name = name.replace("-stubs", "").replace("_stubs", "")
                elif (pkg_dir / "__init__.pyi").exists() or (pkg_dir / "py.typed").exists():
                    # Inline stubs (PEP 561)
                    is_stub = True
                    target_name = name

                if is_stub:
                    version = packages.get(name) or packages.get(target_name)

                    if dry_run:
                        logger.info(f"[DRY-RUN] Would index Python stub: {name} ({version})")
                        continue

                    yield DependencyLocation(
                        name=target_name,
                        version=version,
                        path=pkg_dir,
                        language="python",
                        is_stub=True,
                    )

    def _get_pip_packages(self, project_root: Path) -> dict[str, str] | None:
        """Get installed pip packages as {name: version} dict.

        Uses pip list --format=json (single call, cached).
        """
        if self._pip_packages is not None:
            return self._pip_packages

        # Try project venv first, then system
        python_paths = [
            project_root / "venv" / "bin" / "python",
            project_root / ".venv" / "bin" / "python",
            project_root / "env" / "bin" / "python",
            project_root / "virtualenv" / "bin" / "python",
            # Conda
            project_root / "conda" / "bin" / "python",
            # System Python
            Path(sys.executable),
        ]

        for python_path in python_paths:
            if not python_path.exists():
                continue

            try:
                result = subprocess.run(
                    [str(python_path), "-m", "pip", "list", "--format=json"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(project_root),
                )

                if result.returncode == 0:
                    packages = json.loads(result.stdout)
                    self._pip_packages = {
                        pkg["name"].lower().replace("-", "_"): pkg["version"] for pkg in packages
                    }
                    logger.debug(f"Found {len(self._pip_packages)} pip packages")
                    return self._pip_packages

            except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
                logger.debug(f"pip list failed for {python_path}: {e}")
                continue

        logger.warning("Could not get pip package list from any Python")
        return None

    def _get_python_site_packages(self, project_root: Path) -> list[Path]:
        """Get Python site-packages directories.

        Checks venv, .venv, env, virtualenv, conda, and system.
        """
        paths = []

        # Project virtual environments
        venv_patterns = [
            project_root / "venv" / "lib",
            project_root / ".venv" / "lib",
            project_root / "env" / "lib",
            project_root / "virtualenv" / "lib",
            # Conda environment
            project_root / "conda" / "lib",
        ]

        for venv_lib in venv_patterns:
            if venv_lib.exists():
                # Find python3.X directory
                for python_dir in venv_lib.iterdir():
                    if python_dir.name.startswith("python"):
                        sp = python_dir / "site-packages"
                        if sp.exists():
                            paths.append(sp)

        # System site-packages (fallback)
        try:
            import site

            for sp in site.getsitepackages():
                p = Path(sp)
                if p.exists() and p not in paths:
                    paths.append(p)
        except AttributeError:
            pass

        return paths

    # ========== TypeScript/JavaScript ==========

    def discover_typescript_stubs(
        self,
        project_root: Path,
        dry_run: bool = False,
    ) -> Iterator[DependencyLocation]:
        """Find TypeScript .d.ts files using npm ls (cached).

        Handles npm, yarn, and pnpm.

        Args:
            project_root: Project root directory
            dry_run: If True, just log what would be indexed

        Yields:
            DependencyLocation for each type definition package found
        """
        node_modules = project_root / "node_modules"

        if not node_modules.exists():
            return

        # Get installed packages from npm/yarn/pnpm
        packages = self._get_npm_packages(project_root)

        # @types packages (highest priority)
        types_dir = node_modules / "@types"
        if types_dir.exists():
            for type_pkg in types_dir.iterdir():
                if not type_pkg.is_dir():
                    continue

                version = None
                if packages:
                    version = packages.get(f"@types/{type_pkg.name}", {}).get("version")
                else:
                    # Fallback to package.json
                    version = self._get_npm_version(type_pkg)

                if dry_run:
                    logger.info(f"[DRY-RUN] Would index @types/{type_pkg.name} ({version})")
                    continue

                yield DependencyLocation(
                    name=type_pkg.name,
                    version=version,
                    path=type_pkg,
                    language="typescript",
                    is_stub=True,
                )

        # Packages with inline .d.ts (only if they're in package.json)
        if packages:
            for pkg_name, pkg_info in packages.items():
                if pkg_name.startswith("@types/"):
                    continue  # Already handled above

                # Determine package path
                if "/" in pkg_name:
                    # Scoped package: @scope/name
                    parts = pkg_name.split("/")
                    pkg_path = node_modules / parts[0] / parts[1]
                else:
                    pkg_path = node_modules / pkg_name

                if not pkg_path.exists():
                    continue

                # Check for .d.ts files
                has_types = (
                    (pkg_path / "index.d.ts").exists()
                    or (pkg_path / (pkg_name.split("/")[-1] + ".d.ts")).exists()
                    or self._has_types_field(pkg_path)
                )

                if has_types:
                    if dry_run:
                        logger.info(f"[DRY-RUN] Would index inline types: {pkg_name}")
                        continue

                    yield DependencyLocation(
                        name=pkg_name,
                        version=pkg_info.get("version"),
                        path=pkg_path,
                        language="typescript",
                        is_stub=True,
                    )

    def _get_npm_packages(self, project_root: Path) -> dict[str, dict] | None:
        """Get installed npm packages as {name: {version, ...}} dict.

        Tries npm ls, yarn list, pnpm list in order.
        """
        if self._npm_packages is not None:
            return self._npm_packages

        # Try npm first
        try:
            result = subprocess.run(
                ["npm", "ls", "--json", "--depth=0", "--all"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(project_root),
            )

            if result.returncode == 0 or result.stdout:
                data = json.loads(result.stdout)
                deps = data.get("dependencies", {})
                self._npm_packages = deps
                logger.debug(f"Found {len(deps)} npm packages")
                return self._npm_packages

        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

        # Try yarn
        try:
            result = subprocess.run(
                ["yarn", "list", "--json", "--depth=0"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(project_root),
            )

            if result.returncode == 0:
                # Yarn outputs newline-delimited JSON
                packages = {}
                for line in result.stdout.splitlines():
                    try:
                        item = json.loads(line)
                        if item.get("type") == "tree":
                            for dep in item.get("data", {}).get("trees", []):
                                name = dep.get("name", "").rsplit("@", 1)[0]
                                version = dep.get("name", "").rsplit("@", 1)[-1]
                                packages[name] = {"version": version}
                    except json.JSONDecodeError:
                        continue

                self._npm_packages = packages
                return self._npm_packages

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Try pnpm
        try:
            result = subprocess.run(
                ["pnpm", "list", "--json", "--depth=0"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(project_root),
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                if isinstance(data, list) and data:
                    deps = data[0].get("dependencies", {})
                    self._npm_packages = deps
                    return self._npm_packages

        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

        logger.warning("Could not get npm/yarn/pnpm package list")
        return None

    def _get_npm_version(self, pkg_dir: Path) -> str | None:
        """Get npm package version from package.json (fallback)."""
        pkg_json = pkg_dir / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text())
                return data.get("version")
            except (json.JSONDecodeError, IOError):
                pass
        return None

    def _has_types_field(self, pkg_dir: Path) -> bool:
        """Check if package.json has types/typings field."""
        pkg_json = pkg_dir / "package.json"
        if pkg_json.exists():
            try:
                data = json.loads(pkg_json.read_text())
                return bool(data.get("types") or data.get("typings"))
            except (json.JSONDecodeError, IOError):
                pass
        return False
