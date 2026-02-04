"""Unit tests for embed daemon start behavior."""

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
