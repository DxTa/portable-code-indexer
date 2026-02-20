"""ChunkHound CLI bridge for Sia search/research commands."""

from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, Literal

from ..config import Config


SearchMode = Literal["regex", "semantic"]


def chunkhound_db_path(sia_dir: Path, config: Config) -> Path:
    """Resolve ChunkHound database path from Sia config."""
    return sia_dir / config.chunkhound.db_filename


def split_chunkhound_command(command: str) -> list[str]:
    """Split configured command string into executable argv."""
    stripped = command.strip() if command else ""
    if not stripped:
        stripped = "uvx chunkhound"
    return shlex.split(stripped)


def resolve_search_mode(config: Config, regex: bool, semantic_only: bool) -> SearchMode:
    """Resolve target search mode from CLI flags and config defaults."""
    if regex:
        return "regex"
    if semantic_only:
        return "semantic"
    return config.chunkhound.default_search_mode


def build_index_command(
    config: Config,
    project_path: Path,
    db_path: Path,
    force_reindex: bool = False,
) -> list[str]:
    """Build chunkhound indexing command."""
    cmd = split_chunkhound_command(config.chunkhound.command)
    cmd.extend(["index", str(project_path), "--db", str(db_path)])
    if config.chunkhound.no_embeddings_for_index:
        cmd.append("--no-embeddings")
    if force_reindex:
        cmd.append("--force-reindex")
    return cmd


def build_search_command(
    config: Config,
    query: str,
    project_path: Path,
    db_path: Path,
    mode: SearchMode,
    limit: int,
) -> list[str]:
    """Build chunkhound search command."""
    cmd = split_chunkhound_command(config.chunkhound.command)
    cmd.extend(
        [
            "search",
            query,
            str(project_path),
            "--db",
            str(db_path),
            "--page-size",
            str(limit),
        ]
    )

    if mode == "regex":
        cmd.append("--regex")
        if config.chunkhound.no_embeddings_for_regex_search:
            cmd.append("--no-embeddings")
    elif mode != "semantic":
        raise ValueError(f"Unsupported search mode: {mode}")

    return cmd


def build_research_command(
    config: Config,
    question: str,
    project_path: Path,
    db_path: Path,
) -> list[str]:
    """Build chunkhound research command."""
    cmd = split_chunkhound_command(config.chunkhound.command)
    cmd.extend(["research", build_research_query(config, question), str(project_path)])
    cmd.extend(["--db", str(db_path)])
    return cmd


def build_research_query(config: Config, question: str) -> str:
    """Apply optional prompt prefix before invoking chunkhound research."""
    prefix = config.chunkhound.research_prompt_prefix.strip()
    if not prefix:
        return question
    return f"{prefix}\n\n{question}"


def run_chunkhound_command(
    command: list[str],
    cwd: Path,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run chunkhound command."""
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=capture_output,
    )


def parse_search_output(output: str, query: str, mode: str) -> dict[str, Any]:
    """Parse chunkhound text search output into Sia-compatible JSON structure."""
    results: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_code_block = False
    code_lines: list[str] = []

    def flush_current() -> None:
        nonlocal current
        if not current:
            return

        file_path = current.get("file_path") or "unknown"
        start_line = int(current.get("start_line") or 1)
        end_line = int(current.get("end_line") or start_line)
        snippet = (current.get("snippet") or "").strip()
        rank = int(current.get("rank") or (len(results) + 1))

        results.append(
            {
                "chunk": {
                    "symbol": Path(file_path).stem,
                    "start_line": start_line,
                    "end_line": end_line,
                    "code": snippet,
                    "chunk_type": "unknown",
                    "language": "unknown",
                    "file_path": file_path,
                    "file_id": None,
                    "id": None,
                    "parent_header": None,
                    "metadata": {"source": "chunkhound-cli"},
                },
                "score": max(0.0, 1.0 - (rank - 1) * 0.01),
                "snippet": snippet or None,
                "highlights": [],
            }
        )
        current = None

    for raw_line in output.splitlines():
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code_block:
                if current is not None:
                    current["snippet"] = "\n".join(code_lines).strip()
                code_lines = []
                in_code_block = False
            else:
                in_code_block = True
                code_lines = []
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        match = re.match(r"^\[(\d+)\]\s+(.+)$", stripped)
        if match:
            flush_current()
            current = {
                "rank": int(match.group(1)),
                "file_path": match.group(2).strip(),
                "start_line": None,
                "end_line": None,
                "snippet": "",
            }
            continue

        if current is not None:
            line_match = re.search(r"Lines\s+(\d+)(?:-(\d+))?", stripped)
            if line_match:
                current["start_line"] = int(line_match.group(1))
                current["end_line"] = int(line_match.group(2) or line_match.group(1))

    flush_current()
    return {"query": query, "mode": mode, "results": results}


def research_needs_llm_fallback(output_text: str) -> bool:
    """Detect known chunkhound LLM setup errors for graceful fallback."""
    lowered = output_text.lower()
    return "configure an llm provider" in lowered or "llm provider setup failed" in lowered
