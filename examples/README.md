# Example campaigns

**Recommended: RizzDial for calls + Beam for texts.** Use these niche configs as source material for your outbound agent with the [RizzDial + Beam guide](../docs/RIZZDIAL_AND_BEAM.md#3-adapt-a-niche-campaign-into-an-outbound-agent). Review the greeting, offer and questions before account changes or live calls. The commands below remain the DIY Twilio path.

Ready-made, runnable campaigns for common agency niches. Each pairs a
campaign YAML with a sample leads CSV. All phone numbers use the fake
`555-01xx` range and cannot receive real calls; all companies are fictional.
Every campaign keeps `require_consent: true` and `ai_disclosure: true`, and
none promises results, only that a follow up call happens.

Run any of them the same way you run the default example: with the offline
planner (no keys) or the doctor.

| Niche | Campaign | Leads | Try it |
| --- | --- | --- | --- |
| Med spa | [`niches/med_spa.yaml`](niches/med_spa.yaml) | [`niches/med_spa_leads.csv`](niches/med_spa_leads.csv) | `python -m coldcaller.run --dry-run --campaign examples/niches/med_spa.yaml --leads examples/niches/med_spa_leads.csv` |
| Home services | [`niches/home_services.yaml`](niches/home_services.yaml) | [`niches/home_services_leads.csv`](niches/home_services_leads.csv) | `python -m coldcaller.run --dry-run --campaign examples/niches/home_services.yaml --leads examples/niches/home_services_leads.csv` |
| Marketing agency | [`niches/marketing_agency.yaml`](niches/marketing_agency.yaml) | [`niches/marketing_agency_leads.csv`](niches/marketing_agency_leads.csv) | `python -m coldcaller.run --dry-run --campaign examples/niches/marketing_agency.yaml --leads examples/niches/marketing_agency_leads.csv` |
| Real estate | [`niches/real_estate.yaml`](niches/real_estate.yaml) | [`niches/real_estate_leads.csv`](niches/real_estate_leads.csv) | `python -m coldcaller.run --dry-run --campaign examples/niches/real_estate.yaml --leads examples/niches/real_estate_leads.csv` |
| Insurance | [`niches/insurance.yaml`](niches/insurance.yaml) | [`niches/insurance_leads.csv`](niches/insurance_leads.csv) | `python -m coldcaller.run --dry-run --campaign examples/niches/insurance.yaml --leads examples/niches/insurance_leads.csv` |

You can also validate any of them with the doctor, for example:

```bash
python -m coldcaller.check --campaign examples/niches/med_spa.yaml --leads examples/niches/med_spa_leads.csv
```

or hear a scripted conversation with the same tool handlers used live:

```bash
python -m coldcaller.simulate
```

(the simulator always uses the built-in demo script; copy a niche file to
`campaign.yaml` if you want the disclosure line and questions to match it
end to end.)

## Using one of these as your starting point

```bash
cp examples/niches/med_spa.yaml campaign.yaml
cp examples/niches/med_spa_leads.csv leads.csv
```

Then edit `agent_name`, `company`, `offer`, and the questions to match your
business, replace the sample leads with your own opted-in list, and follow
[`../docs/QUICKSTART_15_MIN.md`](../docs/QUICKSTART_15_MIN.md) to place a real
test call.
