"""Entity extraction for multi-hop code research."""

from dataclasses import dataclass
from typing import Set

from ..core.models import Chunk
from ..core.types import Language, ChunkId
from ..parser.engine import TreeSitterEngine


@dataclass
class Entity:
    """Represents a code entity extracted from a chunk."""

    name: str
    entity_type: str  # "function_call", "class_reference", "import", "attribute"
    source_chunk: ChunkId | None = None
    line_number: int | None = None


class EntityExtractor:
    """Extract code entities from chunks for relationship discovery."""

    def __init__(self):
        """Initialize entity extractor with Tree-sitter engine."""
        self.engine = TreeSitterEngine()

    def extract_from_chunk(self, chunk: Chunk) -> list[Entity]:
        """Extract entities (function calls, imports, class refs) from a chunk.

        Args:
            chunk: Code chunk to analyze

        Returns:
            List of extracted entities
        """
        entities: list[Entity] = []

        # Validate input
        if not chunk.code or not chunk.code.strip():
            return entities

        try:
            # Parse the chunk code
            root = self.engine.parse_code(chunk.code, chunk.language)
            if not root:
                return entities

            # Extract based on language
            if chunk.language == Language.PYTHON:
                entities.extend(self._extract_python_entities(root, chunk))
            elif chunk.language in [Language.JAVASCRIPT, Language.TYPESCRIPT, Language.TSX]:
                entities.extend(self._extract_js_entities(root, chunk))

        except Exception:
            # Silent fail for extraction errors
            pass

        return entities

    def _extract_python_entities(self, root, chunk: Chunk) -> list[Entity]:
        """Extract entities from Python code.

        Args:
            root: Tree-sitter root node
            chunk: Source chunk

        Returns:
            List of entities found
        """
        entities: list[Entity] = []
        seen: Set[str] = set()  # Deduplicate

        # Find function calls
        for node in self._find_nodes_by_type(root, "call"):
            function_node = node.child_by_field_name("function")
            if function_node:
                name = self._get_node_text(function_node, chunk.code)
                if name and name not in seen:
                    entities.append(
                        Entity(
                            name=name,
                            entity_type="function_call",
                            source_chunk=chunk.id,
                            line_number=node.start_point[0] + chunk.start_line,
                        )
                    )
                    seen.add(name)

        # Find imports
        for node in self._find_nodes_by_type(root, "import_statement"):
            name_node = node.child_by_field_name("name")
            if name_node:
                name = self._get_node_text(name_node, chunk.code)
                if name and name not in seen:
                    entities.append(
                        Entity(
                            name=name,
                            entity_type="import",
                            source_chunk=chunk.id,
                            line_number=node.start_point[0] + chunk.start_line,
                        )
                    )
                    seen.add(name)

        # Find from imports
        for node in self._find_nodes_by_type(root, "import_from_statement"):
            # Get module name
            module_node = node.child_by_field_name("module_name")
            if module_node:
                module_name = self._get_node_text(module_node, chunk.code)
                if module_name and module_name not in seen:
                    entities.append(
                        Entity(
                            name=module_name,
                            entity_type="import",
                            source_chunk=chunk.id,
                            line_number=node.start_point[0] + chunk.start_line,
                        )
                    )
                    seen.add(module_name)

        # Find class references (type annotations, base classes)
        for node in self._find_nodes_by_type(root, "type"):
            name = self._get_node_text(node, chunk.code)
            if name and name not in seen and name[0].isupper():  # Classes are capitalized
                entities.append(
                    Entity(
                        name=name,
                        entity_type="class_reference",
                        source_chunk=chunk.id,
                        line_number=node.start_point[0] + chunk.start_line,
                    )
                )
                seen.add(name)

        return entities

    def _extract_js_entities(self, root, chunk: Chunk) -> list[Entity]:
        """Extract entities from JavaScript/TypeScript code.

        Args:
            root: Tree-sitter root node
            chunk: Source chunk

        Returns:
            List of entities found
        """
        entities: list[Entity] = []
        seen: Set[str] = set()

        # Find function calls
        for node in self._find_nodes_by_type(root, "call_expression"):
            function_node = node.child_by_field_name("function")
            if function_node:
                name = self._get_node_text(function_node, chunk.code)
                if name and name not in seen:
                    entities.append(
                        Entity(
                            name=name,
                            entity_type="function_call",
                            source_chunk=chunk.id,
                            line_number=node.start_point[0] + chunk.start_line,
                        )
                    )
                    seen.add(name)

        # Find imports
        for node in self._find_nodes_by_type(root, "import_statement"):
            # Extract module name from import
            source_node = node.child_by_field_name("source")
            if source_node:
                name = self._get_node_text(source_node, chunk.code).strip("\"'")
                if name and name not in seen:
                    entities.append(
                        Entity(
                            name=name,
                            entity_type="import",
                            source_chunk=chunk.id,
                            line_number=node.start_point[0] + chunk.start_line,
                        )
                    )
                    seen.add(name)

        return entities

    def _find_nodes_by_type(self, root, node_type: str) -> list:
        """Recursively find all nodes of a given type.

        Args:
            root: Root node to search from
            node_type: Node type to find

        Returns:
            List of matching nodes
        """
        results = []

        def traverse(node):
            if node.type == node_type:
                results.append(node)
            for child in node.children:
                traverse(child)

        traverse(root)
        return results

    def _get_node_text(self, node, source_code: str) -> str:
        """Get text content of a node.

        Args:
            node: Tree-sitter node
            source_code: Source code string

        Returns:
            Text content of node
        """
        try:
            source_bytes = source_code.encode("utf-8")
            return source_bytes[node.start_byte : node.end_byte].decode("utf-8")
        except Exception:
            return ""
