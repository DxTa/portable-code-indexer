"""Concept extraction from AST nodes."""

from dataclasses import dataclass
from typing import Any

from tree_sitter import Node

from ..core.types import ChunkType, ConceptType, Language, LineNumber, ByteOffset


@dataclass
class UniversalConcept:
    """A semantic concept extracted from code."""

    concept_type: ConceptType
    chunk_type: ChunkType
    symbol: str
    start_line: LineNumber
    end_line: LineNumber
    start_byte: ByteOffset
    end_byte: ByteOffset
    code: str
    parent_header: str | None = None
    metadata: dict[str, Any] | None = None


class ConceptExtractor:
    """Extract semantic concepts from AST."""

    def __init__(self, language: Language):
        """Initialize concept extractor.

        Args:
            language: Programming language
        """
        self.language = language

    def extract_concepts(self, root: Node, source_code: bytes) -> list[UniversalConcept]:
        """Extract all semantic concepts from AST.

        Args:
            root: Root AST node
            source_code: Original source code

        Returns:
            List of extracted concepts
        """
        concepts = []

        if self.language == Language.PYTHON:
            concepts.extend(self._extract_python_concepts(root, source_code))
        elif self.language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
            concepts.extend(self._extract_javascript_concepts(root, source_code))
        elif self.language in (
            Language.GO,
            Language.RUST,
            Language.JAVA,
            Language.C,
            Language.CPP,
            Language.CSHARP,
            Language.RUBY,
            Language.PHP,
        ):
            # Use generic extractor for other languages
            concepts.extend(self._extract_generic_concepts(root, source_code))

        return concepts

    def _extract_python_concepts(self, root: Node, source_code: bytes) -> list[UniversalConcept]:
        """Extract Python-specific concepts."""
        concepts = []

        def traverse(node: Node, parent_class: str | None = None):
            # Function definitions
            if node.type == "function_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbol = source_code[name_node.start_byte : name_node.end_byte].decode("utf-8")
                    concepts.append(
                        UniversalConcept(
                            concept_type=ConceptType.DEFINITION,
                            chunk_type=ChunkType.METHOD if parent_class else ChunkType.FUNCTION,
                            symbol=symbol,
                            start_line=LineNumber(node.start_point[0] + 1),
                            end_line=LineNumber(node.end_point[0] + 1),
                            start_byte=ByteOffset(node.start_byte),
                            end_byte=ByteOffset(node.end_byte),
                            code=source_code[node.start_byte : node.end_byte].decode("utf-8"),
                            parent_header=parent_class,
                        )
                    )

            # Class definitions
            elif node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbol = source_code[name_node.start_byte : name_node.end_byte].decode("utf-8")
                    concepts.append(
                        UniversalConcept(
                            concept_type=ConceptType.DEFINITION,
                            chunk_type=ChunkType.CLASS,
                            symbol=symbol,
                            start_line=LineNumber(node.start_point[0] + 1),
                            end_line=LineNumber(node.end_point[0] + 1),
                            start_byte=ByteOffset(node.start_byte),
                            end_byte=ByteOffset(node.end_byte),
                            code=source_code[node.start_byte : node.end_byte].decode("utf-8"),
                        )
                    )
                    # Traverse children with class context
                    for child in node.children:
                        traverse(child, parent_class=symbol)
                    return  # Don't traverse again

            # Comments
            elif node.type == "comment":
                concepts.append(
                    UniversalConcept(
                        concept_type=ConceptType.COMMENT,
                        chunk_type=ChunkType.COMMENT,
                        symbol="comment",
                        start_line=LineNumber(node.start_point[0] + 1),
                        end_line=LineNumber(node.end_point[0] + 1),
                        start_byte=ByteOffset(node.start_byte),
                        end_byte=ByteOffset(node.end_byte),
                        code=source_code[node.start_byte : node.end_byte].decode("utf-8"),
                    )
                )

            # Traverse children
            for child in node.children:
                traverse(child, parent_class)

        traverse(root)
        return concepts

    def _extract_generic_concepts(self, root: Node, source_code: bytes) -> list[UniversalConcept]:
        """Extract concepts from C-like languages using common node types."""
        concepts = []

        # Common node types across many languages
        function_types = {
            "function_declaration",
            "function_definition",
            "method_declaration",
            "function_item",  # Rust
            "method_definition",  # Ruby, Java
        }

        class_types = {
            "class_declaration",
            "class_definition",
            "struct_item",
            "impl_item",  # Rust
            "class",  # Ruby
        }

        def traverse(node: Node, parent_class: str | None = None):
            # Function/method nodes
            if node.type in function_types:
                # Try multiple ways to get the name
                name_node = (
                    node.child_by_field_name("name")
                    or node.child_by_field_name("declarator")
                    or node.child_by_field_name("identifier")
                )

                symbol = "anonymous"
                if name_node:
                    if name_node.type == "function_declarator":
                        # C/C++ style - need to dig deeper
                        id_node = name_node.child_by_field_name("declarator")
                        if id_node:
                            symbol = source_code[id_node.start_byte : id_node.end_byte].decode(
                                "utf-8"
                            )
                    else:
                        symbol = source_code[name_node.start_byte : name_node.end_byte].decode(
                            "utf-8"
                        )

                concepts.append(
                    UniversalConcept(
                        concept_type=ConceptType.DEFINITION,
                        chunk_type=ChunkType.METHOD if parent_class else ChunkType.FUNCTION,
                        symbol=symbol,
                        start_line=LineNumber(node.start_point[0] + 1),
                        end_line=LineNumber(node.end_point[0] + 1),
                        start_byte=ByteOffset(node.start_byte),
                        end_byte=ByteOffset(node.end_byte),
                        code=source_code[node.start_byte : node.end_byte].decode("utf-8"),
                        parent_header=parent_class,
                    )
                )

            # Class/struct nodes
            elif node.type in class_types:
                name_node = node.child_by_field_name("name") or node.child_by_field_name(
                    "type_identifier"
                )
                if name_node:
                    symbol = source_code[name_node.start_byte : name_node.end_byte].decode("utf-8")
                    concepts.append(
                        UniversalConcept(
                            concept_type=ConceptType.DEFINITION,
                            chunk_type=ChunkType.CLASS,
                            symbol=symbol,
                            start_line=LineNumber(node.start_point[0] + 1),
                            end_line=LineNumber(node.end_point[0] + 1),
                            start_byte=ByteOffset(node.start_byte),
                            end_byte=ByteOffset(node.end_byte),
                            code=source_code[node.start_byte : node.end_byte].decode("utf-8"),
                        )
                    )
                    # Traverse children with class context
                    for child in node.children:
                        traverse(child, parent_class=symbol)
                    return  # Don't double-traverse

            # Traverse children
            for child in node.children:
                traverse(child, parent_class)

        traverse(root)
        return concepts
