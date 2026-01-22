#!/usr/bin/env python3
"""
Test script to identify what triggers memvid pagination.

This test tries various configurations to reproduce the pagination issue
where memvid creates duplicate frames with #page-N URI suffixes.
"""

import os
import tempfile
from pathlib import Path
from memvid_sdk import create, use
from memvid_sdk.embeddings import HuggingFaceEmbeddings


def create_test_index(name: str, cleanup: bool = True):
    """Create a temporary test index."""
    test_path = f"/tmp/test_pagination_{name}.mv2"
    if os.path.exists(test_path):
        os.remove(test_path)
    return test_path


def check_for_pagination(index_path: str, expected_count: int) -> dict:
    """Check if pagination occurred in the index."""
    mem = use("basic", index_path, mode="open")
    stats = mem.stats()

    # Search for content to find actual URIs
    results = mem.find(query="test", mode="lex", k=1000)

    paginated_uris = []
    all_uris = []

    if "hits" in results:
        for hit in results["hits"]:
            uri = hit.get("uri", "")
            all_uris.append(uri)
            if "#page-" in uri:
                paginated_uris.append(uri)

    return {
        "frame_count": stats["frame_count"],
        "expected": expected_count,
        "match": stats["frame_count"] == expected_count,
        "paginated_uris": len(paginated_uris),
        "unique_uris": len(set(all_uris)),
        "has_pagination": len(paginated_uris) > 0,
    }


def test_simple_docs():
    """Test 1: Simple documents without embeddings."""
    print("=" * 80)
    print("TEST 1: Simple documents (no embeddings)")
    print("=" * 80)

    test_path = create_test_index("simple")
    mem = create(test_path, enable_vec=True, enable_lex=True)

    docs = []
    for i in range(100):
        docs.append(
            {
                "title": f"Doc {i}",
                "label": "test",
                "text": f"This is test document number {i} with some content.",
                "uri": f"test://doc/{i}",
            }
        )

    frame_ids = mem.put_many(docs, opts={"enable_embedding": False})
    mem.seal()

    result = check_for_pagination(test_path, 100)
    print(f"Expected: {result['expected']}, Got: {result['frame_count']}")
    print(f"Paginated URIs: {result['paginated_uris']}")
    print(
        f"Result: {'✅ PASS' if not result['has_pagination'] else '❌ FAIL - Pagination detected'}"
    )
    print()

    os.remove(test_path)
    return result


def test_with_bge_embeddings():
    """Test 2: Documents with BGE embeddings."""
    print("=" * 80)
    print("TEST 2: Documents with BGE embeddings")
    print("=" * 80)

    test_path = create_test_index("bge")
    mem = create(test_path, enable_vec=True, enable_lex=True)

    embedder = HuggingFaceEmbeddings(model="BAAI/bge-small-en-v1.5")

    docs = []
    for i in range(100):
        docs.append(
            {
                "title": f"Doc {i}",
                "label": "test",
                "text": f"This is test document number {i} with some content for embedding.",
                "uri": f"test://doc/{i}",
            }
        )

    frame_ids = mem.put_many(docs, embedder=embedder)
    mem.seal()

    result = check_for_pagination(test_path, 100)
    print(f"Expected: {result['expected']}, Got: {result['frame_count']}")
    print(f"Paginated URIs: {result['paginated_uris']}")
    print(
        f"Result: {'✅ PASS' if not result['has_pagination'] else '❌ FAIL - Pagination detected'}"
    )
    print()

    os.remove(test_path)
    return result


def test_large_text():
    """Test 3: Documents with large text (like code chunks)."""
    print("=" * 80)
    print("TEST 3: Large text documents (simulating code chunks)")
    print("=" * 80)

    test_path = create_test_index("large")
    mem = create(test_path, enable_vec=True, enable_lex=True)

    embedder = HuggingFaceEmbeddings(model="BAAI/bge-small-en-v1.5")

    # Create larger text similar to actual code chunks
    code_template = """
def test_function_{i}(self, config):
    '''Test function for processing data.
    
    Args:
        config: Configuration dictionary
    
    Returns:
        Processed results
    '''
    self.config = config
    results = []
    
    for item in range(100):
        if item % 2 == 0:
            results.append(item * {i})
        else:
            results.append(item + {i})
    
    return results

class TestClass{i}:
    def __init__(self, value):
        self.value = value
    
    def process(self, data):
        return [x * self.value for x in data]
"""

    docs = []
    for i in range(100):
        docs.append(
            {
                "title": f"test_function_{i}",
                "label": "function",
                "text": code_template.format(i=i),
                "uri": f"test://file.py#{i * 20}-{i * 20 + 30}",
                "metadata": {"file_path": "/test/file.py", "language": "python"},
            }
        )

    frame_ids = mem.put_many(docs, embedder=embedder)
    mem.seal()

    result = check_for_pagination(test_path, 100)
    print(f"Expected: {result['expected']}, Got: {result['frame_count']}")
    print(f"Paginated URIs: {result['paginated_uris']}")
    print(
        f"Result: {'✅ PASS' if not result['has_pagination'] else '❌ FAIL - Pagination detected'}"
    )
    print()

    os.remove(test_path)
    return result


def test_multiple_batches():
    """Test 4: Multiple put_many() calls (simulating real indexing)."""
    print("=" * 80)
    print("TEST 4: Multiple batches (simulating real indexing)")
    print("=" * 80)

    test_path = create_test_index("batches")
    mem = create(test_path, enable_vec=True, enable_lex=True)

    embedder = HuggingFaceEmbeddings(model="BAAI/bge-small-en-v1.5")

    total_docs = 0

    # Simulate indexing multiple files with batches
    for batch_num in range(10):
        docs = []
        for i in range(10):
            doc_id = batch_num * 10 + i
            docs.append(
                {
                    "title": f"Doc {doc_id}",
                    "label": "test",
                    "text": f"Batch {batch_num}, document {i} with content for testing.",
                    "uri": f"test://batch{batch_num}/doc{i}",
                }
            )

        frame_ids = mem.put_many(docs, embedder=embedder)
        total_docs += len(docs)

    mem.seal()

    result = check_for_pagination(test_path, total_docs)
    print(f"Expected: {result['expected']}, Got: {result['frame_count']}")
    print(f"Paginated URIs: {result['paginated_uris']}")
    print(
        f"Result: {'✅ PASS' if not result['has_pagination'] else '❌ FAIL - Pagination detected'}"
    )
    print()

    os.remove(test_path)
    return result


def test_varied_text_sizes():
    """Test 5: Documents with widely varying text sizes."""
    print("=" * 80)
    print("TEST 5: Varied text sizes (small to large)")
    print("=" * 80)

    test_path = create_test_index("varied")
    mem = create(test_path, enable_vec=True, enable_lex=True)

    embedder = HuggingFaceEmbeddings(model="BAAI/bge-small-en-v1.5")

    docs = []
    for i in range(100):
        # Create texts of varying sizes
        if i < 20:
            text = f"Small doc {i}"
        elif i < 50:
            text = f"Medium document {i} with more content. " * 10
        else:
            text = f"Large document {i} with lots of content. " * 50

        docs.append(
            {
                "title": f"Doc {i}",
                "label": "test",
                "text": text,
                "uri": f"test://doc/{i}",
            }
        )

    frame_ids = mem.put_many(docs, embedder=embedder)
    mem.seal()

    result = check_for_pagination(test_path, 100)
    print(f"Expected: {result['expected']}, Got: {result['frame_count']}")
    print(f"Paginated URIs: {result['paginated_uris']}")
    print(
        f"Result: {'✅ PASS' if not result['has_pagination'] else '❌ FAIL - Pagination detected'}"
    )
    print()

    os.remove(test_path)
    return result


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("MEMVID PAGINATION INVESTIGATION")
    print("=" * 80)
    print()

    results = []

    try:
        results.append(("Simple docs (no embedding)", test_simple_docs()))
        results.append(("BGE embeddings", test_with_bge_embeddings()))
        results.append(("Large text (code-like)", test_large_text()))
        results.append(("Multiple batches", test_multiple_batches()))
        results.append(("Varied text sizes", test_varied_text_sizes()))
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback

        traceback.print_exc()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()

    for test_name, result in results:
        status = (
            "✅ No pagination"
            if not result["has_pagination"]
            else f"❌ Pagination: {result['paginated_uris']} URIs"
        )
        frame_diff = result["frame_count"] - result["expected"]
        print(f"{test_name:30s}: {status} (diff: {frame_diff:+d})")

    print()

    # Identify pattern
    pagination_tests = [r for _, r in results if r["has_pagination"]]
    if pagination_tests:
        print("⚠️  PAGINATION DETECTED IN THESE SCENARIOS")
        print("   Further investigation needed to identify root cause")
    else:
        print("✅ NO PAGINATION DETECTED")
        print("   May need to test with actual diffusers repo to reproduce")


if __name__ == "__main__":
    main()
