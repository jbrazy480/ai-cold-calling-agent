# Get results in 15 minutes

> **Fastest path: RizzDial.** Use the recommended [RizzDial + Beam guide](RIZZDIAL_AND_BEAM.md) for managed outbound AI calling and texting from an iMessage business line. The steps below keep the DIY Twilio path available.

The outcome: a real, permissioned test call from this starter to your own
phone, with the AI disclosure, a qualification question, and a clean hangup.

This assumes you already have a Twilio account and an OpenAI account. If you
do not, start with [`docs/GET_YOUR_KEYS.md`](GET_YOUR_KEYS.md) first (creating
accounts and adding billing takes longer than 15 minutes the first time; the
steps below are the fast path once that is done).

## 0. Prerequisites (1 minute)

- Python 3.11 or newer, on Linux, macOS, or WSL
- A Twilio account with a voice-capable number, and your own phone number verified as a trial caller ID
- An OpenAI account with billing enabled
- [ngrok](https://ngrok.com/docs/getting-started/) installed and authenticated

## 1. Install and confirm the offline demo (3 minutes)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m coldcaller.check
python -m coldcaller.run --dry-run
python -m coldcaller.simulate
```

**Checkpoint:** `coldcaller.check` prints `OK Python ...`. `coldcaller.run --dry-run` prints a plan with CALL and SKIP rows. `coldcaller.simulate` prints three scripted conversations. No errors, no network calls.

## 2. Set up your keys (5 minutes if you already have accounts)

```bash
cp .env.example .env
```

Edit `.env` with the values from [`docs/GET_YOUR_KEYS.md`](GET_YOUR_KEYS.md):
`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, `OPENAI_API_KEY`.
Leave `PUBLIC_BASE_URL` for the next step.

In a separate terminal:

```bash
ngrok http 8000
```

Copy the `https://` forwarding URL and paste it into `.env` as `PUBLIC_BASE_URL` (no trailing slash).

**Checkpoint:** `.env` has five real values filled in; ngrok shows a "Session Status: online" line with your forwarding URL.

## 3. Configure your own test campaign (2 minutes)

```bash
cp campaign.example.yaml campaign.yaml
touch dnc.txt
```

Create `leads.csv` with exactly one row: your own verified phone number, in
E.164 form (e.g. `+12025550123`), with `consent=yes` and `dnc=no`:

```
name,phone,company,timezone,consent,dnc,notes
Your Name,+1YOURNUMBER,Your Business,,yes,no,First test call
```

**Checkpoint:**

```bash
python -m coldcaller.check --live --campaign campaign.yaml --leads leads.csv
```

prints `Live configuration: present (not network-verified)`.

## 4. Place the real test call (3 minutes)

In one terminal (virtual environment active):

```bash
uvicorn coldcaller.server:app --host 0.0.0.0 --port 8000 --workers 1
```

In another terminal, same directory, virtual environment active:

```bash
python -m coldcaller.run --leads leads.csv --campaign campaign.yaml --dry-run
python -m coldcaller.run --leads leads.csv --campaign campaign.yaml --live
```

**Checkpoint:** the dry run shows your row as `CALL eligible`. The live run
prints `CALL <name>: <Call SID>`, your phone rings, and you hear the AI
disclosure line from `campaign.yaml` followed by the first qualification
question. Answer it, then say you are not interested or ask to be removed to
see the opt-out path end the call politely.

## 5. What you should have after 15 minutes

- A real call placed to your own phone through your own Twilio number
- A row in `data/results.csv` / `data/results.jsonl` showing the outcome
- Confidence that keys, tunnel, and server are wired correctly before you load a real lead list

## If something did not work

- **No live configuration present:** re-check `.env` against the table in [`docs/GET_YOUR_KEYS.md`](GET_YOUR_KEYS.md).
- **Signature or callback errors:** `PUBLIC_BASE_URL` must exactly match the current ngrok HTTPS URL; restart `uvicorn` after changing it.
- **Trial account cannot call your number:** verify it under Twilio Console > Phone Numbers > Verified Caller IDs.
- **Nothing happens after the call answers:** check the `uvicorn` terminal for errors; Twilio's async AMD has to classify the answer before the disclosure plays.

Next: load your own leads and campaign, or start from one of the ready-made
niche examples in [`examples/README.md`](../examples/README.md).
