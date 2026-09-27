from coldcaller.check import main


def test_doctor_points_to_key_guide_when_incomplete(capsys, monkeypatch):
    for name in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER",
                 "OPENAI_API_KEY", "PUBLIC_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "docs/GET_YOUR_KEYS.md" in output


def test_doctor_silent_about_keys_when_complete(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC" + "x" * 32)
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+12025550100")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.ngrok.app")
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "docs/GET_YOUR_KEYS.md" not in output
    assert "Live configuration: present" in output
