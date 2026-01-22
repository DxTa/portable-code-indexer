"""cAST-based code chunking algorithm."""

from dataclasses import dataclass
from pathlib import Path

from .concepts import ConceptExtractor, UniversalConcept
from .engine import TreeSitterEngine
from ..core.models import Chunk
from ..core.types import FilePath, Language, LineNumber


@dataclass
class CASTConfig:
    """Configuration for cAST algorithm."""

    max_chunk_size: int = 4000  # Non-whitespace characters (optimized for fewer chunks)
    min_chunk_size: int = 200  # Increased to avoid tiny fragments
    merge_threshold: float = 0.9  # More aggressive merging
    greedy_merge: bool = True


class CASTChunker:
    """Semantic code chunker using cAST algorithm."""

    def __init__(self, config: CASTConfig | None = None):
        """Initialize chunker.

        Args:
            config: Chunking configuration
        """
        self.config = config or CASTConfig()
        self.engine = TreeSitterEngine()

    def chunk_file(self, file_path: Path, language: Language) -> list[Chunk]:
        """Chunk a source file using cAST algorithm.

        Args:
            file_path: Path to source file
            language: Programming language

        Returns:
            List of code chunks
        """
        # Parse file
        root = self.engine.parse_file(file_path, language)
        if not root:
            return []

        # Extract concepts
        with open(file_path, "rb") as f:
            source_code = f.read()

        # Skip empty files
        if not source_code or len(source_code.strip()) == 0:
            return []

        extractor = ConceptExtractor(language)
        concepts = extractor.extract_concepts(root, source_code)

        # Convert concepts to chunks
        chunks = self._concepts_to_chunks(concepts, file_path, language)

        # Apply cAST algorithm
        chunks = self._apply_cast_algorithm(chunks)

        return chunks

    def _concepts_to_chunks(
        self, concepts: list[UniversalConcept], file_path: Path, language: Language
    ) -> list[Chunk]:
        """Convert concepts to chunks."""
        chunks = []
        for concept in concepts:
            # Skip concepts with empty code
            if not concept.code or not concept.code.strip():
                continue
            chunks.append(
                Chunk(
                    symbol=concept.symbol,
                    start_line=concept.start_line,
                    end_line=concept.end_line,
                    code=concept.code,
                    chunk_type=concept.chunk_type,
                    language=language,
                    file_path=FilePath(str(file_path)),
                    parent_header=concept.parent_header,
                    start_byte=concept.start_byte,
                    end_byte=concept.end_byte,
                    metadata=concept.metadata or {},
                )
            )
        return chunks

    def _apply_cast_algorithm(self, chunks: list[Chunk]) -> list[Chunk]:
        """Apply cAST split-merge algorithm.

        Algorithm:
        1. Split oversized chunks
        2. Greedy merge small adjacent chunks
        3. Deduplicate
        """
        if not chunks:
            return []

        # Step 1: Split oversized chunks
        processed_chunks = []
        for chunk in chunks:
            if self._chunk_size(chunk) > self.config.max_chunk_size:
                processed_chunks.extend(self._split_chunk(chunk))
            else:
                processed_chunks.append(chunk)

        # Step 2: Greedy merge small chunks
        if self.config.greedy_merge:
            processed_chunks = self._greedy_merge(processed_chunks)

        # Step 3: Deduplicate
        processed_chunks = self._deduplicate(processed_chunks)

        return processed_chunks

    def _chunk_size(self, chunk: Chunk) -> int:
        """Calculate chunk size (non-whitespace characters)."""
        return chunk.char_count

    def _split_chunk(self, chunk: Chunk) -> list[Chunk]:
        """Split an oversized chunk at logical boundaries.

        Simple implementation: split by lines, tracking absolute line numbers.
        """
        lines = chunk.code.split("\n")
        target_size = self.config.max_chunk_size

        sub_chunks = []
        current_lines = []
        current_size = 0
        # Track start index within lines array (0-based)
        chunk_start_idx = 0

        for i, line in enumerate(lines):
            line_size = len(line.replace(" ", "").replace("\t", ""))

            if current_size + line_size > target_size and current_lines:
                # Create chunk from accumulated lines
                code = "\n".join(current_lines)
                # Calculate absolute line numbers from chunk's start + offset in lines array
                abs_start = chunk.start_line + chunk_start_idx
                abs_end = abs_start + len(current_lines) - 1
                sub_chunks.append(
                    Chunk(
                        symbol=f"{chunk.symbol}_part{len(sub_chunks) + 1}",
                        start_line=LineNumber(abs_start),
                        end_line=LineNumber(abs_end),
                        code=code,
                        chunk_type=chunk.chunk_type,
                        language=chunk.language,
                        file_path=chunk.file_path,
                        parent_header=chunk.parent_header,
                    )
                )
                # Reset for next chunk - new chunk starts at current line index
                chunk_start_idx = i
                current_lines = [line]
                current_size = line_size
            else:
                current_lines.append(line)
                current_size += line_size

        # Add remaining lines
        if current_lines:
            code = "\n".join(current_lines)
            abs_start = chunk.start_line + chunk_start_idx
            abs_end = abs_start + len(current_lines) - 1
            sub_chunks.append(
                Chunk(
                    symbol=f"{chunk.symbol}_part{len(sub_chunks) + 1}",
                    start_line=LineNumber(abs_start),
                    end_line=LineNumber(abs_end),
                    code=code,
                    chunk_type=chunk.chunk_type,
                    language=chunk.language,
                    file_path=chunk.file_path,
                    parent_header=chunk.parent_header,
                )
            )

        return sub_chunks if sub_chunks else [chunk]

    def _greedy_merge(self, chunks: list[Chunk]) -> list[Chunk]:
        """Greedily merge small adjacent chunks."""
        if len(chunks) <= 1:
            return chunks

        # Sort chunks by file path and start line to ensure correct merge order
        sorted_chunks = sorted(chunks, key=lambda c: (c.file_path, c.start_line))
        merged = [sorted_chunks[0]]

        for chunk in sorted_chunks[1:]:
            last_chunk = merged[-1]

            # Check if chunks are adjacent and both small
            if (
                last_chunk.file_path == chunk.file_path
                and last_chunk.end_line + 1 >= chunk.start_line
                and self._chunk_size(last_chunk)
                < self.config.max_chunk_size * self.config.merge_threshold
                and self._chunk_size(chunk)
                < self.config.max_chunk_size * self.config.merge_threshold
            ):
                # Merge
                merged_code = last_chunk.code + "\n" + chunk.code
                merged_chunk = Chunk(
                    symbol=f"{last_chunk.symbol}+{chunk.symbol}",
                    start_line=last_chunk.start_line,
                    end_line=chunk.end_line,
                    code=merged_code,
                    chunk_type=last_chunk.chunk_type,
                    language=last_chunk.language,
                    file_path=last_chunk.file_path,
                )
                merged[-1] = merged_chunk
            else:
                merged.append(chunk)

        return merged

    def _deduplicate(self, chunks: list[Chunk]) -> list[Chunk]:
        """Remove duplicate chunks based on content."""
        seen_codes = set()
        unique_chunks = []

        for chunk in chunks:
            # Use normalized code as key
            code_key = chunk.code.strip()
            if code_key not in seen_codes:
                seen_codes.add(code_key)
                unique_chunks.append(chunk)

        return unique_chunks
