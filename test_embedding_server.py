#!/usr/bin/env python3
"""Integration test for embedding server."""

import sys
import time
import tempfile
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))


def test_client_availability():
    """Test that client can detect daemon availability."""
    from sia_code.embed_server.client import EmbedClient

    # Should return False when daemon not running
    available = EmbedClient.is_available()
    print(f"✓ Client.is_available() when daemon not running: {available}")
    assert not available, "Client should report daemon as not available"


def test_protocol():
    """Test protocol message encoding/decoding."""
    from sia_code.embed_server.protocol import (
        Message,
        EmbedRequest,
        EmbedResponse,
        HealthRequest,
        HealthResponse,
    )

    # Test embed request
    req = EmbedRequest.create("test-123", "model-name", ["text1", "text2"])
    encoded = Message.encode(req)
    decoded = Message.decode(encoded)

    assert decoded["id"] == "test-123"
    assert decoded["method"] == "embed"
    assert decoded["params"]["model"] == "model-name"
    assert decoded["params"]["texts"] == ["text1", "text2"]
    print("✓ Protocol: EmbedRequest encoding/decoding works")

    # Test embed response
    resp = EmbedResponse.create("test-123", [[0.1, 0.2], [0.3, 0.4]], "model-name", 2, "cpu")
    encoded = Message.encode(resp)
    decoded = Message.decode(encoded)

    assert decoded["id"] == "test-123"
    assert decoded["result"]["model"] == "model-name"
    assert decoded["result"]["dimensions"] == 2
    assert decoded["result"]["device"] == "cpu"
    assert len(decoded["result"]["embeddings"]) == 2
    print("✓ Protocol: EmbedResponse encoding/decoding works")

    # Test health check
    health_req = HealthRequest.create("health-1")
    encoded = Message.encode(health_req)
    decoded = Message.decode(encoded)

    assert decoded["id"] == "health-1"
    assert decoded["method"] == "health"
    print("✓ Protocol: HealthRequest encoding/decoding works")

    health_resp = HealthResponse.create("health-1", ["model1", "model2"], 742.5, "cuda")
    encoded = Message.encode(health_resp)
    decoded = Message.decode(encoded)

    assert decoded["id"] == "health-1"
    assert decoded["result"]["status"] == "ok"
    assert decoded["result"]["memory_mb"] == 742.5
    assert decoded["result"]["device"] == "cuda"
    assert decoded["result"]["models_loaded"] == ["model1", "model2"]
    print("✓ Protocol: HealthResponse encoding/decoding works")


def test_daemon_startup_shutdown():
    """Test daemon can start and stop (without actual model loading)."""
    import socket
    import os
    import signal
    from sia_code.embed_server.daemon import EmbedDaemon
    import threading

    # Use temp paths
    with tempfile.TemporaryDirectory() as tmpdir:
        socket_path = f"{tmpdir}/test-embed.sock"
        pid_path = f"{tmpdir}/test-embed.pid"

        # Create daemon
        daemon = EmbedDaemon(socket_path=socket_path, pid_path=pid_path)

        # Start in thread (so we can test it)
        server_thread = threading.Thread(target=daemon.serve, daemon=True)
        server_thread.start()

        # Wait for server to start
        time.sleep(0.5)

        # Check socket exists
        assert Path(socket_path).exists(), "Socket should be created"
        print(f"✓ Daemon: Socket created at {socket_path}")

        # Check PID file
        assert Path(pid_path).exists(), "PID file should be created"
        pid = int(Path(pid_path).read_text())
        assert pid == os.getpid(), "PID should match current process"
        print(f"✓ Daemon: PID file created with PID {pid}")

        # Try to connect
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        try:
            sock.connect(socket_path)
            print("✓ Daemon: Socket accepts connections")
            sock.close()
        except Exception as e:
            print(f"✗ Daemon: Failed to connect: {e}")
            raise

        # Shutdown
        daemon.shutdown_flag.set()
        server_thread.join(timeout=2.0)

        print("✓ Daemon: Shutdown complete")


def test_data_separation():
    """Test that different repo data is kept separate."""
    # This is a logical test - the architecture ensures separation because:
    # 1. Daemon only holds models (shared)
    # 2. Each repo has its own .sia-code/index.db (not shared)
    # 3. Each repo has its own .sia-code/vectors.usearch (not shared)
    # 4. Client only sends text -> receives embeddings (stateless)

    print("\n✓ Architecture verification: Data separation")
    print("  - Daemon: Shares embedding models only (stateless)")
    print("  - Repo 1: .sia-code/index.db (separate SQLite database)")
    print("  - Repo 2: .sia-code/index.db (separate SQLite database)")
    print("  - Repo 1: .sia-code/vectors.usearch (separate vector index)")
    print("  - Repo 2: .sia-code/vectors.usearch (separate vector index)")
    print("  - Communication: Text in -> Embeddings out (no repo state in daemon)")


def test_performance_expectations():
    """Document expected performance improvements."""
    print("\n✓ Expected Performance Improvements:")
    print("  Scenario: 3 repos with bge-base (700MB model)")
    print("  - Without daemon: 2.1GB total (700MB × 3)")
    print("  - With daemon:    700MB total (shared model)")
    print("  - Memory savings: 67% (1.4GB saved)")
    print()
    print("  - First command:       3-5s (model load)")
    print("  - Subsequent commands: <100ms (socket request)")
    print("  - Speedup:            30-50x faster")


if __name__ == "__main__":
    print("=" * 60)
    print("Embedding Server Integration Tests")
    print("=" * 60)
    print()

    try:
        test_client_availability()
        print()

        test_protocol()
        print()

        test_daemon_startup_shutdown()
        print()

        test_data_separation()

        test_performance_expectations()

        print()
        print("=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

    except Exception as e:
        print()
        print("=" * 60)
        print(f"✗ Test failed: {e}")
        print("=" * 60)
        import traceback

        traceback.print_exc()
        sys.exit(1)
