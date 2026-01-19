"""Core type definitions for PCI."""

from enum import Enum
from typing import NewType

# Type aliases for clarity
FileId = NewType("FileId", str)
ChunkId = NewType("ChunkId", str)
FilePath = NewType("FilePath", str)
LineNumber = NewType("LineNumber", int)
ByteOffset = NewType("ByteOffset", int)


class Language(str, Enum):
    """Supported programming languages."""

    # Programming languages
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JSX = "jsx"
    TSX = "tsx"
    JAVA = "java"
    KOTLIN = "kotlin"
    GROOVY = "groovy"
    C = "c"
    CPP = "cpp"
    CSHARP = "csharp"
    GO = "go"
    RUST = "rust"
    HASKELL = "haskell"
    SWIFT = "swift"
    BASH = "bash"
    MATLAB = "matlab"
    MAKEFILE = "makefile"
    OBJECTIVE_C = "objective_c"
    PHP = "php"
    RUBY = "ruby"
    VUE = "vue"
    SVELTE = "svelte"
    ZIG = "zig"

    # Configuration languages
    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    HCL = "hcl"
    MARKDOWN = "markdown"

    # Text-based
    TEXT = "text"
    PDF = "pdf"

    UNKNOWN = "unknown"

    @classmethod
    def from_extension(cls, ext: str) -> "Language":
        """Get language from file extension."""
        ext = ext.lower().lstrip(".")
        extension_map = {
            "py": cls.PYTHON,
            "js": cls.JAVASCRIPT,
            "mjs": cls.JAVASCRIPT,
            "cjs": cls.JAVASCRIPT,
            "ts": cls.TYPESCRIPT,
            "jsx": cls.JSX,
            "tsx": cls.TSX,
            "java": cls.JAVA,
            "kt": cls.KOTLIN,
            "kts": cls.KOTLIN,
            "groovy": cls.GROOVY,
            "c": cls.C,
            "h": cls.C,
            "cpp": cls.CPP,
            "cc": cls.CPP,
            "cxx": cls.CPP,
            "hpp": cls.CPP,
            "cs": cls.CSHARP,
            "go": cls.GO,
            "rs": cls.RUST,
            "hs": cls.HASKELL,
            "swift": cls.SWIFT,
            "sh": cls.BASH,
            "bash": cls.BASH,
            "m": cls.MATLAB,
            "makefile": cls.MAKEFILE,
            "mk": cls.MAKEFILE,
            "objc": cls.OBJECTIVE_C,
            "php": cls.PHP,
            "rb": cls.RUBY,
            "vue": cls.VUE,
            "svelte": cls.SVELTE,
            "zig": cls.ZIG,
            "json": cls.JSON,
            "yaml": cls.YAML,
            "yml": cls.YAML,
            "toml": cls.TOML,
            "hcl": cls.HCL,
            "tf": cls.HCL,
            "md": cls.MARKDOWN,
            "markdown": cls.MARKDOWN,
            "txt": cls.TEXT,
            "pdf": cls.PDF,
        }
        return extension_map.get(ext, cls.UNKNOWN)


class ChunkType(str, Enum):
    """Types of code chunks based on semantic meaning."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    BLOCK = "block"
    COMMENT = "comment"
    DOCSTRING = "docstring"
    IMPORT = "import"
    STRUCTURE = "structure"
    CALL = "call"
    DEFINITION = "definition"
    UNKNOWN = "unknown"


class ConceptType(str, Enum):
    """Types of semantic concepts extracted from AST."""

    DEFINITION = "definition"  # Functions, classes, methods
    BLOCK = "block"  # Code blocks, control flow
    COMMENT = "comment"  # Comments, docstrings
    STRUCTURE = "structure"  # File structure, imports
    CALL = "call"  # Function/method calls


class IndexTier(str, Enum):
    """Index tier for chunk source classification."""

    PROJECT = "project"  # User's codebase (primary)
    DEPENDENCY = "dependency"  # Installed packages (stubs/exports)
    STDLIB = "stdlib"  # Standard library (future)
