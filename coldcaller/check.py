"""Offline installation and live configuration doctor. Never makes network requests."""
import argparse
import sys
from zoneinfo import ZoneInfo

from .config import Settings, load_campaign
from .guards import NPA
from .leads import read_leads


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", default="campaign.example.yaml")
    parser.add_argument("--leads", default="leads.example.csv")
    parser.add_argument("--live", action="store_true", help="Require complete live environment")
    args = parser.parse_args(argv)
    try:
        load_campaign(args.campaign)
        leads = read_leads(args.leads)
        for zones in NPA.values():
            for zone in zones:
                ZoneInfo(zone)
        print(f"OK Python {sys.version.split()[0]}, campaign, {len(leads)} leads, {len(NPA)} NPA entries")
        settings = Settings.from_env()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        import tempfile
        with tempfile.TemporaryFile(dir=settings.data_dir):
            pass
        print("OK runtime directory writable")
        missing = settings.live_errors()
        print("Live configuration: " + (", ".join(missing) if missing else "present (not network-verified)"))
        print("Twilio signatures: " + ("enabled" if settings.validate_signatures else "DISABLED for local development"))
        return 1 if args.live and missing else 0
    except (ValueError, OSError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
