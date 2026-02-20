"""Unit tests for ChunkHound CLI bridge helpers."""

from pathlib import Path

from sia_code.config import Config
from sia_code.search.chunkhound_cli import build_search_command, parse_search_output


def test_build_search_command_regex_uses_no_embeddings_by_default():
    config = Config()

    cmd = build_search_command(
        config=config,
        query="auth",
        project_path=Path("."),
        db_path=Path("/tmp/chunkhound.db"),
        mode="regex",
        limit=7,
    )

    assert cmd[:3] == ["uvx", "chunkhound", "search"]
    assert "--regex" in cmd
    assert "--no-embeddings" in cmd
    assert "--page-size" in cmd
    assert "7" in cmd


def test_parse_search_output_extracts_file_and_lines():
    output = """=== Regex Search Results ===

[1] src/auth/service.py
[INFO] [blue][INFO][/blue] Lines 12-18
```python
def authenticate_user(token: str) -> bool:
    return token != ""
```
"""

    parsed = parse_search_output(output=output, query="authenticate", mode="regex")

    assert parsed["query"] == "authenticate"
    assert parsed["mode"] == "regex"
    assert len(parsed["results"]) == 1
    first = parsed["results"][0]
    assert first["chunk"]["file_path"] == "src/auth/service.py"
    assert first["chunk"]["start_line"] == 12
    assert first["chunk"]["end_line"] == 18
    assert "authenticate_user" in (first["snippet"] or "")
