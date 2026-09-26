"""Plan calls offline or explicitly execute a paced live campaign."""
import argparse
import asyncio
import fcntl
import json
import sys
import time
from datetime import datetime

from .config import Campaign, Settings, load_campaign
from .guards import skip_reason
from .leads import Lead, read_leads
from .store import Store, TERMINAL


def plan(leads: list[Lead], campaign: Campaign, settings: Settings, store: Store,
         now: datetime | None = None) -> list[tuple[Lead, str]]:
    return [(lead, skip_reason(lead, campaign, settings.dnc_path, store.attempts(lead.phone), now))
            for lead in leads]


def print_plan(rows: list[tuple[Lead, str]]):
    print("DRY RUN PLAN | no calls placed")
    print(f"{'NAME':<18} {'PHONE':<16} {'ACTION':<6} REASON")
    for lead, reason in rows:
        print(f"{lead.name:<18} {lead.phone:<16} {'SKIP' if reason else 'CALL':<6} {reason or 'eligible'}")


async def live(leads: list[Lead], campaign: Campaign, settings: Settings, store: Store, client):
    """One process owns outbound scheduling; hold each slot until provider terminal status."""
    semaphore = asyncio.Semaphore(campaign.max_concurrent_calls)
    pacing = asyncio.Lock()
    last_started = 0.0

    async def call(lead):
        nonlocal last_started
        async with semaphore:
            async with pacing:
                await asyncio.sleep(max(0, campaign.seconds_between_calls - (time.monotonic() - last_started)))
                reason = skip_reason(lead, campaign, settings.dnc_path, store.attempts(lead.phone))
                if reason:
                    store.add(lead, "skipped", reason)
                    print(f"SKIP {lead.name}: {reason}")
                    return
                row = store.add(lead, "reserved", campaign=campaign.model_dump(mode="json"))
                base = settings.public_url
                try:
                    created = await asyncio.to_thread(lambda: client.calls.create(
                        to=lead.phone, from_=settings.phone_number,
                        url=f"{base}/twiml/outbound?id={row['id']}", method="POST",
                        machine_detection="DetectMessageEnd", async_amd="true",
                        async_amd_status_callback=f"{base}/amd?id={row['id']}",
                        async_amd_status_callback_method="POST",
                        status_callback=f"{base}/status?id={row['id']}", status_callback_method="POST",
                        status_callback_event=["initiated", "ringing", "answered", "completed"],
                        timeout=30, time_limit=campaign.max_call_seconds))
                    store.update(row["id"], sid=created.sid, status="queued")
                    last_started = time.monotonic()
                    print(f"CALL {lead.name}: {created.sid}")
                except Exception as exc:
                    # A timeout may still have placed a call. Stop scheduling until reconciled.
                    store.update(row["id"], status="uncertain", outcome="create_" + type(exc).__name__)
                    raise RuntimeError("Call creation failed or is uncertain. Reconcile with Twilio before rerunning.") from exc
            deadline = time.monotonic() + campaign.max_call_seconds + 90
            try:
                while store.get(row["id"])["status"] not in TERMINAL:
                    remote = await asyncio.to_thread(lambda: client.calls(created.sid).fetch())
                    store.update(row["id"], status=remote.status)
                    if remote.status in TERMINAL:
                        break
                    if time.monotonic() >= deadline:
                        await asyncio.to_thread(lambda: client.calls(created.sid).update(status="completed"))
                        store.update(row["id"], status="completed", outcome="call_timeout")
                        break
                    await asyncio.sleep(1)
            except BaseException:
                await asyncio.to_thread(lambda: client.calls(created.sid).update(status="completed"))
                raise

    # TaskGroup cancels queued work and cleans up connected calls on any failure.
    async with asyncio.TaskGroup() as group:
        for lead in leads:
            group.create_task(call(lead))


def reconcile(store: Store, client):
    """Refuse new calls while a previous invocation may still own an active call."""
    with store.transaction() as db:
        rows = [json.loads(row[0]) for row in db.execute("SELECT payload FROM calls")]
    for row in rows:
        if row["status"] in TERMINAL | {"planned", "skipped", "simulated"}:
            continue
        if not row["sid"]:
            raise ValueError(f"Unresolved call {row['id']}; inspect Twilio call logs and data/state.sqlite3 before retrying")
        status = client.calls(row["sid"]).fetch().status
        store.update(row["id"], status=status)
        if status not in TERMINAL:
            raise ValueError(f"Previous call {row['sid']} is still active; wait for completion")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--leads", default="leads.example.csv")
    parser.add_argument("--campaign", default="campaign.example.yaml")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    try:
        settings = Settings.from_env()
        campaign, leads = load_campaign(args.campaign), read_leads(args.leads)
        store = Store(settings.data_dir)
        if not args.live:
            rows = plan(leads, campaign, settings, store)
            print_plan(rows)
            for lead, reason in rows:
                store.add(lead, "skipped" if reason else "planned", reason)
            return 0
        if errors := settings.live_errors():
            raise ValueError("Live configuration missing: " + ", ".join(errors))
        # Linux/macOS advisory lock spans the whole live run, including call completion.
        with (settings.data_dir / "dialer.lock").open("w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError("Another live dialer owns this data directory") from exc
            from .server import twilio_client
            client = twilio_client(settings)
            reconcile(store, client)
            asyncio.run(live(leads, campaign, settings, store, client))
        return 0
    except (ValueError, OSError, RuntimeError, ExceptionGroup) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Stopped. Check Twilio call status before restarting.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
