"""Protocol for embedding server communication."""

import json
from typing import Any


class Message:
    """Base message class for socket communication."""

    @staticmethod
    def encode(data: dict) -> bytes:
        """Encode message to JSON bytes with newline delimiter."""
        return (json.dumps(data) + "\n").encode("utf-8")

    @staticmethod
    def decode(data: bytes) -> dict:
        """Decode JSON bytes to message dict."""
        return json.loads(data.decode("utf-8").strip())


class EmbedRequest:
    """Embedding request message."""

    @staticmethod
    def create(request_id: str, model: str, texts: list[str]) -> dict:
        """Create embedding request."""
        return {
            "id": request_id,
            "method": "embed",
            "params": {"model": model, "texts": texts},
        }


class EmbedResponse:
    """Embedding response message."""

    @staticmethod
    def create(
        request_id: str, embeddings: list[list[float]], model: str, dimensions: int, device: str
    ) -> dict:
        """Create embedding response."""
        return {
            "id": request_id,
            "result": {
                "embeddings": embeddings,
                "model": model,
                "dimensions": dimensions,
                "device": device,
            },
        }


class HealthRequest:
    """Health check request."""

    @staticmethod
    def create(request_id: str) -> dict:
        """Create health check request."""
        return {"id": request_id, "method": "health"}


class HealthResponse:
    """Health check response."""

    @staticmethod
    def create(request_id: str, models_loaded: list[str], memory_mb: float, device: str) -> dict:
        """Create health check response."""
        return {
            "id": request_id,
            "result": {
                "status": "ok",
                "models_loaded": models_loaded,
                "memory_mb": memory_mb,
                "device": device,
            },
        }


class ErrorResponse:
    """Error response message."""

    @staticmethod
    def create(request_id: str, error: str, error_type: str = "ServerError") -> dict:
        """Create error response."""
        return {"id": request_id, "error": {"type": error_type, "message": error}}
