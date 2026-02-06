"""Unit tests for embed daemon start behavior."""

import logging

from sia_code.embed_server import daemon as daemon_mod


def test_start_daemon_noop_when_running(monkeypatch):
    def fake_status(*_args, **_kwargs):
        return {"running": True, "pid": 123, "health": {"status": "ok"}}

    class FailDaemon:
        def __init__(self, *args, **kwargs):
            raise AssertionError("EmbedDaemon should not be constructed")

    monkeypatch.setattr(daemon_mod, "daemon_status", fake_status)
    monkeypatch.setattr(daemon_mod, "EmbedDaemon", FailDaemon)

    daemon_mod.start_daemon(foreground=True)


def test_handle_connection_closed_header_is_not_error(tmp_path, caplog):
    """Closing a probe connection before header should not log an error."""
    daemon = daemon_mod.EmbedDaemon(
        socket_path=str(tmp_path / "sock"),
        pid_path=str(tmp_path / "pid"),
        idle_timeout_seconds=1,
    )

    class FakeSocket:
        def recv(self, _size):
            return b""

        def sendall(self, _data):
            raise AssertionError("sendall should not be called")

        def close(self):
            pass

    caplog.set_level(logging.ERROR, logger="sia_code.embed_server.daemon")
    daemon._handle_connection(FakeSocket())  # type: ignore[arg-type]

    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
