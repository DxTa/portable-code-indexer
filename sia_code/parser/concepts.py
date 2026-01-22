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
        """Extract Python-specific concepts with full coverage."""
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

        # Ensure full coverage by filling gaps (matches JS/TS behavior)
        concepts = self._fill_coverage_gaps(concepts, source_code)

        return concepts

    def _fill_coverage_gaps(
        self, concepts: list[UniversalConcept], source_code: bytes
    ) -> list[UniversalConcept]:
        """Fill gaps in coverage to ensure 100% of file is chunked.

        Args:
            concepts: Existing extracted concepts
            source_code: Original source code

        Returns:
            Concepts with gaps filled
        """
        if not concepts:
            # No concepts extracted - create one chunk for entire file
            lines = source_code.decode("utf-8", errors="ignore").split("\n")
            total_lines = len(lines)

            if total_lines > 0:
                return [
                    UniversalConcept(
                        concept_type=ConceptType.DEFINITION,
                        chunk_type=ChunkType.UNKNOWN,
                        symbol="module_content",
                        start_line=LineNumber(1),
                        end_line=LineNumber(total_lines),
                        start_byte=ByteOffset(0),
                        end_byte=ByteOffset(len(source_code)),
                        code=source_code.decode("utf-8", errors="ignore"),
                    )
                ]
            return []

        # Sort concepts by start line
        sorted_concepts = sorted(concepts, key=lambda c: c.start_line)

        # Get total lines in file
        lines = source_code.decode("utf-8", errors="ignore").split("\n")
        total_lines = len(lines)

        # Find gaps and create concepts for uncovered ranges
        filled_concepts = []
        current_line = 1

        for concept in sorted_concepts:
            # Check if there's a gap before this concept
            if current_line < concept.start_line:
                # Create concept for the gap
                gap_start_line = current_line
                gap_end_line = concept.start_line - 1

                # Extract code for the gap
                gap_code_lines = lines[gap_start_line - 1 : gap_end_line]
                gap_code = "\n".join(gap_code_lines)

                # Only create gap chunk if it has non-whitespace content
                if gap_code.strip():
                    # Calculate byte offsets (approximate)
                    gap_start_byte = sum(len(line) + 1 for line in lines[: gap_start_line - 1])
                    gap_end_byte = sum(len(line) + 1 for line in lines[:gap_end_line])

                    filled_concepts.append(
                        UniversalConcept(
                            concept_type=ConceptType.DEFINITION,
                            chunk_type=ChunkType.UNKNOWN,
                            symbol=f"module_gap_{gap_start_line}_{gap_end_line}",
                            start_line=LineNumber(gap_start_line),
                            end_line=LineNumber(gap_end_line),
                            start_byte=ByteOffset(gap_start_byte),
                            end_byte=ByteOffset(gap_end_byte),
                            code=gap_code,
                        )
                    )

            # Add the concept itself
            filled_concepts.append(concept)

            # Update current line to after this concept
            current_line = max(current_line, concept.end_line + 1)

        # Check if there's a gap at the end of the file
        if current_line <= total_lines:
            gap_start_line = current_line
            gap_end_line = total_lines

            gap_code_lines = lines[gap_start_line - 1 : gap_end_line]
            gap_code = "\n".join(gap_code_lines)

            if gap_code.strip():
                gap_start_byte = sum(len(line) + 1 for line in lines[: gap_start_line - 1])
                gap_end_byte = len(source_code)

                filled_concepts.append(
                    UniversalConcept(
                        concept_type=ConceptType.DEFINITION,
                        chunk_type=ChunkType.UNKNOWN,
                        symbol=f"module_gap_{gap_start_line}_{gap_end_line}",
                        start_line=LineNumber(gap_start_line),
                        end_line=LineNumber(gap_end_line),
                        start_byte=ByteOffset(gap_start_byte),
                        end_byte=ByteOffset(gap_end_byte),
                        code=gap_code,
                    )
                )

        return filled_concepts

    def _extract_javascript_concepts(
        self, root: Node, source_code: bytes
    ) -> list[UniversalConcept]:
        """Extract JavaScript/TypeScript-specific concepts."""
        concepts = []

        def traverse(node: Node, parent_class: str | None = None):
            # Function declarations: function foo() {}
            if node.type == "function_declaration":
                name_node = node.child_by_field_name("name")
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

            # Arrow functions and function expressions: const foo = () => {}
            elif node.type in ("arrow_function", "function_expression", "function"):
                # Try to find the parent variable declarator to get the name
                parent = node.parent
                symbol = "anonymous"
                if parent and parent.type == "variable_declarator":
                    name_node = parent.child_by_field_name("name")
                    if name_node:
                        symbol = source_code[name_node.start_byte : name_node.end_byte].decode(
                            "utf-8"
                        )

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
                    # Traverse children with class context
                    for child in node.children:
                        traverse(child, parent_class=symbol)
                    return  # Don't traverse again

            # Method definitions (inside classes)
            elif node.type in ("method_definition", "public_field_definition"):
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

            # TypeScript-specific: interface declarations
            elif node.type == "interface_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbol = source_code[name_node.start_byte : name_node.end_byte].decode("utf-8")
                    concepts.append(
                        UniversalConcept(
                            concept_type=ConceptType.DEFINITION,
                            chunk_type=ChunkType.CLASS,  # Treat interfaces like classes
                            symbol=symbol,
                            start_line=LineNumber(node.start_point[0] + 1),
                            end_line=LineNumber(node.end_point[0] + 1),
                            start_byte=ByteOffset(node.start_byte),
                            end_byte=ByteOffset(node.end_byte),
                            code=source_code[node.start_byte : node.end_byte].decode("utf-8"),
                        )
                    )

            # TypeScript-specific: type alias declarations
            elif node.type == "type_alias_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbol = source_code[name_node.start_byte : name_node.end_byte].decode("utf-8")
                    concepts.append(
                        UniversalConcept(
                            concept_type=ConceptType.DEFINITION,
                            chunk_type=ChunkType.CLASS,  # Treat type aliases like classes
                            symbol=symbol,
                            start_line=LineNumber(node.start_point[0] + 1),
                            end_line=LineNumber(node.end_point[0] + 1),
                            start_byte=ByteOffset(node.start_byte),
                            end_byte=ByteOffset(node.end_byte),
                            code=source_code[node.start_byte : node.end_byte].decode("utf-8"),
                        )
                    )

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

        # NEW: Ensure full coverage by filling gaps
        concepts = self._fill_coverage_gaps(concepts, source_code)

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
