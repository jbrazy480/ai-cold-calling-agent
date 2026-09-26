"""Shared, validated tool execution for Realtime and the offline simulator."""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .config import Campaign
from .store import Store


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Answer(Arguments):
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=4000)


class Booking(Arguments):
    time: str
    email: str | None = None

    @field_validator("time")
    @classmethod
    def with_offset(cls, value):
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError("time must be ISO 8601 with timezone offset")
        return value


class Reason(Arguments):
    reason: str = Field(min_length=1, max_length=2000)


MODELS = {"record_answer": Answer, "book_meeting": Booking,
          "mark_not_interested": Reason, "request_dnc": Reason, "end_call": Reason}
DESCRIPTIONS = {
    "record_answer": "Record the prospect's actual answer to a qualification question.",
    "book_meeting": "Request a meeting only after explicit agreement on time and timezone. Do not invent availability.",
    "mark_not_interested": "Accept lack of interest and end politely.",
    "request_dnc": "Immediately suppress this number and end politely when asked not to call.",
    "end_call": "End the conversation politely when finished or asked to stop.",
}
TOOL_SCHEMAS = [{"type": "function", "name": name, "description": DESCRIPTIONS[name],
                 "parameters": model.model_json_schema()} for name, model in MODELS.items()]


class ToolRunner:
    def __init__(self, store: Store, call_id: str, campaign: Campaign, dnc_path: Path,
                 finish: Callable[[str], Awaitable[None]] | None = None):
        self.store, self.call_id, self.campaign = store, call_id, campaign
        self.dnc_path, self.finish = dnc_path, finish
        self.lock = asyncio.Lock()

    async def execute(self, name: str, arguments: str | dict, call_id: str) -> dict:
        async with self.lock:
            key = f"{self.call_id}:{call_id}"
            cached = self.store.tool_result(key)
            if cached is not None:
                return cached
            try:
                if name not in MODELS:
                    return {"ok": False, "error": "unknown tool"}
                args = MODELS[name].model_validate(json.loads(arguments) if isinstance(arguments, str) else arguments)
                row = self.store.get(self.call_id)
                if row is None:
                    return {"ok": False, "error": "unknown call"}
                result = {"ok": True}
                closing = None
                if name == "record_answer":
                    answers = {**row["answers"], args.question: args.answer}
                    self.store.update(self.call_id, answers=answers, outcome="qualifying")
                elif name == "book_meeting":
                    if row["booked_time"]:
                        return {"ok": True, "time": row["booked_time"], "already_booked": True}
                    booking = {"id": self.call_id, "phone": row["phone"], "name": row["name"], **args.model_dump()}
                    if self.campaign.booking_webhook_url:
                        async with httpx.AsyncClient(timeout=10) as client:
                            response = await client.post(str(self.campaign.booking_webhook_url), json=booking,
                                                         headers={"Idempotency-Key": self.call_id})
                            response.raise_for_status()
                    else:
                        self.store.save_booking(booking)
                    self.store.update(self.call_id, booked_time=args.time, outcome="booking_requested")
                    result = {"ok": True, "time": args.time, "status": "booking_requested"}
                elif name == "request_dnc":
                    self.store.add_dnc(self.dnc_path, row["phone"])
                    self.store.update(self.call_id, outcome="dnc_requested", end_reason=args.reason)
                    closing = "Your number has been added to our do not call list. Goodbye."
                elif name == "mark_not_interested":
                    self.store.update(self.call_id, outcome="not_interested", end_reason=args.reason)
                    closing = "Thank you for your time. Goodbye."
                else:
                    self.store.update(self.call_id, end_reason=args.reason)
                    closing = "Thank you for your time. Goodbye."
                if closing and self.finish:
                    await self.finish(closing)
                self.store.save_tool_result(key, result)
                return result
            except (ValueError, ValidationError, httpx.HTTPError) as exc:
                return {"ok": False, "error": type(exc).__name__, "message": "Invalid arguments or booking delivery failed; do not claim success."}
