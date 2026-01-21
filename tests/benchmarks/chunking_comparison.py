"""Chunking strategy comparison for benchmark evaluation.

Compares sia-code's AST-aware chunking against:
- Fixed-line chunking (baseline, like ChunkHound's line-based)
- Fixed-token chunking
- Future: cAST (contextual AST) implementation

Enables measuring impact of chunking on retrieval quality.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Protocol
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sia_code.parser.chunker import CodeChunker
from sia_code.core.models import Chunk
from sia_code.core.types import Language, ChunkType

logger = logging.getLogger(__name__)


class ChunkingStrategy(Protocol):
    """Protocol for chunking strategies."""

    def chunk_code(self, code: str, file_path: str, language: Language) -> List[Chunk]:
        """Chunk code into retrievable units."""
        ...


@dataclass
class FixedLineChunker:
    """Baseline: Fixed number of lines per chunk."""

    lines_per_chunk: int = 50

    def chunk_code(self, code: str, file_path: str, language: Language) -> List[Chunk]:
        """Chunk code by fixed line count.

        Args:
            code: Source code to chunk
            file_path: Path to source file
            language: Programming language

        Returns:
            List of chunks (fixed line boundaries)
        """
        lines = code.split("\n")
        chunks = []

        for i in range(0, len(lines), self.lines_per_chunk):
            chunk_lines = lines[i : i + self.lines_per_chunk]
            chunk_code = "\n".join(chunk_lines)

            chunks.append(
                Chunk(
                    symbol=f"{Path(file_path).name}:L{i + 1}-{i + len(chunk_lines)}",
                    start_line=i + 1,
                    end_line=i + len(chunk_lines),
                    code=chunk_code,
                    chunk_type=ChunkType.UNKNOWN,
                    language=language,
                    file_path=file_path,
                    parent_header=None,
                )
            )

        return chunks


@dataclass
class FixedTokenChunker:
    """Fixed number of tokens per chunk (approximated by characters)."""

    chars_per_chunk: int = 512

    def chunk_code(self, code: str, file_path: str, language: Language) -> List[Chunk]:
        """Chunk code by approximate token count.

        Args:
            code: Source code to chunk
            file_path: Path to source file
            language: Programming language

        Returns:
            List of chunks (fixed character boundaries)
        """
        chunks = []
        lines = code.split("\n")

        current_chunk = []
        current_chars = 0
        start_line = 1

        for line_num, line in enumerate(lines, 1):
            line_len = len(line) + 1  # +1 for newline

            if current_chars + line_len > self.chars_per_chunk and current_chunk:
                # Finalize current chunk
                chunk_code = "\n".join(current_chunk)
                chunks.append(
                    Chunk(
                        symbol=f"{Path(file_path).name}:L{start_line}-{line_num - 1}",
                        start_line=start_line,
                        end_line=line_num - 1,
                        code=chunk_code,
                        chunk_type=ChunkType.UNKNOWN,
                        language=language,
                        file_path=file_path,
                        parent_header=None,
                    )
                )

                # Start new chunk
                current_chunk = [line]
                current_chars = line_len
                start_line = line_num
            else:
                current_chunk.append(line)
                current_chars += line_len

        # Final chunk
        if current_chunk:
            chunk_code = "\n".join(current_chunk)
            chunks.append(
                Chunk(
                    symbol=f"{Path(file_path).name}:L{start_line}-{len(lines)}",
                    start_line=start_line,
                    end_line=len(lines),
                    code=chunk_code,
                    chunk_type=ChunkType.UNKNOWN,
                    language=language,
                    file_path=file_path,
                    parent_header=None,
                )
            )

        return chunks


class SiaCodeASTChunker:
    """sia-code's current tree-sitter AST-aware chunking."""

    def __init__(self):
        self.chunker = CodeChunker()

    def chunk_code(self, code: str, file_path: str, language: Language) -> List[Chunk]:
        """Chunk code using AST-aware approach.

        Args:
            code: Source code to chunk
            file_path: Path to source file
            language: Programming language

        Returns:
            List of chunks (AST-aware boundaries)
        """
        return self.chunker.chunk_file_content(code, file_path, language)


def get_chunking_strategies() -> Dict[str, ChunkingStrategy]:
    """Get all available chunking strategies.

    Returns:
        Dict mapping strategy name to chunker instance
    """
    return {
        "sia-code-ast": SiaCodeASTChunker(),
        "fixed-line-50": FixedLineChunker(lines_per_chunk=50),
        "fixed-line-100": FixedLineChunker(lines_per_chunk=100),
        "fixed-token-512": FixedTokenChunker(chars_per_chunk=512),
        "fixed-token-1024": FixedTokenChunker(chars_per_chunk=1024),
    }


def compare_chunk_stats(
    strategies: Dict[str, ChunkingStrategy], code: str, language: Language
) -> Dict[str, Dict]:
    """Compare chunking statistics across strategies.

    Args:
        strategies: Dict of strategy name to chunker
        code: Source code to analyze
        language: Programming language

    Returns:
        Dict mapping strategy name to stats
    """
    stats = {}

    for name, chunker in strategies.items():
        chunks = chunker.chunk_code(code, "test.py", language)

        chunk_sizes = [len(c.code) for c in chunks]
        stats[name] = {
            "num_chunks": len(chunks),
            "avg_chunk_size": sum(chunk_sizes) / len(chunks) if chunks else 0,
            "min_chunk_size": min(chunk_sizes) if chunks else 0,
            "max_chunk_size": max(chunk_sizes) if chunks else 0,
        }

    return stats
