from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from twilio.request_validator import RequestValidator

from coldcaller.config import Campaign, Settings
from coldcaller.leads import Lead
from coldcaller.server import create_app
from coldcaller.store import Store


@pytest.fixture
def setup(tmp_path):
    settings = Settings(auth_token="test-token", account_sid="ACfake", public_url="https://test.example",
                        data_dir=tmp_path / "data", dnc_path=tmp_path / "dnc")
    store = Store(settings.data_dir)
    campaign = Campaign()
    row = store.add(Lead("Demo", "+12025550101", consent="yes"), "queued", campaign=campaign.model_dump(mode="json"))
    store.update(row["id"], sid="CAfake")
    client = Mock()
    app = create_app(settings, store, client)
    return TestClient(app), settings, store, row, client


def post(setup, path, **params):
    http, settings, _, _, _ = setup
    data = {"AccountSid": "ACfake", "CallSid": "CAfake", **params}
    signature = RequestValidator(settings.auth_token).compute_signature(settings.public_url + path, data)
    return http.post(path, data=data, headers={"X-Twilio-Signature": signature})


def test_health(setup):
    assert setup[0].get("/health").json() == {"status": "ok"}


def test_invalid_signature(setup):
    assert setup[0].post("/amd", data={"CallSid": "CAfake"}).status_code == 403


def test_signed_query_url_and_tampering(setup):
    path = "/twiml/outbound?id=" + setup[3]["id"]
    response = post(setup, path)
    assert response.status_code == 200 and "<Pause" in response.text
    signature = RequestValidator("test-token").compute_signature("https://test.example" + path, {"CallSid": "CAfake"})
    assert setup[0].post(path, data={"CallSid": "CAother"}, headers={"X-Twilio-Signature": signature}).status_code == 403


def test_outbound_connects_human_and_discloses(setup):
    setup[2].update("CAfake", amd="human")
    response = post(setup, "/twiml/outbound")
    assert "<Connect><Stream" in response.text
    assert "wss://test.example/media-stream" in response.text
    assert "AI voice assistant" in response.text
    assert 'name="call_id"' in response.text


def test_disclosure_can_be_disabled(setup):
    setup[2].update("CAfake", amd="human", campaign=Campaign(ai_disclosure=False).model_dump(mode="json"))
    assert "<Say>" not in post(setup, "/twiml/outbound").text


@pytest.mark.parametrize("answer,outcome", [("machine_end_beep", "machine_hangup"),
                                          ("machine_end_silence", "machine_hangup"),
                                          ("machine_end_other", "machine_hangup"),
                                          ("fax", "amd_fax"), ("unknown", "amd_unknown")])
def test_amd_hangup(setup, answer, outcome):
    assert post(setup, "/amd", AnsweredBy=answer).status_code == 200
    assert setup[2].get("CAfake")["outcome"] == outcome
    assert "<Hangup" in setup[4].calls.return_value.update.call_args.kwargs["twiml"]


def test_amd_voicemail_idempotent(setup):
    setup[2].update("CAfake", campaign=Campaign(voicemail_enabled=True, voicemail_message="Example message").model_dump(mode="json"))
    post(setup, "/amd", AnsweredBy="machine_end_beep")
    post(setup, "/amd", AnsweredBy="machine_end_beep")
    twiml = setup[4].calls.return_value.update.call_args.kwargs["twiml"]
    assert "Example message" in twiml and "AI voice assistant" in twiml
    assert setup[4].calls.return_value.update.call_count == 1


def test_amd_human(setup):
    post(setup, "/amd", AnsweredBy="human")
    setup[4].calls.assert_not_called()
    assert setup[2].get("CAfake")["amd"] == "human"


def test_status_terminal_is_not_regressed(setup):
    post(setup, "/status", CallStatus="completed", SequenceNumber="3")
    post(setup, "/status", CallStatus="ringing", SequenceNumber="1")
    assert setup[2].get("CAfake")["status"] == "completed"
    assert "<Hangup" in post(setup, "/twiml/outbound").text


def test_unknown_call_and_wrong_account(setup):
    assert post(setup, "/status", CallSid="CAunknown").status_code == 404
    assert post(setup, "/status", AccountSid="ACother").status_code == 403


def test_websocket_rejects_unsigned(setup):
    with pytest.raises(WebSocketDisconnect):
        with setup[0].websocket_connect("/media-stream"):
            pass


def test_websocket_signed_but_unknown_call_rejected(setup):
    signature = RequestValidator("test-token").compute_signature("https://test.example/media-stream", {})
    with setup[0].websocket_connect("/media-stream", headers={"x-twilio-signature": signature}) as ws:
        ws.send_json({"event": "start", "start": {"customParameters": {"call_id": "unknown"}}})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_local_signature_opt_out(tmp_path):
    app = create_app(Settings(validate_signatures=False, data_dir=tmp_path), Store(tmp_path), Mock())
    assert TestClient(app).post("/status", data={"CallSid": "CAunknown"}).status_code == 404


def test_signed_websocket_audio_session(setup, monkeypatch):
    import asyncio
    import json
    setup[2].update("CAfake", amd="human")
    sent = []
    connection_args = []

    class FakeAI:
        def __init__(self):
            self.queue = asyncio.Queue()
        async def send(self, message):
            event = json.loads(message)
            sent.append(event)
            if event["type"] == "response.create":
                await self.queue.put({"type": "response.output_audio.delta", "delta": "YWJj", "item_id": "item1"})
        def __aiter__(self):
            return self.messages()
        async def messages(self):
            while True:
                yield json.dumps(await self.queue.get())
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass

    def connect(*args, **kwargs):
        connection_args.append((args, kwargs))
        return FakeAI()

    monkeypatch.setattr("coldcaller.server.websockets.connect", connect)
    signature = RequestValidator("test-token").compute_signature("https://test.example/media-stream", {})
    with setup[0].websocket_connect("/media-stream", headers={"x-twilio-signature": signature}) as ws:
        ws.send_json({"event": "connected"})
        ws.send_json({"event": "start", "start": {"streamSid": "MZfake", "callSid": "CAfake",
                     "accountSid": "ACfake", "customParameters": {"call_id": setup[3]["id"]}}})
        audio = ws.receive_json()
        assert audio == {"event": "media", "streamSid": "MZfake", "media": {"payload": "YWJj"}}
        assert ws.receive_json()["event"] == "mark"
        ws.send_json({"event": "stop"})
    assert sent[0]["session"]["type"] == "realtime"
    assert connection_args[0][0][0] == "wss://api.openai.com/v1/realtime?model=gpt-realtime"
    assert "Authorization" in connection_args[0][1]["additional_headers"]


def test_invalid_status_sequence(setup):
    assert post(setup, "/status", CallStatus="completed", SequenceNumber="bad").status_code == 400
