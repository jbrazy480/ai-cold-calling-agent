"""All tests are offline; unexpected network access fails immediately."""
import socket

import pytest

from coldcaller import config


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    # Patch the imported binding so dotenv cannot reload the developer's .env
    # after a test deletes a setting. Tests supply their own environment values.
    monkeypatch.setattr(config, "load_dotenv", lambda *args, **kwargs: False)
    for name in (
        "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER",
        "OPENAI_API_KEY", "PUBLIC_BASE_URL", "PUBLIC_URL", "DATA_DIR",
        "DNC_PATH", "VALIDATE_TWILIO_SIGNATURES",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "runtime"))
    monkeypatch.setenv("DNC_PATH", str(tmp_path / "dnc.txt"))
    def blocked(*args, **kwargs):
        raise AssertionError("Network access is forbidden in offline tests")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
