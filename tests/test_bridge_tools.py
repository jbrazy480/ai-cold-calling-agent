import asyncio
import base64
import json
from unittest.mock import AsyncMock

import httpx
import pytest

from coldcaller.bridge import Bridge, session_update
from coldcaller.config import Campaign
from coldcaller.leads import Lead
from coldcaller.simulate import simulate
from coldcaller.store import Store
from coldcaller.tools import ToolRunner


class FakeSocket:
    def __init__(self):
        self.sent = []
        self.queue = asyncio.Queue()
        self.cancelled = False

    async def send(self, message):
        self.sent.append(json.loads(message))

    async def send_json(self, event):
        self.sent.append(event)

    async def iter_text(self):
        try:
            while True:
                item = await self.queue.get()
                if item is None:
                    return
                yield json.dumps(item)
        finally:
            self.cancelled = True

    def __aiter__(self):
        return self.iter_text()


@pytest.fixture
def context(tmp_path):
    store = Store(tmp_path / "data")
    row = store.add(Lead("Demo", "+12025550101", consent="yes"), "in-progress")
    finish = AsyncMock()
    runner = ToolRunner(store, row["id"], Campaign(), tmp_path / "dnc.txt", finish)
    return store, row, runner, finish


def test_ga_session_schema():
    payload = session_update(Campaign(), {})
    session = payload["session"]
    assert session["type"] == "realtime" and session["model"] == "gpt-realtime"
    assert session["audio"]["input"]["format"] == {"type": "audio/pcmu"}
    assert session["audio"]["output"]["format"] == {"type": "audio/pcmu"}
    assert {tool["name"] for tool in session["tools"]} == {
        "record_answer", "book_meeting", "request_dnc", "end_call", "mark_not_interested"}


async def test_audio_forwarding_both_directions(context):
    phone, ai = FakeSocket(), FakeSocket()
    bridge = Bridge(phone, ai, context[2])
    await bridge.from_twilio({"event": "start", "start": {"streamSid": "MZfake"}})
    await bridge.from_twilio({"event": "media", "media": {"timestamp": "100", "payload": "YWJj"}})
    assert ai.sent == [{"type": "input_audio_buffer.append", "audio": "YWJj"}]
    await bridge.from_openai({"type": "response.output_audio.delta", "item_id": "item1", "delta": "YWJj"})
    assert phone.sent[0] == {"event": "media", "streamSid": "MZfake", "media": {"payload": "YWJj"}}
    assert phone.sent[1]["event"] == "mark"


async def test_barge_in_truncates_played_audio(context):
    phone, ai = FakeSocket(), FakeSocket()
    bridge = Bridge(phone, ai, context[2])
    await bridge.from_twilio({"event": "start", "start": {"streamSid": "MZfake"}})
    bridge.latest_timestamp = 100
    await bridge.from_openai({"type": "response.output_audio.delta", "item_id": "item1",
                              "delta": base64.b64encode(b'a' * 8000).decode()})
    bridge.latest_timestamp = 350
    await bridge.from_openai({"type": "input_audio_buffer.speech_started"})
    assert ai.sent[-1] == {"type": "conversation.item.truncate", "item_id": "item1",
                           "content_index": 0, "audio_end_ms": 250}
    assert phone.sent[-1]["event"] == "clear"
    assert not bridge.marks and bridge.item_id is None


async def test_acknowledged_audio_not_truncated(context):
    phone, ai = FakeSocket(), FakeSocket()
    bridge = Bridge(phone, ai, context[2])
    bridge.stream_sid = "MZfake"
    await bridge.from_openai({"type": "response.output_audio.delta", "item_id": "item1", "delta": "YWJj"})
    await bridge.from_twilio({"event": "mark", "mark": phone.sent[-1]["mark"]})
    await bridge.from_openai({"type": "input_audio_buffer.speech_started"})
    assert not ai.sent


async def test_function_round_trip_dnc(context, tmp_path):
    phone, ai = FakeSocket(), FakeSocket()
    bridge = Bridge(phone, ai, context[2])
    event = {"type": "response.function_call_arguments.done", "name": "request_dnc",
             "arguments": '{"reason":"stop calling"}', "call_id": "tool1"}
    await bridge.from_openai(event)
    await bridge.from_openai(event)
    assert (tmp_path / "dnc.txt").read_text() == "+12025550101\n"
    assert ai.sent[0]["item"]["type"] == "function_call_output"
    assert json.loads(ai.sent[0]["item"]["output"])["ok"]
    assert ai.sent[1] == {"type": "response.create"}
    context[3].assert_awaited_once()
    assert context[0].get(context[1]["id"])["outcome"] == "dnc_requested"


async def test_bidirectional_tasks_stop_together(context):
    phone, ai = FakeSocket(), FakeSocket()
    bridge = Bridge(phone, ai, context[2])
    await phone.queue.put({"event": "start", "start": {"streamSid": "MZfake"}})
    await phone.queue.put({"event": "media", "media": {"timestamp": "0", "payload": "YWJj"}})
    task = asyncio.create_task(bridge.run())
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await ai.queue.put({"type": "response.output_audio.delta", "item_id": "item1", "delta": "YWJj"})
    await asyncio.sleep(0)
    await phone.queue.put({"event": "stop"})
    await asyncio.wait_for(task, timeout=1)
    assert ai.cancelled
    assert ai.sent[0]["audio"] == "YWJj" and phone.sent[0]["event"] == "media"


async def test_record_answer_and_local_booking(context):
    store, row, runner, _ = context
    await runner.execute("record_answer", {"question": "Need?", "answer": "Follow-ups"}, "a1")
    args = {"time": "2026-10-05T14:00:00+00:00", "email": "demo@example.invalid"}
    result = await runner.execute("book_meeting", args, "b1")
    await runner.execute("book_meeting", args, "b1")
    await runner.execute("book_meeting", args, "b2")
    assert result["status"] == "booking_requested"
    assert store.get(row["id"])["answers"] == {"Need?": "Follow-ups"}
    assert len((store.directory / "bookings.jsonl").read_text().splitlines()) == 1


async def test_webhook_booking(context, monkeypatch):
    store, row, runner, _ = context
    runner.campaign = Campaign(booking_webhook_url="https://booking.example/request")
    response = httpx.Response(200, request=httpx.Request("POST", "https://booking.example/request"))
    post = AsyncMock(return_value=response)
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    result = await runner.execute("book_meeting", {"time": "2026-10-05T14:00:00+00:00"}, "b1")
    assert result["ok"]
    assert post.call_args.kwargs["headers"]["Idempotency-Key"] == row["id"]
    assert not (store.directory / "bookings.jsonl").exists()


async def test_failed_booking_never_claimed_success(context, monkeypatch):
    store, row, runner, _ = context
    runner.campaign = Campaign(booking_webhook_url="https://booking.example/request")
    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(side_effect=httpx.ConnectError("offline")))
    result = await runner.execute("book_meeting", {"time": "2026-10-05T14:00:00+00:00"}, "b1")
    assert not result["ok"] and store.get(row["id"])["booked_time"] == ""


@pytest.mark.parametrize("name,args", [("unknown", {}), ("record_answer", {}),
                                      ("end_call", "not-json"), ("book_meeting", {"time": "tomorrow"}),
                                      ("book_meeting", {"time": "2026-10-05T14:00:00"})])
async def test_invalid_tools_return_errors(context, name, args):
    assert not (await context[2].execute(name, args, "bad"))["ok"]


async def test_simulator_qualification_objection_booking_dnc_and_decline(tmp_path, capsys):
    results = await simulate(tmp_path)
    assert [row["outcome"] for row in results] == ["booking_requested", "dnc_requested", "not_interested"]
    assert len(results[0]["answers"]) == 2
    output = capsys.readouterr().out
    assert "busy right now" in output and "Tool book_meeting" in output
    assert (tmp_path / "dnc.txt").read_text() == "+12025550101\n"
    assert len((tmp_path / "bookings.jsonl").read_text().splitlines()) == 1
