"""Unit tests for embedding client framing."""

from sia_code.embed_server.client import EmbedClient
from sia_code.embed_server.protocol import Message


def test_send_request_reads_chunked_response(monkeypatch):
    response = {"id": "1", "result": {"status": "ok"}}
    encoded = Message.encode(response)
    chunks = [encoded[:10], encoded[10:20], encoded[20:]]

    class FakeSocket:
        def __init__(self):
            self._chunks = list(chunks)

        def settimeout(self, _timeout):
            pass

        def connect(self, _path):
            pass

        def sendall(self, _data):
            pass

        def recv(self, _size):
            if self._chunks:
                return self._chunks.pop(0)
            return b""

        def close(self):
            pass

    monkeypatch.setattr("socket.socket", lambda *_args, **_kwargs: FakeSocket())

    client = EmbedClient(socket_path="/tmp/does-not-matter")
    result = client._send_request({"id": "1", "method": "health"})

    assert result["result"]["status"] == "ok"
