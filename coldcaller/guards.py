"""Conservative scheduling helpers, not a compliance determination."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Campaign
from .leads import Lead

E164 = re.compile(r"^\+[1-9][0-9]{7,14}$")
NPA = json.loads((Path(__file__).parent / "assets/npa_timezones.json").read_text())


def timezones(lead: Lead) -> list[str]:
    if lead.timezone:
        try:
            ZoneInfo(lead.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            return []
        return [lead.timezone]
    return NPA.get(lead.phone[2:5], []) if lead.phone.startswith("+1") and len(lead.phone) == 12 else []


def internal_dnc(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.split("#", 1)[0].strip() for line in path.read_text().splitlines()}


def skip_reason(lead: Lead, campaign: Campaign, dnc_path: Path, attempts: int = 0,
                now: datetime | None = None) -> str:
    """Return the first blocker; start inclusive, end exclusive in every candidate zone."""
    if not E164.fullmatch(lead.phone):
        return "invalid E.164 phone"
    if lead.dnc == "yes":
        return "lead DNC flag"
    if lead.phone in internal_dnc(dnc_path):
        return "internal DNC list"
    if campaign.require_consent and lead.consent != "yes":
        return "consent required"
    if attempts >= campaign.max_attempts_per_lead:
        return "max attempts reached"
    zones = timezones(lead)
    if not zones:
        return "unknown or invalid timezone; provide an IANA timezone"
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    for zone in zones:
        local = now.astimezone(ZoneInfo(zone))
        if not campaign.calling_window.start <= local.time() < campaign.calling_window.end:
            return f"outside calling window ({zone}, {local:%H:%M})"
    return ""
