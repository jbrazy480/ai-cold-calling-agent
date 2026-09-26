"""Signed Twilio webhooks and authenticated media streams."""
import asyncio
import json
import logging
from urllib.parse import urlencode

import websockets
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from twilio.http.http_client import TwilioHttpClient
from twilio.request_validator import RequestValidator
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

from .bridge import Bridge, session_update
from .config import Campaign, Settings
from .logging import configure
from .store import Store, TERMINAL
from .tools import ToolRunner

configure()
log = logging.getLogger(__name__)


def twilio_client(settings: Settings):
    return Client(settings.account_sid, settings.auth_token, http_client=TwilioHttpClient(timeout=15))


def create_app(settings: Settings | None = None, store: Store | None = None, client=None) -> FastAPI:
    settings = settings or Settings.from_env()
    store = store or Store(settings.data_dir)
    app = FastAPI(title="AI cold calling agent")
    app.state.store = store

    def api():
        return client or twilio_client(settings)

    def valid_signature(request, params, websocket=False):
        if not settings.validate_signatures:
            return True
        if not settings.auth_token:
            return False
        # Use configured external URL, never trust forwarded host headers.
        url = settings.public_url + request.url.path
        if request.url.query:
            url += "?" + request.url.query
        validator = RequestValidator(settings.auth_token)
        signature = request.headers.get("x-twilio-signature", "")
        return validator.validate(url, params, signature) or (
            websocket and validator.validate(url.rstrip("/") + "/", params, signature))

    async def form(request):
        params = await request.form()
        if not valid_signature(request, params):
            raise HTTPException(403, "Invalid Twilio signature")
        if settings.account_sid and params.get("AccountSid") != settings.account_sid:
            raise HTTPException(403, "Wrong Twilio account")
        return params

    def resolve(params, token=None):
        row = store.get(token or params.get("CallSid", ""))
        if not row:
            raise HTTPException(404, "Unknown call")
        sid = params.get("CallSid")
        if not sid or (row["sid"] and row["sid"] != sid):
            raise HTTPException(403, "Call mismatch")
        if not row["sid"]:
            row = store.update(row["id"], sid=sid)
        return row

    async def redirect(sid, twiml):
        await asyncio.to_thread(lambda: api().calls(sid).update(twiml=str(twiml)))

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/twiml/outbound")
    async def outbound(request: Request):
        params = await form(request)
        row = resolve(params, request.query_params.get("id"))
        campaign = Campaign.model_validate(row["campaign"])
        response = VoiceResponse()
        if row["status"] in TERMINAL or row.get("amd") in {"fax", "unknown"}:
            response.hangup()
        elif row.get("amd", "").startswith("machine"):
            if campaign.voicemail_enabled and row["amd"].startswith("machine_end"):
                if campaign.ai_disclosure:
                    response.say(campaign.ai_disclosure_line)
                response.say(campaign.voicemail_message)
            response.hangup()
        elif row.get("amd") != "human":
            # Async AMD runs while this silent TwiML waits, avoiding speech over a greeting.
            response.pause(length=2)
            response.redirect(settings.public_url + "/twiml/outbound?" + urlencode({"id": row["id"]}), method="POST")
        else:
            if campaign.ai_disclosure:
                response.say(campaign.ai_disclosure_line)
            stream = response.connect().stream(url=settings.public_url.replace("https://", "wss://", 1) + "/media-stream")
            stream.parameter(name="call_id", value=row["id"])
        return Response(str(response), media_type="application/xml")

    @app.post("/amd")
    async def amd(request: Request):
        params = await form(request)
        row = resolve(params, request.query_params.get("id"))
        detected = params.get("AnsweredBy", "unknown")
        if row["status"] in TERMINAL or row.get("amd_handled"):
            return {"ok": True}
        store.update(row["id"], amd=detected)
        campaign = Campaign.model_validate(row["campaign"])
        response = VoiceResponse()
        if detected == "human":
            # The waiting TwiML redirects itself and sees the persisted decision.
            pass
        elif detected.startswith("machine_end"):
            if campaign.voicemail_enabled:
                if campaign.ai_disclosure:
                    response.say(campaign.ai_disclosure_line)
                response.say(campaign.voicemail_message)
            response.hangup()
            await redirect(row["sid"], response)
            store.update(row["id"], outcome="voicemail" if campaign.voicemail_enabled else "machine_hangup")
        else:
            response.hangup()
            await redirect(row["sid"], response)
            store.update(row["id"], outcome="amd_" + detected)
        store.update(row["id"], amd_handled=True)
        return {"ok": True}

    @app.post("/status")
    async def status(request: Request):
        params = await form(request)
        row = resolve(params, request.query_params.get("id"))
        changes = {"status": params.get("CallStatus", "unknown")}
        try:
            sequence = int(params.get("SequenceNumber", "-1"))
        except ValueError as exc:
            raise HTTPException(400, "Invalid status sequence") from exc
        if sequence >= 0 and sequence <= row.get("status_sequence", -1):
            return {"ok": True}
        if sequence >= 0:
            changes["status_sequence"] = sequence
        store.update(row["id"], **changes)
        return {"ok": True}

    @app.websocket("/media-stream")
    async def media(websocket: WebSocket):
        if not valid_signature(websocket, {}, websocket=True):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        row = None
        try:
            # Twilio sends connected then start. Do not open a paid AI session until correlated.
            async with asyncio.timeout(10):
                while True:
                    event = json.loads(await websocket.receive_text())
                    if event.get("event") == "start":
                        start = event["start"]
                        row = store.get(start.get("customParameters", {}).get("call_id", ""))
                        if (not row or row["sid"] != start.get("callSid") or row.get("amd") != "human"
                                or row["status"] in TERMINAL
                                or (settings.account_sid and start.get("accountSid") != settings.account_sid)):
                            await websocket.close(code=1008)
                            return
                        break
            campaign = Campaign.model_validate(row["campaign"])

            async def finish(message):
                response = VoiceResponse()
                response.say(message)
                response.hangup()
                await redirect(row["sid"], response)

            runner = ToolRunner(store, row["id"], campaign, settings.dnc_path, finish)
            async with websockets.connect("wss://api.openai.com/v1/realtime?model=gpt-realtime",
                                          additional_headers={"Authorization": f"Bearer {settings.openai_key}"},
                                          max_size=2**22) as ai:
                bridge = Bridge(websocket, ai, runner)
                await bridge.from_twilio(event)
                await bridge.send(session_update(campaign, row))
                await bridge.send({"type": "response.create"})
                async with asyncio.timeout(campaign.max_call_seconds):
                    await bridge.run()
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            log.error("media_stream_failed", extra={"error_type": type(exc).__name__})
            if row:
                store.update(row["id"], outcome="bridge_error")
                try:
                    await asyncio.to_thread(lambda: api().calls(row["sid"]).update(status="completed"))
                except Exception:
                    log.error("call_cleanup_failed")
            await websocket.close(code=1011)

    return app


app = create_app()
