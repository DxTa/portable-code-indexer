"""Link documentation to code chunks using proximity and symbol extraction.

Documentation linking strategies:
1. Proximity-based: README.md in a directory relates to code in that directory
2. Symbol extraction: Extract code references from markdown (e.g., `function_name`)
3. Hierarchy: docs/ folder structure mirrors code structure
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Iterator
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class DocumentationLink:
    """A link between documentation and code."""

    doc_path: Path  # Path to documentation file
    code_pattern: str  # Pattern to match code files/symbols
    link_type: str  # "proximity", "symbol", "explicit"
    confidence: float  # 0.0 to 1.0
    metadata: dict = field(default_factory=dict)


@dataclass
class DocumentationChunk:
    """A chunk of documentation to be indexed."""

    file_path: Path
    content: str
    symbols: list[str]  # Extracted code symbols (functions, classes, etc.)
    related_paths: list[Path]  # Related code files by proximity


class DocumentationLinker:
    """Links documentation files to code chunks.

    Uses multiple strategies:
    - Proximity: README.md in a directory relates to code in that directory
    - Symbol extraction: Extract `code_references` from markdown
    - Hierarchy: docs/api/auth.md might relate to src/auth/
    """

    # Documentation file patterns
    DOC_PATTERNS = [
        "README.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "*.md",
        "docs/**/*.md",
        "doc/**/*.md",
    ]

    # Regex to extract code symbols from markdown
    # Matches: `symbol_name`, `ClassName.method`, `package.module.function`, `sia-code`, `file/path`
    CODE_REFERENCE_PATTERN = re.compile(r"`([a-zA-Z_][a-zA-Z0-9_\.\-/]*)`")

    # Regex to extract code blocks with language hints
    CODE_BLOCK_PATTERN = re.compile(
        r"```(?P<lang>\w+)?\n(?P<code>.*?)```", re.DOTALL | re.MULTILINE
    )

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def discover_documentation(self, dry_run: bool = False) -> Iterator[DocumentationChunk]:
        """Discover and process documentation files.

        Args:
            dry_run: If True, just log what would be indexed

        Yields:
            DocumentationChunk for each documentation file found
        """
        doc_files = self._find_documentation_files()

        for doc_file in doc_files:
            if not doc_file.exists():
                continue

            try:
                content = doc_file.read_text(encoding="utf-8", errors="ignore")
            except (IOError, UnicodeDecodeError) as e:
                logger.warning(f"Could not read {doc_file}: {e}")
                continue

            # Extract code symbols from markdown
            symbols = self._extract_symbols(content)

            # Find related code files by proximity
            related_paths = self._find_related_by_proximity(doc_file)

            if dry_run:
                logger.info(f"[DRY-RUN] Would index: {doc_file.relative_to(self.project_root)}")
                logger.info(f"  Symbols: {len(symbols)}")
                logger.info(f"  Related paths: {len(related_paths)}")
                continue

            yield DocumentationChunk(
                file_path=doc_file,
                content=content,
                symbols=symbols,
                related_paths=related_paths,
            )

    def _find_documentation_files(self) -> list[Path]:
        """Find all documentation files in the project.

        Returns:
            List of documentation file paths
        """
        doc_files = []

        # README.md at project root
        readme = self.project_root / "README.md"
        if readme.exists():
            doc_files.append(readme)

        # CONTRIBUTING.md
        contributing = self.project_root / "CONTRIBUTING.md"
        if contributing.exists():
            doc_files.append(contributing)

        # CHANGELOG.md
        changelog = self.project_root / "CHANGELOG.md"
        if changelog.exists():
            doc_files.append(changelog)

        # All markdown files in docs/ and doc/
        for docs_dir in ["docs", "doc", "documentation"]:
            docs_path = self.project_root / docs_dir
            if docs_path.exists() and docs_path.is_dir():
                doc_files.extend(docs_path.rglob("*.md"))

        # Markdown files in subdirectories (but not node_modules, .git, etc.)
        exclude_dirs = {
            "node_modules",
            ".git",
            ".venv",
            "venv",
            "env",
            "__pycache__",
            ".pytest_cache",
            "dist",
            "build",
        }

        for md_file in self.project_root.rglob("*.md"):
            # Skip if in excluded directory
            if any(excluded in md_file.parts for excluded in exclude_dirs):
                continue

            # Skip if already added
            if md_file in doc_files:
                continue

            doc_files.append(md_file)

        return sorted(set(doc_files))

    def _extract_symbols(self, content: str) -> list[str]:
        """Extract code symbols from markdown content.

        Looks for:
        - Inline code: `function_name`, `ClassName.method`
        - Code blocks with function/class definitions

        Args:
            content: Markdown content

        Returns:
            List of extracted symbols
        """
        symbols = []

        # Extract inline code references
        for match in self.CODE_REFERENCE_PATTERN.finditer(content):
            symbol = match.group(1)

            # Filter out common non-code words
            if self._is_likely_code_symbol(symbol):
                symbols.append(symbol)

        # Extract from code blocks (optional, can be expensive)
        # for match in self.CODE_BLOCK_PATTERN.finditer(content):
        #     code = match.group("code")
        #     lang = match.group("lang") or "unknown"
        #     # Could parse code blocks to extract symbols
        #     # For now, skip to keep it lightweight

        return list(set(symbols))  # Deduplicate

    def _is_likely_code_symbol(self, symbol: str) -> bool:
        """Check if a string is likely a code symbol (not just a word).

        Args:
            symbol: Potential code symbol

        Returns:
            True if likely a code symbol
        """
        # Filter out common markdown/documentation words
        excluded = {
            "true",
            "false",
            "null",
            "undefined",
            "int",
            "str",
            "bool",
            "void",
            "const",
            "let",
            "var",
            "function",
            "class",
            "import",
            "from",
            "return",
            # Common non-code words
            "note",
            "warning",
            "example",
            "usage",
            "description",
            "parameters",
            "returns",
        }

        if symbol.lower() in excluded:
            return False

        # Must have at least one letter
        if not any(c.isalpha() for c in symbol):
            return False

        # Likely code if:
        # - Contains underscore (snake_case)
        # - Contains dot (module.function)
        # - Contains hyphen (kebab-case, model names)
        # - Contains slash (file paths)
        # - Has camelCase pattern
        # - All caps (CONSTANT)
        has_underscore = "_" in symbol
        has_dot = "." in symbol
        has_hyphen = "-" in symbol
        has_slash = "/" in symbol
        has_camel_case = any(
            c.isupper() and i > 0 and symbol[i - 1].islower() for i, c in enumerate(symbol)
        )
        all_caps = symbol.isupper() and len(symbol) > 2

        return has_underscore or has_dot or has_hyphen or has_slash or has_camel_case or all_caps

    def _find_related_by_proximity(self, doc_file: Path) -> list[Path]:
        """Find code files related by proximity (same directory).

        Args:
            doc_file: Documentation file path

        Returns:
            List of related code file paths
        """
        related = []

        doc_dir = doc_file.parent

        # Code file extensions
        code_extensions = {
            ".py",
            ".js",
            ".ts",
            ".tsx",
            ".jsx",
            ".go",
            ".rs",
            ".java",
            ".cpp",
            ".c",
            ".h",
            ".hpp",
            ".cs",
            ".rb",
            ".php",
        }

        # Find code files in the same directory
        if doc_dir.exists():
            for code_file in doc_dir.iterdir():
                if code_file.suffix in code_extensions:
                    related.append(code_file)

        # If this is a README.md, also look in subdirectories (1 level)
        if doc_file.name == "README.md":
            for subdir in doc_dir.iterdir():
                if subdir.is_dir() and not subdir.name.startswith("."):
                    for code_file in subdir.iterdir():
                        if code_file.suffix in code_extensions:
                            related.append(code_file)

        return related

    def create_links(self, doc_chunk: DocumentationChunk) -> Iterator[DocumentationLink]:
        """Create links between documentation and code.

        Args:
            doc_chunk: Documentation chunk to link

        Yields:
            DocumentationLink for each discovered relationship
        """
        # Proximity-based links (high confidence)
        for code_path in doc_chunk.related_paths:
            yield DocumentationLink(
                doc_path=doc_chunk.file_path,
                code_pattern=str(code_path.relative_to(self.project_root)),
                link_type="proximity",
                confidence=0.9,
                metadata={"reason": "same_directory"},
            )

        # Symbol-based links (medium confidence)
        for symbol in doc_chunk.symbols:
            yield DocumentationLink(
                doc_path=doc_chunk.file_path,
                code_pattern=symbol,
                link_type="symbol",
                confidence=0.6,
                metadata={"symbol": symbol},
            )

        # Hierarchy-based links (if in docs/ folder)
        if "docs" in doc_chunk.file_path.parts or "doc" in doc_chunk.file_path.parts:
            # docs/api/auth.md might relate to src/api/auth.py
            hierarchy_pattern = self._infer_hierarchy_pattern(doc_chunk.file_path)
            if hierarchy_pattern:
                yield DocumentationLink(
                    doc_path=doc_chunk.file_path,
                    code_pattern=hierarchy_pattern,
                    link_type="hierarchy",
                    confidence=0.7,
                    metadata={"pattern": hierarchy_pattern},
                )

    def _infer_hierarchy_pattern(self, doc_path: Path) -> str | None:
        """Infer code pattern from docs/ hierarchy.

        Examples:
        - docs/api/auth.md -> **/api/auth.py or **/api/auth/*
        - docs/getting-started.md -> None (general doc)

        Args:
            doc_path: Documentation file path

        Returns:
            Pattern to match code files, or None
        """
        try:
            # Get relative path from project root
            rel_path = doc_path.relative_to(self.project_root)

            # Remove docs/ or doc/ prefix
            parts = list(rel_path.parts)
            if parts[0] in ["docs", "doc", "documentation"]:
                parts = parts[1:]

            if not parts:
                return None

            # Remove .md extension from last part
            if parts[-1].endswith(".md"):
                parts[-1] = parts[-1][:-3]

            # Create pattern: api/auth -> **/api/auth.*
            pattern = "/".join(parts)
            return f"**/{pattern}.*"

        except ValueError:
            return None
