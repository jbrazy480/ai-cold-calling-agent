from datetime import datetime

import pytest

from coldcaller.config import Campaign, Window
from coldcaller.guards import skip_reason, timezones, NPA
from coldcaller.leads import Lead

NOW = datetime.fromisoformat("2026-09-26T17:00:00+00:00")


def lead(**kwargs):
    return Lead(**({"name": "Demo", "phone": "+12025550101", "consent": "yes"} | kwargs))


@pytest.mark.parametrize("changes,reason", [
    ({"phone": "2025550101"}, "invalid E.164"),
    ({"phone": "+02025550101"}, "invalid E.164"),
    ({"phone": "+120255501011111111"}, "invalid E.164"),
    ({"phone": "+1abc5550101"}, "invalid E.164"),
    ({"consent": "no"}, "consent required"),
    ({"dnc": "yes"}, "lead DNC flag"),
    ({"timezone": "Moon/Sea"}, "unknown or invalid timezone"),
    ({"phone": "+442079460123"}, "unknown or invalid timezone"),
    ({"phone": "+18005550101"}, "unknown or invalid timezone"),
])
def test_guard_reasons(tmp_path, changes, reason):
    assert skip_reason(lead(**changes), Campaign(), tmp_path / "dnc", now=NOW).startswith(reason)


def test_internal_dnc(tmp_path):
    path = tmp_path / "dnc"
    path.write_text("# comment\n+12025550101 # requested\n")
    assert skip_reason(lead(), Campaign(), path, now=NOW) == "internal DNC list"


def test_attempt_limit(tmp_path):
    assert skip_reason(lead(), Campaign(max_attempts_per_lead=2), tmp_path / "dnc", 2, NOW) == "max attempts reached"
    assert skip_reason(lead(), Campaign(), tmp_path / "dnc", 1, NOW) == ""


def test_consent_configurable(tmp_path):
    assert skip_reason(lead(consent="no"), Campaign(require_consent=False), tmp_path / "dnc", now=NOW) == ""


@pytest.mark.parametrize("phone,expected", [
    ("+12025550101", "America/New_York"),
    ("+14155550101", "America/Los_Angeles"),
    ("+13125550101", "America/Chicago"),
    ("+16135550101", "America/Toronto"),
    ("+16045550101", "America/Vancouver"),
    ("+16025550101", "America/Phoenix"),
    ("+19075550101", "America/Anchorage"),
])
def test_timezone_lookup(phone, expected):
    assert expected in timezones(lead(phone=phone))


def test_explicit_timezone_overrides_npa():
    assert timezones(lead(timezone="Europe/London")) == ["Europe/London"]
    assert len(NPA) > 400


@pytest.mark.parametrize("instant,allowed", [
    ("2026-01-15T13:59:59+00:00", False),
    ("2026-01-15T14:00:00+00:00", True),
    ("2026-01-16T00:59:59+00:00", True),
    ("2026-01-16T01:00:00+00:00", False),
    ("2026-07-15T12:59:59+00:00", False),
    ("2026-07-15T13:00:00+00:00", True),
    ("2026-07-16T00:00:00+00:00", False),
    ("2026-03-08T13:00:00+00:00", True),
    ("2026-11-01T13:00:00+00:00", False),
    ("2026-11-01T14:00:00+00:00", True),
])
def test_window_boundaries_and_dst(tmp_path, instant, allowed):
    reason = skip_reason(lead(), Campaign(), tmp_path / "dnc", now=datetime.fromisoformat(instant))
    assert (not reason) is allowed


def test_all_zones_must_allow(tmp_path):
    item = lead(phone="+12085550101")
    assert len(timezones(item)) >= 2
    assert "outside calling window" in skip_reason(item, Campaign(), tmp_path / "dnc",
                                                  now=datetime.fromisoformat("2026-07-15T15:30:00+00:00"))
    assert skip_reason(item, Campaign(), tmp_path / "dnc", now=datetime.fromisoformat("2026-07-15T17:00:00+00:00")) == ""


def test_stricter_window(tmp_path):
    config = Campaign(calling_window=Window(start="11:00", end="12:00"))
    assert "outside" in skip_reason(lead(), config, tmp_path / "dnc", now=NOW)


@pytest.mark.parametrize("start,end", [("20:00", "09:00"), ("09:00", "09:00")])
def test_reject_overnight_and_empty_windows(start, end):
    with pytest.raises(ValueError):
        Window(start=start, end=end)


def test_naive_clock_rejected(tmp_path):
    with pytest.raises(ValueError, match="timezone-aware"):
        skip_reason(lead(), Campaign(), tmp_path / "dnc", now=datetime(2026, 1, 1))
