"""Performance metrics tracking for indexing operations."""

import time
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class PerformanceMetrics:
    """Track performance metrics during indexing."""

    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    files_processed: int = 0
    chunks_created: int = 0
    bytes_processed: int = 0
    errors_count: int = 0

    def finish(self):
        """Mark operation as finished."""
        self.end_time = time.time()

    @property
    def duration(self) -> float:
        """Get operation duration in seconds."""
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def files_per_second(self) -> float:
        """Get files processed per second."""
        duration = self.duration
        return self.files_processed / duration if duration > 0 else 0

    @property
    def chunks_per_second(self) -> float:
        """Get chunks created per second."""
        duration = self.duration
        return self.chunks_created / duration if duration > 0 else 0

    @property
    def mb_per_second(self) -> float:
        """Get MB processed per second."""
        duration = self.duration
        mb = self.bytes_processed / (1024 * 1024)
        return mb / duration if duration > 0 else 0

    def to_dict(self) -> Dict:
        """Convert to dictionary for display."""
        return {
            "duration_seconds": round(self.duration, 2),
            "files_processed": self.files_processed,
            "chunks_created": self.chunks_created,
            "bytes_processed": self.bytes_processed,
            "errors": self.errors_count,
            "files_per_second": round(self.files_per_second, 2),
            "chunks_per_second": round(self.chunks_per_second, 2),
            "mb_per_second": round(self.mb_per_second, 2),
        }

    def __str__(self) -> str:
        """Get human-readable summary."""
        return (
            f"Duration: {self.duration:.2f}s | "
            f"Files: {self.files_processed} ({self.files_per_second:.1f}/s) | "
            f"Chunks: {self.chunks_created} ({self.chunks_per_second:.1f}/s) | "
            f"Throughput: {self.mb_per_second:.2f} MB/s"
        )
