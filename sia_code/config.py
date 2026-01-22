"""Configuration management for PCI."""

import json
from pathlib import Path

from pydantic import BaseModel, Field


class EmbeddingConfig(BaseModel):
    """Embedding configuration.

    Supported models:
    - OpenAI: "openai-small" (1536d), "openai-large" (3072d) - requires OPENAI_API_KEY
    - HuggingFace/BGE (local, free): "bge-small" (384d), "bge-base" (768d), "bge-large" (1024d)
    - Voyage (code-specific): "voyage-code-3" (1024d) - requires VOYAGE_API_KEY
    - Cohere: "cohere" - requires COHERE_API_KEY
    """

    enabled: bool = True
    provider: str = "openai"  # Deprecated - provider auto-detected from model name
    model: str = "openai-small"  # Model name (see supported models above)
    api_key_env: str = "OPENAI_API_KEY"  # Environment variable for API key
    dimensions: int = 1536  # Embedding dimensions (auto-detected for most models)


class IndexingConfig(BaseModel):
    """Indexing configuration."""

    exclude_patterns: list[str] = Field(
        default_factory=lambda: [
            "node_modules/",
            "__pycache__/",
            ".git/",
            "venv/",
            ".venv/",
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
    vector_weight: float = (
        0.7  # Weight for vector search in hybrid (0.0=lexical only, 1.0=semantic only)
    )
    # Configurable tier boosting for search results
    tier_boost: dict[str, float] = Field(
        default_factory=lambda: {
            "project": 1.0,
            "dependency": 0.7,
            "stdlib": 0.5,
        }
    )
    include_dependencies: bool = True  # Default: deps always included in search


class DependencyConfig(BaseModel):
    """Dependency indexing configuration."""

    enabled: bool = True
    index_stubs: bool = True  # Index .pyi, .d.ts
    # Languages to index deps for (Phase 1: python, typescript only)
    languages: list[str] = Field(default_factory=lambda: ["python", "typescript", "javascript"])


class DocumentationConfig(BaseModel):
    """Documentation linking configuration."""

    enabled: bool = True
    link_to_code: bool = True  # Create doc-to-code links
    patterns: list[str] = Field(default_factory=lambda: ["*.md", "*.txt", "*.rst"])


class AdaptiveConfig(BaseModel):
    """Auto-detected project configuration."""

    auto_detect: bool = True
    detected_languages: list[str] = Field(default_factory=list)
    is_multi_language: bool = False
    search_strategy: str = "weighted"  # "weighted" or "non_dominated"


class Config(BaseModel):
    """Main PCI configuration."""

    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    indexing: IndexingConfig = Field(default_factory=IndexingConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    # New configuration sections
    dependencies: DependencyConfig = Field(default_factory=DependencyConfig)
    documentation: DocumentationConfig = Field(default_factory=DocumentationConfig)
    adaptive: AdaptiveConfig = Field(default_factory=AdaptiveConfig)

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
        return Path(".sia-code/config.json")
