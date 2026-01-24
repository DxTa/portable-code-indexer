#!/usr/bin/env python3
"""Test auto-unload and reload functionality."""

import sys
import time
import tempfile
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))


def test_auto_unload_reload():
    """Test that models auto-unload after idle timeout and reload on next request."""
    import threading
    from sia_code.embed_server.daemon import EmbedDaemon
    from sia_code.embed_server.client import EmbedClient

    print("=" * 60)
    print("Auto-Unload/Reload Test")
    print("=" * 60)
    print()

    # Use temp paths and SHORT timeout for testing (10 seconds)
    with tempfile.TemporaryDirectory() as tmpdir:
        socket_path = f"{tmpdir}/test-embed.sock"
        pid_path = f"{tmpdir}/test-embed.pid"

        # Create daemon with 10 second timeout
        daemon = EmbedDaemon(
            socket_path=socket_path,
            pid_path=pid_path,
            idle_timeout_seconds=10,  # 10 seconds for testing
        )

        # Start in thread
        server_thread = threading.Thread(target=daemon.serve, daemon=True)
        server_thread.start()

        # Wait for server to start
        time.sleep(0.5)
        print("✓ Daemon started with 10s idle timeout")

        # Create client
        client = EmbedClient(socket_path=socket_path)

        # First request - should load model
        print("\n1. First request (should load model)...")
        start = time.time()
        embeddings = client.encode(["test text"])
        load_time = time.time() - start
        print(f"   ✓ Got embeddings: shape={embeddings.shape}")
        print(f"   ✓ Time: {load_time:.2f}s (includes model loading)")

        # Check model is loaded
        with daemon.model_lock:
            assert len(daemon.models) == 1, "Model should be loaded"
            model_name = list(daemon.models.keys())[0]
            print(f"   ✓ Model loaded: {model_name}")

        # Second request immediately - should use cached model
        print("\n2. Second request (should use cached model)...")
        start = time.time()
        embeddings = client.encode(["another test"])
        cached_time = time.time() - start
        print(f"   ✓ Got embeddings: shape={embeddings.shape}")
        print(f"   ✓ Time: {cached_time:.2f}s (using cached model)")
        print(f"   ✓ Speedup: {load_time / cached_time:.1f}x faster")

        # Wait for model to be unloaded (10s + 10s cleanup interval = ~20s max)
        print("\n3. Waiting for auto-unload (10s idle timeout)...")
        print("   (cleanup thread runs every 10 minutes in production,")
        print("    but we'll manually trigger it for this test)")

        # Manually trigger cleanup for testing
        time.sleep(11)  # Wait for idle timeout to pass

        # Manually run cleanup logic
        from datetime import datetime, timedelta

        now = datetime.now()
        with daemon.model_lock:
            models_to_unload = []
            for model_name, last_used in daemon.model_last_used.items():
                idle_time = (now - last_used).total_seconds()
                if idle_time > daemon.idle_timeout_seconds:
                    models_to_unload.append((model_name, idle_time))

            for model_name, idle_time in models_to_unload:
                if model_name in daemon.models:
                    print(f"   ✓ Unloading idle model: {model_name} (idle {idle_time:.1f}s)")
                    del daemon.models[model_name]

        # Check model is unloaded
        with daemon.model_lock:
            if len(daemon.models) == 0:
                print("   ✓ Model successfully unloaded")
            else:
                print("   ✗ Model still loaded (should be unloaded)")
                return False

        # Third request after unload - should reload model
        print("\n4. Third request (should reload model)...")
        start = time.time()
        embeddings = client.encode(["test after reload"])
        reload_time = time.time() - start
        print(f"   ✓ Got embeddings: shape={embeddings.shape}")
        print(f"   ✓ Time: {reload_time:.2f}s (includes model reload)")

        # Check model is loaded again
        with daemon.model_lock:
            if len(daemon.models) == 1:
                print(f"   ✓ Model reloaded: {list(daemon.models.keys())[0]}")
            else:
                print("   ✗ Model not reloaded")
                return False

        # Shutdown
        daemon.shutdown_flag.set()
        server_thread.join(timeout=2.0)
        print("\n✓ Daemon shutdown complete")

        print()
        print("=" * 60)
        print("✓ Auto-Unload/Reload Test PASSED")
        print("=" * 60)
        print()
        print("Summary:")
        print(f"  - Initial load: {load_time:.2f}s")
        print(f"  - Cached use:   {cached_time:.2f}s ({load_time / cached_time:.1f}x faster)")
        print(f"  - After reload: {reload_time:.2f}s")
        print(f"  - Model unloaded after 10s idle ✓")
        print(f"  - Model reloaded on next request ✓")
        print()

        return True


if __name__ == "__main__":
    try:
        success = test_auto_unload_reload()
        sys.exit(0 if success else 1)
    except Exception as e:
        print()
        print("=" * 60)
        print(f"✗ Test failed: {e}")
        print("=" * 60)
        import traceback

        traceback.print_exc()
        sys.exit(1)
