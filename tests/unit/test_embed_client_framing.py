"""Unit tests for embedding client framing."""

from sia_code.embed_server.client import EmbedClient
from sia_code.embed_server.protocol import Message


def test_send_request_reads_length_prefixed_response(monkeypatch):
    """Test that client correctly reads length-prefixed messages in chunks."""
    response = {"id": "1", "result": {"status": "ok"}}
    # Encode with 4-byte length prefix
    encoded = Message.encode(response)

    class FakeSocket:
        def __init__(self):
            self._data = encoded
            self._pos = 0

        def settimeout(self, _timeout):
            pass

        def connect(self, _path):
            pass

        def sendall(self, _data):
            pass

        def recv(self, size):
            # Simulate reading from socket buffer byte by byte
            if self._pos >= len(self._data):
                return b""
            chunk = self._data[self._pos : self._pos + size]
            self._pos += len(chunk)
            return chunk

        def close(self):
            pass

    monkeypatch.setattr("socket.socket", lambda *_args, **_kwargs: FakeSocket())

    client = EmbedClient(socket_path="/tmp/does-not-matter")
    result = client._send_request({"id": "1", "method": "health"})

    assert result["result"]["status"] == "ok"


def test_is_available_requires_health_check(monkeypatch, tmp_path):
    """Availability should fail if health check cannot complete."""
    socket_path = tmp_path / "embed.sock"
    socket_path.write_text("ready")

    class FakeSocket:
        def settimeout(self, _timeout):
            pass

        def connect(self, _path):
            pass

        def close(self):
            pass

    monkeypatch.setattr("socket.socket", lambda *_args, **_kwargs: FakeSocket())

    def _raise_health(_self):
        raise RuntimeError("Protocol mismatch")

    monkeypatch.setattr(EmbedClient, "health_check", _raise_health)

    assert EmbedClient.is_available(str(socket_path)) is False


def test_read_from_socket_protocol_mismatch_message():
    """Invalid framing should hint at protocol mismatch, not payload size."""

    class FakeSocket:
        def __init__(self):
            self._data = b'{"id"'
            self._pos = 0

        def recv(self, size):
            if self._pos >= len(self._data):
                return b""
            chunk = self._data[self._pos : self._pos + size]
            self._pos += len(chunk)
            return chunk

    try:
        Message.read_from_socket(FakeSocket(), max_bytes=50_000_000)
        assert False, "Expected ValueError for protocol mismatch"
    except ValueError as exc:
        message = str(exc)
        assert "protocol mismatch" in message
        assert "7b226964" in message
