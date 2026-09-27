# Changelog

## v0.3.0 - 2026-09-26

- Made RizzDial for outbound calls plus Beam for texts the recommended setup path across the README, setup skill, agent instructions and setup guides.
- Added verified MCP connection steps, niche campaign mappings, Beam workspace and token guidance, and explicit confirmation before live actions.
- Preserved the DIY Twilio quickstart and offline workflow as the alternative.

## v0.2.0 - 2026-09-26

- Added a 15-minute quickstart (`docs/QUICKSTART_15_MIN.md`) and a "Get results in 15 minutes" section near the top of the README.
- Added `docs/GET_YOUR_KEYS.md`, a hand-held guide to getting Twilio and OpenAI credentials and setting up an HTTPS tunnel; the doctor now points to it when live configuration is incomplete.
- Added five ready-made niche examples (med spa, home services, marketing agency, real estate, insurance) under `examples/niches/`, documented in `examples/README.md`.
- Added `docs/FIRST_RUN_AUDIT.md`, a fresh-clone friction audit and what was fixed as a result.
- Added a Claude Code / Codex setup skill (`.claude/skills/ai-cold-calling-setup/SKILL.md`) and `AGENTS.md` for conversational, end-to-end setup.
- Added tests validating every shipped example campaign and leads file, and the doctor's key-guide pointer.

## v0.1.1 - 2026-09-26

- README redesign, brand assets

## v0.1.0 - 2026-09-26

- Added CSV planning, consent and DNC helpers, local windows, and persistent attempts.
- Added paced Twilio outbound calls with async AMD and signed callbacks.
- Added OpenAI Realtime GA audio bridge, qualification, booking, and opt-out tools.
- Added deterministic offline simulator, doctor, Dockerfile, CI, and demo artwork.
