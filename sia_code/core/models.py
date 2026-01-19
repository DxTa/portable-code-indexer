"""Core data models for PCI."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .types import ByteOffset, ChunkId, ChunkType, FileId, FilePath, Language, LineNumber


@dataclass(frozen=True)
class Chunk:
    """Represents a semantic code chunk."""

    symbol: str
    start_line: LineNumber
    end_line: LineNumber
    code: str
    chunk_type: ChunkType
    language: Language
    file_path: FilePath
    file_id: FileId | None = None
    id: ChunkId | None = None
    parent_header: str | None = None
    start_byte: ByteOffset | None = None
    end_byte: ByteOffset | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self):
        """Validate chunk data."""
        if self.start_line < 1:
            raise ValueError(f"start_line must be >= 1, got {self.start_line}")
        if self.end_line < self.start_line:
            raise ValueError(
                f"end_line ({self.end_line}) must be >= start_line ({self.start_line})"
            )
        if not self.code:
            raise ValueError("code cannot be empty")

    @property
    def line_count(self) -> int:
        return self.end_line - self.start_line + 1

    @property
    def char_count(self) -> int:
        return len(self.code.replace(" ", "").replace("\n", "").replace("\t", ""))

    def contains_line(self, line: int) -> bool:
        return self.start_line <= line <= self.end_line

    def overlaps_with(self, other: "Chunk") -> bool:
        return not (self.end_line < other.start_line or self.start_line > other.end_line)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "code": self.code,
            "chunk_type": self.chunk_type.value,
            "language": self.language.value,
            "file_path": str(self.file_path),
            "file_id": self.file_id,
            "id": self.id,
            "parent_header": self.parent_header,
            "metadata": self.metadata,
        }

    def with_metadata(self, extra: dict[str, Any]) -> "Chunk":
        """Return a new Chunk with additional metadata merged.

        Since Chunk is frozen, this creates a new instance.

        Args:
            extra: Additional metadata to merge with existing metadata

        Returns:
            New Chunk instance with merged metadata
        """
        merged = {**self.metadata, **extra}
        return Chunk(
            symbol=self.symbol,
            start_line=self.start_line,
            end_line=self.end_line,
            code=self.code,
            chunk_type=self.chunk_type,
            language=self.language,
            file_path=self.file_path,
            file_id=self.file_id,
            id=self.id,
            parent_header=self.parent_header,
            start_byte=self.start_byte,
            end_byte=self.end_byte,
            metadata=merged,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


@dataclass(frozen=True)
class File:
    """Represents a source code file."""

    path: FilePath
    language: Language
    size_bytes: int
    mtime: float
    id: FileId | None = None

    @classmethod
    def from_path(cls, path: Path) -> "File":
        stat = path.stat()
        language = Language.from_extension(path.suffix)
        return cls(
            path=FilePath(str(path)),
            language=language,
            size_bytes=stat.st_size,
            mtime=stat.st_mtime,
        )


@dataclass
class SearchResult:
    """Represents a search result."""

    chunk: Chunk
    score: float
    snippet: str | None = None
    highlights: list[tuple[int, int]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert search result to dictionary for JSON serialization."""
        return {
            "chunk": self.chunk.to_dict(),
            "score": self.score,
            "snippet": self.snippet,
            "highlights": self.highlights,
        }


@dataclass
class IndexStats:
    """Statistics about the code index."""

    total_files: int = 0
    total_chunks: int = 0
    total_size_bytes: int = 0
    languages: dict[Language, int] = field(default_factory=dict)
    last_indexed: datetime | None = None
