"""Configuration management for PCI."""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class EmbeddingConfig(BaseModel):
    """Embedding configuration."""

    enabled: bool = True
    provider: str = "openai"  # "openai", "ollama", or "local"
    model: str = "openai-small"  # "openai-small", "openai-large", or "bge-small"
    api_key_env: str = "OPENAI_API_KEY"  # Environment variable for API key
    dimensions: int = 1536  # Embedding dimensions (1536 for openai-small, 3072 for openai-large)


class IndexingConfig(BaseModel):
    """Indexing configuration."""

    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "node_modules/",
            "__pycache__/",
            ".git/",
            "*.pyc",
            "*.pyo",
            "*.so",
            "*.dylib",
            ".pci/",
        ]
    )
    include_patterns: list[str] = Field(default_factory=lambda: ["**/*"])
    max_file_size_mb: int = 5


class ChunkingConfig(BaseModel):
    """Chunking configuration."""

    max_chunk_size: int = 1200
    min_chunk_size: int = 50
    merge_threshold: float = 0.8
    greedy_merge: bool = True


class SearchConfig(BaseModel):
    """Search configuration."""

    default_limit: int = 10
    multi_hop_enabled: bool = True
    max_hops: int = 2


class Config(BaseModel):
    """Main PCI configuration."""

    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    indexing: IndexingConfig = Field(default_factory=IndexingConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)

    @classmethod
    def load(cls, path: Path) -> "Config":
        """Load configuration from JSON file."""
        if not path.exists():
            return cls()
        with open(path) as f:
            data = json.load(f)
        return cls(**data)

    def save(self, path: Path) -> None:
        """Save configuration to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.model_dump(), f, indent=2)

    @classmethod
    def get_default_config_path(cls) -> Path:
        """Get default configuration file path."""
        return Path(".pci/config.json")
