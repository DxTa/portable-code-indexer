"""Embedding server daemon."""

import logging
import os
import signal
import socket
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import psutil

from .protocol import (
    EmbedRequest,
    EmbedResponse,
    ErrorResponse,
    HealthRequest,
    HealthResponse,
    Message,
)

logger = logging.getLogger(__name__)


class EmbedDaemon:
    """Embedding server daemon.

    Features:
    - Lazy model loading (loads on first request)
    - Thread pool for concurrent requests
    - Graceful shutdown on SIGTERM
    - Unix socket communication
    """

    def __init__(
        self,
        socket_path: str = "/tmp/sia-embed.sock",
        pid_path: str = "/tmp/sia-embed.pid",
        log_path: str | None = None,
    ):
        """Initialize daemon.

        Args:
            socket_path: Path to Unix socket
            pid_path: Path to PID file
            log_path: Path to log file (None = stderr)
        """
        self.socket_path = Path(socket_path)
        self.pid_path = Path(pid_path)
        self.log_path = Path(log_path) if log_path else None

        # Model storage (lazy-loaded)
        self.models: dict[str, Any] = {}
        self.device: str = "cpu"  # Will be set on first model load

        # Thread pool for concurrent requests
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Shutdown flag
        self.shutdown_flag = threading.Event()

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown_flag.set()

    def _load_model(self, model_name: str) -> Any:
        """Lazy-load embedding model.

        Args:
            model_name: Model name (e.g., 'BAAI/bge-base-en-v1.5')

        Returns:
            SentenceTransformer model
        """
        if model_name not in self.models:
            logger.info(f"Loading model: {model_name}")

            # Import here to avoid loading if not needed
            from sentence_transformers import SentenceTransformer
            import torch

            # Auto-detect device on first load
            if not self.models:  # First model
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
                logger.info(f"Using device: {self.device}")

            # Load model
            model = SentenceTransformer(model_name, device=self.device)
            self.models[model_name] = model

            logger.info(f"Model loaded: {model_name} ({len(self.models)} total)")

        return self.models[model_name]

    def _handle_embed(self, model: str, texts: list[str]) -> dict:
        """Handle embedding request.

        Args:
            model: Model name
            texts: List of texts to embed

        Returns:
            Response dict with embeddings
        """
        try:
            embedder = self._load_model(model)
            vectors = embedder.encode(texts, convert_to_numpy=True, batch_size=32)

            return {
                "embeddings": vectors.tolist(),
                "model": model,
                "dimensions": vectors.shape[1],
                "device": self.device,
            }
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            raise

    def _handle_health(self) -> dict:
        """Handle health check request.

        Returns:
            Health status dict
        """
        # Get process memory usage
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024

        return {
            "status": "ok",
            "models_loaded": list(self.models.keys()),
            "memory_mb": round(memory_mb, 2),
            "device": self.device if self.models else "not initialized",
        }

    def _handle_connection(self, conn: socket.socket):
        """Handle a single client connection.

        Args:
            conn: Client socket connection
        """
        try:
            # Read request (up to 10MB)
            data = conn.recv(10_000_000)
            if not data:
                return

            # Parse request
            request = Message.decode(data)
            request_id = request.get("id", "unknown")
            method = request.get("method")

            # Route request
            if method == "embed":
                params = request.get("params", {})
                model = params.get("model")
                texts = params.get("texts", [])

                if not model or not texts:
                    response = ErrorResponse.create(
                        request_id, "Missing model or texts", "InvalidRequest"
                    )
                else:
                    result = self._handle_embed(model, texts)
                    response = EmbedResponse.create(
                        request_id,
                        result["embeddings"],
                        result["model"],
                        result["dimensions"],
                        result["device"],
                    )

            elif method == "health":
                result = self._handle_health()
                response = HealthResponse.create(
                    request_id,
                    result["models_loaded"],
                    result["memory_mb"],
                    result["device"],
                )

            else:
                response = ErrorResponse.create(
                    request_id, f"Unknown method: {method}", "UnknownMethod"
                )

            # Send response
            conn.sendall(Message.encode(response))

        except Exception as e:
            logger.error(f"Connection error: {e}", exc_info=True)
            # Try to send error response
            try:
                response = ErrorResponse.create("unknown", str(e), "ServerError")
                conn.sendall(Message.encode(response))
            except Exception:
                pass  # Connection may be closed

        finally:
            conn.close()

    def _write_pid(self):
        """Write PID file."""
        self.pid_path.write_text(str(os.getpid()))

    def _cleanup(self):
        """Cleanup resources."""
        # Remove PID file
        if self.pid_path.exists():
            self.pid_path.unlink()

        # Remove socket
        if self.socket_path.exists():
            self.socket_path.unlink()

        # Shutdown executor
        self.executor.shutdown(wait=True)

        logger.info("Cleanup complete")

    def serve(self):
        """Start the daemon and serve requests."""
        try:
            # Write PID file
            self._write_pid()
            logger.info(f"Daemon started (PID: {os.getpid()})")

            # Clean up old socket
            if self.socket_path.exists():
                self.socket_path.unlink()

            # Create Unix socket
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.bind(str(self.socket_path))
            sock.listen(5)
            sock.settimeout(1.0)  # Timeout for accept() to check shutdown flag

            logger.info(f"Listening on {self.socket_path}")

            # Main event loop
            while not self.shutdown_flag.is_set():
                try:
                    conn, _ = sock.accept()
                    # Handle in thread pool
                    self.executor.submit(self._handle_connection, conn)
                except socket.timeout:
                    continue  # Check shutdown flag
                except Exception as e:
                    if not self.shutdown_flag.is_set():
                        logger.error(f"Accept error: {e}")

            logger.info("Shutdown initiated")

        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)

        finally:
            self._cleanup()


def start_daemon(
    socket_path: str = "/tmp/sia-embed.sock",
    pid_path: str = "/tmp/sia-embed.pid",
    log_path: str | None = None,
    foreground: bool = False,
):
    """Start the embedding daemon.

    Args:
        socket_path: Path to Unix socket
        pid_path: Path to PID file
        log_path: Path to log file (None = stderr)
        foreground: Run in foreground (don't daemonize)
    """
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_path) if log_path else logging.StreamHandler()],
    )

    if not foreground:
        # Fork to background
        pid = os.fork()
        if pid > 0:
            # Parent process - exit
            print(f"Daemon started with PID {pid}")
            sys.exit(0)

        # Child process - continue as daemon
        os.setsid()  # Create new session
        os.chdir("/")  # Change working directory

        # Redirect standard file descriptors
        sys.stdin = open(os.devnull, "r")
        if not log_path:
            sys.stdout = open(os.devnull, "w")
            sys.stderr = open(os.devnull, "w")

    # Start daemon
    daemon = EmbedDaemon(socket_path, pid_path, log_path)
    daemon.serve()


def stop_daemon(pid_path: str = "/tmp/sia-embed.pid"):
    """Stop the embedding daemon.

    Args:
        pid_path: Path to PID file
    """
    pid_file = Path(pid_path)

    if not pid_file.exists():
        print("Daemon not running (no PID file)")
        return False

    try:
        pid = int(pid_file.read_text())
        os.kill(pid, signal.SIGTERM)
        print(f"Sent SIGTERM to daemon (PID {pid})")
        return True
    except ProcessLookupError:
        print(f"Daemon not running (stale PID file)")
        pid_file.unlink()
        return False
    except Exception as e:
        print(f"Error stopping daemon: {e}")
        return False


def daemon_status(socket_path: str = "/tmp/sia-embed.sock", pid_path: str = "/tmp/sia-embed.pid"):
    """Get daemon status.

    Args:
        socket_path: Path to Unix socket
        pid_path: Path to PID file

    Returns:
        Status dict or None if not running
    """
    from .client import EmbedClient

    pid_file = Path(pid_path)
    socket_file = Path(socket_path)

    # Check PID file
    if not pid_file.exists():
        return {"running": False, "reason": "No PID file"}

    try:
        pid = int(pid_file.read_text())
        # Check if process exists
        os.kill(pid, 0)  # Signal 0 checks existence
    except ProcessLookupError:
        return {"running": False, "reason": "Stale PID file", "pid": pid}
    except Exception as e:
        return {"running": False, "reason": f"Error checking PID: {e}"}

    # Check socket
    if not socket_file.exists():
        return {"running": False, "reason": "No socket file", "pid": pid}

    # Try health check
    try:
        client = EmbedClient(socket_path=str(socket_path))
        health = client.health_check()
        return {"running": True, "pid": pid, "health": health}
    except Exception as e:
        return {"running": False, "reason": f"Health check failed: {e}", "pid": pid}
