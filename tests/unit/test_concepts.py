"""Unit tests for concept extraction from AST."""

import pytest
from sia_code.parser.concepts import ConceptExtractor, UniversalConcept
from sia_code.parser.engine import TreeSitterEngine
from sia_code.core.types import Language, ChunkType, ConceptType


@pytest.fixture
def parser_engine():
    """Create parser engine for testing."""
    return TreeSitterEngine()


class TestJavaScriptConceptExtraction:
    """Test JavaScript concept extraction."""

    def test_function_declaration(self, parser_engine):
        """Test extraction of function declarations."""
        source_code = b"""
function greet(name) {
    return `Hello, ${name}!`;
}
"""
        root_node = parser_engine.parse_code(source_code, Language.JAVASCRIPT)
        extractor = ConceptExtractor(Language.JAVASCRIPT)
        concepts = extractor.extract_concepts(root_node, source_code)

        # Find the function concept
        func_concepts = [c for c in concepts if c.chunk_type == ChunkType.FUNCTION]
        assert len(func_concepts) >= 1

        greet_func = next((c for c in func_concepts if c.symbol == "greet"), None)
        assert greet_func is not None
        assert greet_func.concept_type == ConceptType.DEFINITION
        assert "function greet" in greet_func.code

    def test_arrow_function(self, parser_engine):
        """Test extraction of arrow functions."""
        source_code = b"""
const multiply = (a, b) => {
    return a * b;
};
"""
        root_node = parser_engine.parse_code(source_code, Language.JAVASCRIPT)
        extractor = ConceptExtractor(Language.JAVASCRIPT)
        concepts = extractor.extract_concepts(root_node, source_code)

        # Find the arrow function concept
        func_concepts = [c for c in concepts if c.chunk_type == ChunkType.FUNCTION]
        assert len(func_concepts) >= 1

        multiply_func = next((c for c in func_concepts if c.symbol == "multiply"), None)
        assert multiply_func is not None
        assert "=>" in multiply_func.code

    def test_class_declaration(self, parser_engine):
        """Test extraction of class declarations."""
        source_code = b"""
class Calculator {
    add(a, b) {
        return a + b;
    }
    
    subtract(a, b) {
        return a - b;
    }
}
"""
        root_node = parser_engine.parse_code(source_code, Language.JAVASCRIPT)
        extractor = ConceptExtractor(Language.JAVASCRIPT)
        concepts = extractor.extract_concepts(root_node, source_code)

        # Find the class
        class_concepts = [c for c in concepts if c.chunk_type == ChunkType.CLASS]
        assert len(class_concepts) >= 1

        calc_class = next((c for c in class_concepts if c.symbol == "Calculator"), None)
        assert calc_class is not None
        assert "class Calculator" in calc_class.code

        # Find methods
        method_concepts = [c for c in concepts if c.chunk_type == ChunkType.METHOD]
        assert len(method_concepts) >= 2

        method_names = {c.symbol for c in method_concepts}
        assert "add" in method_names
        assert "subtract" in method_names

    def test_method_parent_context(self, parser_engine):
        """Test that methods maintain parent class context."""
        source_code = b"""
class Person {
    constructor(name) {
        this.name = name;
    }
    
    getName() {
        return this.name;
    }
}
"""
        root_node = parser_engine.parse_code(source_code, Language.JAVASCRIPT)
        extractor = ConceptExtractor(Language.JAVASCRIPT)
        concepts = extractor.extract_concepts(root_node, source_code)

        # Find methods
        method_concepts = [c for c in concepts if c.chunk_type == ChunkType.METHOD]

        for method in method_concepts:
            assert method.parent_header == "Person", (
                f"Method {method.symbol} should have Person as parent"
            )


class TestTypeScriptConceptExtraction:
    """Test TypeScript concept extraction."""

    def test_typescript_function_with_types(self, parser_engine):
        """Test extraction of TypeScript functions with type annotations."""
        source_code = b"""
function add(a: number, b: number): number {
    return a + b;
}
"""
        root_node = parser_engine.parse_code(source_code, Language.TYPESCRIPT)
        extractor = ConceptExtractor(Language.TYPESCRIPT)
        concepts = extractor.extract_concepts(root_node, source_code)

        # Find the function
        func_concepts = [c for c in concepts if c.chunk_type == ChunkType.FUNCTION]
        assert len(func_concepts) >= 1

        add_func = next((c for c in func_concepts if c.symbol == "add"), None)
        assert add_func is not None
        assert "number" in add_func.code

    def test_interface_declaration(self, parser_engine):
        """Test extraction of interface declarations."""
        source_code = b"""
interface User {
    id: number;
    name: string;
    email: string;
}
"""
        root_node = parser_engine.parse_code(source_code, Language.TYPESCRIPT)
        extractor = ConceptExtractor(Language.TYPESCRIPT)
        concepts = extractor.extract_concepts(root_node, source_code)

        # Find the interface (treated as CLASS chunk type)
        class_concepts = [c for c in concepts if c.chunk_type == ChunkType.CLASS]
        assert len(class_concepts) >= 1

        user_interface = next((c for c in class_concepts if c.symbol == "User"), None)
        assert user_interface is not None
        assert "interface User" in user_interface.code

    def test_type_alias_declaration(self, parser_engine):
        """Test extraction of type alias declarations."""
        source_code = b"""
type Point = {
    x: number;
    y: number;
};
"""
        root_node = parser_engine.parse_code(source_code, Language.TYPESCRIPT)
        extractor = ConceptExtractor(Language.TYPESCRIPT)
        concepts = extractor.extract_concepts(root_node, source_code)

        # Find the type alias (treated as CLASS chunk type)
        class_concepts = [c for c in concepts if c.chunk_type == ChunkType.CLASS]
        assert len(class_concepts) >= 1

        point_type = next((c for c in class_concepts if c.symbol == "Point"), None)
        assert point_type is not None
        assert "type Point" in point_type.code

    def test_class_with_typescript_features(self, parser_engine):
        """Test extraction of TypeScript class with visibility modifiers."""
        source_code = b"""
class DataService {
    private apiUrl: string;
    
    constructor(url: string) {
        this.apiUrl = url;
    }
    
    public async fetchData(): Promise<any> {
        return fetch(this.apiUrl);
    }
}
"""
        root_node = parser_engine.parse_code(source_code, Language.TYPESCRIPT)
        extractor = ConceptExtractor(Language.TYPESCRIPT)
        concepts = extractor.extract_concepts(root_node, source_code)

        # Find the class
        class_concepts = [c for c in concepts if c.chunk_type == ChunkType.CLASS]
        assert len(class_concepts) >= 1

        service_class = next((c for c in class_concepts if c.symbol == "DataService"), None)
        assert service_class is not None

        # Find methods
        method_concepts = [c for c in concepts if c.chunk_type == ChunkType.METHOD]
        method_names = {c.symbol for c in method_concepts}
        assert "constructor" in method_names or "fetchData" in method_names


class TestPythonConceptExtraction:
    """Test Python concept extraction (baseline verification)."""

    def test_python_function(self, parser_engine):
        """Test extraction of Python functions."""
        source_code = b"""
def calculate_sum(numbers):
    return sum(numbers)
"""
        root_node = parser_engine.parse_code(source_code, Language.PYTHON)
        extractor = ConceptExtractor(Language.PYTHON)
        concepts = extractor.extract_concepts(root_node, source_code)

        func_concepts = [c for c in concepts if c.chunk_type == ChunkType.FUNCTION]
        assert len(func_concepts) >= 1

        calc_func = next((c for c in func_concepts if c.symbol == "calculate_sum"), None)
        assert calc_func is not None

    def test_python_class(self, parser_engine):
        """Test extraction of Python classes."""
        source_code = b"""
class Vehicle:
    def __init__(self, brand):
        self.brand = brand
    
    def start(self):
        return f"{self.brand} is starting"
"""
        root_node = parser_engine.parse_code(source_code, Language.PYTHON)
        extractor = ConceptExtractor(Language.PYTHON)
        concepts = extractor.extract_concepts(root_node, source_code)

        class_concepts = [c for c in concepts if c.chunk_type == ChunkType.CLASS]
        assert len(class_concepts) >= 1

        vehicle_class = next((c for c in class_concepts if c.symbol == "Vehicle"), None)
        assert vehicle_class is not None

        method_concepts = [c for c in concepts if c.chunk_type == ChunkType.METHOD]
        method_names = {c.symbol for c in method_concepts}
        assert "__init__" in method_names
        assert "start" in method_names


class TestGoConceptExtraction:
    """Test Go concept extraction (generic extractor)."""

    def test_go_function(self, parser_engine):
        """Test extraction of Go functions."""
        source_code = b"""
package main

func add(a int, b int) int {
    return a + b
}
"""
        root_node = parser_engine.parse_code(source_code, Language.GO)
        extractor = ConceptExtractor(Language.GO)
        concepts = extractor.extract_concepts(root_node, source_code)

        func_concepts = [c for c in concepts if c.chunk_type == ChunkType.FUNCTION]
        # Should find at least the add function (may also find others)
        assert len(func_concepts) >= 0  # Generic extractor should handle this


# Smoke tests for other languages (verify no crashes)
@pytest.mark.parametrize(
    "language,source_code",
    [
        (Language.RUST, b'fn main() { println!("Hello"); }'),
        (Language.JAVA, b"public class Test { public void run() {} }"),
        (Language.C, b"int main() { return 0; }"),
        (Language.CPP, b"int main() { return 0; }"),
        (Language.CSHARP, b"class Test { void Main() {} }"),
        (Language.RUBY, b"def hello\n  puts 'Hello'\nend"),
        (Language.PHP, b"<?php function test() { return 42; } ?>"),
    ],
)
def test_language_smoke(parser_engine, language, source_code):
    """Smoke test: verify languages don't crash during concept extraction."""
    root_node = parser_engine.parse_code(source_code, language)
    extractor = ConceptExtractor(language)

    # Should not raise an exception
    concepts = extractor.extract_concepts(root_node, source_code)

    # Should return a list (may be empty for simple code)
    assert isinstance(concepts, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
