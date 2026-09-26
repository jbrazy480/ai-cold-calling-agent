"""All tests are offline; unexpected network access fails immediately."""
import socket

import pytest


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("DNC_PATH", str(tmp_path / "dnc.txt"))
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    def blocked(*args, **kwargs):
        raise AssertionError("Network access is forbidden in offline tests")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
