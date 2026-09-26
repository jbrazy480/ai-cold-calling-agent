import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from coldcaller.config import Campaign, Settings, load_campaign
from coldcaller.leads import read_leads, Lead
from coldcaller.run import main, live, reconcile
from coldcaller.store import Store


@pytest.mark.parametrize("content,match", [
    ("name,phone\nA,+12025550101\n", "requires"),
    ("name,phone,consent,dnc,phone\n", "duplicate"),
    ("name,phone,consent,dnc,extra\n", "unknown"),
    ("name,phone,consent,dnc\nA,+12025550101,maybe,no\n", "consent"),
    ("name,phone,consent,dnc\nA,+12025550101,yes,no,extra\n", "column count"),
    ("name,phone,consent,dnc\nA,+12025550101,yes\n", "column count"),
    ("name,phone,consent,dnc\nA,+12025550101,yes,no\nB,+12025550101,yes,no\n", "duplicate phone"),
    ("name,phone,consent,dnc\n,+12025550101,yes,no\n", "empty"),
    ('name,phone,consent,dnc\n"A,+12025550101,yes,no\n', "CSV line"),
])
def test_csv_errors(tmp_path, content, match):
    path = tmp_path / "leads.csv"
    path.write_text(content)
    with pytest.raises(ValueError, match=match):
        read_leads(path)


def test_csv_optional_timezone_and_bom(tmp_path):
    path = tmp_path / "leads.csv"
    path.write_text('\ufeffname,phone,consent,dnc,notes\nDemo,+12025550101,YES,NO,"quoted, note"\n')
    result = read_leads(path)[0]
    assert result.timezone == "" and result.consent == "yes" and result.notes == "quoted, note"


def test_dry_run_default_offline(capsys, tmp_path):
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "DRY RUN PLAN" in output and "consent required" in output
    assert "lead DNC flag" in output and "invalid E.164" in output
    rows = [json.loads(line) for line in (tmp_path / "runtime/results.jsonl").read_text().splitlines()]
    assert len(rows) == 5
    assert all(row["status"] in {"skipped", "planned"} for row in rows)
    assert Store(tmp_path / "runtime").attempts("+12025550101") == 0


def test_live_requires_configuration(capsys):
    assert main(["--live"]) == 1
    assert "Live configuration missing" in capsys.readouterr().err


def test_bad_file_has_clear_error(capsys):
    assert main(["--leads", "missing.csv"]) == 1
    assert "Error:" in capsys.readouterr().err


def test_invalid_campaign(tmp_path):
    path = tmp_path / "campaign.yaml"
    path.write_text("max_concurrent_calls: 0")
    with pytest.raises(ValueError):
        load_campaign(path)


async def test_live_rest_options_and_attempts(tmp_path, monkeypatch):
    monkeypatch.setattr("coldcaller.run.skip_reason", lambda *args: "")
    store = Store(tmp_path / "data")
    client = Mock()
    client.calls.create.return_value = SimpleNamespace(sid="CAfake")
    client.calls.return_value.fetch.return_value = SimpleNamespace(status="completed")
    campaign = Campaign(seconds_between_calls=0)
    settings = Settings(data_dir=tmp_path / "data", dnc_path=tmp_path / "dnc", public_url="https://test.example")
    await live([Lead("Demo", "+12025550101", consent="yes")], campaign, settings, store, client)
    kwargs = client.calls.create.call_args.kwargs
    assert kwargs["machine_detection"] == "DetectMessageEnd"
    assert kwargs["async_amd"] == "true"
    assert "/amd?id=" in kwargs["async_amd_status_callback"]
    assert kwargs["status_callback_event"] == ["initiated", "ringing", "answered", "completed"]
    assert kwargs["time_limit"] == campaign.max_call_seconds
    assert store.attempts("+12025550101") == 1
    assert store.get("CAfake")["status"] == "completed"


async def test_live_rechecks_guard_before_dialing(tmp_path):
    client = Mock()
    store = Store(tmp_path / "data")
    await live([Lead("Demo", "+12025550101", consent="no")], Campaign(seconds_between_calls=0),
               Settings(dnc_path=tmp_path / "dnc"), store, client)
    client.calls.create.assert_not_called()


def test_unresolved_call_blocks_new_run(tmp_path):
    store = Store(tmp_path)
    store.add(Lead("Demo", "+12025550101"), "uncertain")
    with pytest.raises(ValueError, match="Unresolved"):
        reconcile(store, Mock())


@pytest.mark.parametrize("maximum", [1, 2])
async def test_concurrent_calls_respect_limit(tmp_path, monkeypatch, maximum):
    import asyncio
    import threading
    monkeypatch.setattr("coldcaller.run.skip_reason", lambda *args: "")
    original_sleep = asyncio.sleep
    async def fast_sleep(delay):
        await original_sleep(0)
    monkeypatch.setattr("coldcaller.run.asyncio.sleep", fast_sleep)
    guard = threading.Lock()
    active, fetched = set(), set()
    peak = 0
    counter = 0
    def create(**kwargs):
        nonlocal peak, counter
        with guard:
            counter += 1
            sid = f"CA{counter}"
            active.add(sid)
            peak = max(peak, len(active))
            return SimpleNamespace(sid=sid)
    def resource(sid):
        def fetch():
            with guard:
                if sid not in fetched:
                    fetched.add(sid)
                    return SimpleNamespace(status="in-progress")
                active.discard(sid)
                return SimpleNamespace(status="completed")
        return SimpleNamespace(fetch=fetch, update=lambda **kwargs: None)
    client = Mock()
    client.calls.side_effect = resource
    client.calls.create.side_effect = create
    leads = [Lead("Demo", f"+1202555010{i}", consent="yes") for i in range(4)]
    await live(leads, Campaign(seconds_between_calls=0, max_concurrent_calls=maximum),
               Settings(data_dir=tmp_path, dnc_path=tmp_path / "dnc"), Store(tmp_path), client)
    assert 1 <= peak <= maximum and counter == 4 and not active


async def test_live_paces_call_creations(tmp_path, monkeypatch):
    import time
    monkeypatch.setattr("coldcaller.run.skip_reason", lambda *args: "")
    started = []
    def create(**kwargs):
        started.append(time.monotonic())
        return SimpleNamespace(sid=f"CA{len(started)}")
    client = Mock()
    client.calls.create.side_effect = create
    client.calls.return_value.fetch.return_value = SimpleNamespace(status="completed")
    await live([Lead("Demo", f"+1202555010{i}") for i in range(2)], Campaign(seconds_between_calls=0.02),
               Settings(dnc_path=tmp_path / "dnc"), Store(tmp_path), client)
    assert started[1] - started[0] >= 0.02


async def test_uncertain_creation_is_persisted_and_stops(tmp_path, monkeypatch):
    monkeypatch.setattr("coldcaller.run.skip_reason", lambda *args: "")
    store = Store(tmp_path)
    client = Mock()
    client.calls.create.side_effect = TimeoutError("provider timeout")
    with pytest.raises(ExceptionGroup):
        await live([Lead("Demo", "+12025550101")], Campaign(seconds_between_calls=0),
                   Settings(dnc_path=tmp_path / "dnc"), store, client)
    assert store.attempts("+12025550101") == 1
    with pytest.raises(ValueError, match="Unresolved"):
        reconcile(store, client)
