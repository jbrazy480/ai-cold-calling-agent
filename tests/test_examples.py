"""Every shipped example campaign and leads file must load and validate."""
from pathlib import Path

import pytest

from coldcaller.config import load_campaign
from coldcaller.leads import read_leads

ROOT = Path(__file__).parent.parent
NICHES = ROOT / "examples/niches"

CAMPAIGNS = [ROOT / "campaign.example.yaml", *sorted(NICHES.glob("*.yaml"))]
LEADS = [ROOT / "leads.example.csv", *sorted(NICHES.glob("*_leads.csv"))]


@pytest.mark.parametrize("path", CAMPAIGNS, ids=lambda p: p.name)
def test_example_campaign_loads(path):
    campaign = load_campaign(path)
    assert campaign.ai_disclosure
    assert campaign.ai_disclosure_line.strip()
    assert campaign.require_consent


@pytest.mark.parametrize("path", LEADS, ids=lambda p: p.name)
def test_example_leads_load(path):
    leads = read_leads(path)
    assert leads
    assert any(lead.consent == "yes" and lead.dnc == "no" for lead in leads)


def test_niche_examples_are_paired():
    yaml_stems = {path.stem for path in NICHES.glob("*.yaml")}
    csv_stems = {path.stem.removesuffix("_leads") for path in NICHES.glob("*_leads.csv")}
    assert yaml_stems == csv_stems
    assert len(yaml_stems) == 5
