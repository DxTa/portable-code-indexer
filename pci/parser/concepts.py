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

    def _extract_javascript_concepts(self, root: Node, source_code: bytes) -> list[UniversalConcept]:
        """Extract JavaScript/TypeScript concepts."""
        concepts = []

        def traverse(node: Node, parent_class: str | None = None):
            # Function declarations
            if node.type in ("function_declaration", "arrow_function", "function"):
                name_node = node.child_by_field_name("name")
                symbol = "anonymous"
                if name_node:
                    symbol = source_code[name_node.start_byte : name_node.end_byte].decode("utf-8")
                
                concepts.append(
                    UniversalConcept(
                        concept_type=ConceptType.DEFINITION,
                        chunk_type=ChunkType.FUNCTION,
                        symbol=symbol,
                        start_line=LineNumber(node.start_point[0] + 1),
                        end_line=LineNumber(node.end_point[0] + 1),
                        start_byte=ByteOffset(node.start_byte),
                        end_byte=ByteOffset(node.end_byte),
                        code=source_code[node.start_byte : node.end_byte].decode("utf-8"),
                        parent_header=parent_class,
                    )
                )

            # Class declarations
            elif node.type == "class_declaration":
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

            # Traverse children
            for child in node.children:
                traverse(child, parent_class)

        traverse(root)
        return concepts
