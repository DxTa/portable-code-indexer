"""Embedding server daemon for cross-repo model sharing."""

from .client import EmbedClient
from .daemon import EmbedDaemon

__all__ = ["EmbedClient", "EmbedDaemon"]
