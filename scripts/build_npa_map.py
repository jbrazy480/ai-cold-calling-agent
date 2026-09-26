"""Regenerate bundled data with: pip install phonenumbers==9.0.40."""
import json
from pathlib import Path

from phonenumbers import parse, region_code_for_number, tzdata

zones: dict[str, set[str]] = {}
for prefix, candidates in tzdata.TIMEZONE_DATA.items():
    if prefix.startswith("1") and len(prefix) >= 4:
        npa = prefix[1:4]
        if region_code_for_number(parse("+1" + npa + "2345678")) in {"US", "CA"}:
            zones.setdefault(npa, set()).update(candidates)
path = Path(__file__).resolve().parents[1] / "coldcaller/assets/npa_timezones.json"
path.write_text(json.dumps({key: sorted(value) for key, value in sorted(zones.items())}, indent=2) + "\n")
print(f"Wrote {len(zones)} NPA entries")
