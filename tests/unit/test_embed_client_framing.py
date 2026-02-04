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
