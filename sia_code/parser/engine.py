"""Tree-sitter parsing engine wrapper."""

from pathlib import Path

try:
    import tree_sitter_python as ts_python
    import tree_sitter_javascript as ts_javascript
    import tree_sitter_typescript as ts_typescript
    import tree_sitter_go as ts_go
    import tree_sitter_rust as ts_rust
    import tree_sitter_java as ts_java
    import tree_sitter_c as ts_c
    import tree_sitter_cpp as ts_cpp
    import tree_sitter_c_sharp as ts_csharp
    import tree_sitter_ruby as ts_ruby
    import tree_sitter_php as ts_php
    from tree_sitter import Parser, Language

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    Parser = None
    Language = None

from ..core.types import Language as PciLanguage


class TreeSitterEngine:
    """Wrapper for Tree-sitter parsing."""

    def __init__(self):
        """Initialize Tree-sitter engine with language support."""
        if not TREE_SITTER_AVAILABLE:
            raise ImportError("tree-sitter packages not available")

        self._parsers = {}
        self._load_parsers()

    def _load_parsers(self) -> None:
        """Load Tree-sitter parsers for each language."""
        try:
            # Python
            py_lang = Language(ts_python.language())
            self._parsers[PciLanguage.PYTHON] = Parser(py_lang)

            # JavaScript
            js_lang = Language(ts_javascript.language())
            self._parsers[PciLanguage.JAVASCRIPT] = Parser(js_lang)

            # TypeScript
            ts_lang = Language(ts_typescript.language_typescript())
            self._parsers[PciLanguage.TYPESCRIPT] = Parser(ts_lang)

            # TSX
            tsx_lang = Language(ts_typescript.language_tsx())
            self._parsers[PciLanguage.TSX] = Parser(tsx_lang)

            # Go
            go_lang = Language(ts_go.language())
            self._parsers[PciLanguage.GO] = Parser(go_lang)

            # Rust
            rust_lang = Language(ts_rust.language())
            self._parsers[PciLanguage.RUST] = Parser(rust_lang)

            # Java
            java_lang = Language(ts_java.language())
            self._parsers[PciLanguage.JAVA] = Parser(java_lang)

            # C
            c_lang = Language(ts_c.language())
            self._parsers[PciLanguage.C] = Parser(c_lang)
            self._parsers[PciLanguage.CPP] = Parser(c_lang)  # C++ uses same initially

            # C++
            cpp_lang = Language(ts_cpp.language())
            self._parsers[PciLanguage.CPP] = Parser(cpp_lang)  # Override with C++

            # C#
            csharp_lang = Language(ts_csharp.language())
            self._parsers[PciLanguage.CSHARP] = Parser(csharp_lang)

            # Ruby
            ruby_lang = Language(ts_ruby.language())
            self._parsers[PciLanguage.RUBY] = Parser(ruby_lang)

            # PHP
            php_lang = Language(ts_php.language_php())  # Note: special function name
            self._parsers[PciLanguage.PHP] = Parser(php_lang)

        except Exception as e:
            print(f"Warning: Could not load all language parsers: {e}")

    def parse_file(self, file_path: Path, language: PciLanguage):
        """Parse a file and return the AST root node."""
        if language not in self._parsers:
            return None

        try:
            with open(file_path, "rb") as f:
                source_code = f.read()
            return self.parse_code(source_code, language)
        except Exception as e:
            # Log parse failures for debugging
            import logging

            logging.getLogger(__name__).debug(f"Parse failed for {file_path}: {e}")
            return None

    def parse_code(self, source_code: bytes | str, language: PciLanguage):
        """Parse source code and return AST root node."""
        if language not in self._parsers:
            return None

        if isinstance(source_code, str):
            source_code = source_code.encode("utf-8")

        try:
            parser = self._parsers[language]
            tree = parser.parse(source_code)
            return tree.root_node
        except Exception as e:
            # Log parse failures for debugging
            import logging

            logging.getLogger(__name__).debug(f"Parse code failed for {language}: {e}")
            return None

    def is_supported(self, language: PciLanguage) -> bool:
        """Check if language is supported."""
        return language in self._parsers
