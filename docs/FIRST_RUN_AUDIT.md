# First-run audit

Performed as a non-developer agency owner, following `README.md` literally on a
fresh clone (`/tmp/fresh-ai-cold-calling-agent`), no real API keys, no real calls.

## What worked without changes

- `git clone`, `python3 -m venv .venv`, `pip install -r requirements-dev.txt` all completed cleanly on Python 3.13.5.
- `python -m coldcaller.check` printed a clear `OK` summary and a list of missing live variables.
- `python -m coldcaller.run --dry-run` printed the CALL/SKIP plan exactly as documented.
- `python -m coldcaller.simulate` ran the four scripted conversations with no network access.
- `pytest -q` passed all 90 tests, matching the badge and the README's stated count.

## Friction found and fixed

- [x] **No time-boxed path to a first real outcome.** The README jumps from the
  offline demo straight into a long "real setup" section with no sense of how
  long it takes or what a first-timer should expect at each step.
  Fixed: added `docs/QUICKSTART_15_MIN.md` and a "Get results in 15 minutes"
  section near the top of `README.md`.
- [x] **No hand-held guide to getting Twilio and OpenAI credentials.** The
  README links to Twilio and OpenAI docs but never says where Account SID,
  Auth Token, or an API key actually come from, or which trial limitations
  (verified caller IDs) will block a first test call.
  Fixed: added `docs/GET_YOUR_KEYS.md` and linked it from the README and from
  the doctor's output.
- [x] **The doctor does not point anywhere when keys are missing.** It lists
  variable names but a first-timer would not know what to do next.
  Fixed: `python -m coldcaller.check` now prints a pointer to
  `docs/GET_YOUR_KEYS.md` whenever live configuration is incomplete.
- [x] **No ready-made example beyond one generic campaign.** A first-timer in
  a specific niche (med spa, home services, etc.) has to invent their own
  YAML and CSV from scratch before they can see something relevant.
  Fixed: added `examples/niches/` with five runnable niche configs and sample
  leads, documented in `examples/README.md`.
- [x] **No agent-assisted setup path.** Nothing told a Claude Code or Codex
  user that this repo can be set up conversationally.
  Fixed: added `.claude/skills/ai-cold-calling-setup/SKILL.md`, `AGENTS.md`,
  and a README mention.

## Friction noted, not changed

- The "real setup" section still uses technical terms (`PUBLIC_BASE_URL`,
  signed callbacks, TwiML). This is inherent to the tool; `docs/GET_YOUR_KEYS.md`
  and the 15-minute quickstart translate it into concrete copy/paste steps
  instead of removing the underlying concepts.
- Live calling requires a paid Twilio number and OpenAI billing; there is no
  way to remove that cost, only to make the first setup faster.
