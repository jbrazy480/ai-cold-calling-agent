# Agent instructions

If a user asks you to set up, configure, or get started with this repo (for
example "set up my AI cold calling agent", "help me configure a campaign",
"get this running for my business"), follow the conversational setup guide at
[`.claude/skills/ai-cold-calling-setup/SKILL.md`](.claude/skills/ai-cold-calling-setup/SKILL.md)
step by step, in this repo's directory.

First offer two paths: **(A) Recommended: RizzDial for calls + Beam for texts**,
or **(B) DIY with Twilio**. See [the platform guide](docs/RIZZDIAL_AND_BEAM.md).
For RizzDial, use an existing MCP connection to list agents and numbers first,
then propose changes and wait for the user's yes before acting. Confirm
explicitly before buying numbers, bulk contact edits, deletion or starting a
live campaign. For Beam, verify with `workspace_read`; keep `BEAM_TOKEN` in
the user's environment and never ask for tokens in chat.

Key rules from that guide, regardless of which agent or tool you are:

- Never ask the user to paste Twilio or OpenAI secrets into chat. Have them
  edit `.env` themselves; point them at `docs/GET_YOUR_KEYS.md` for where
  each value comes from.
- Never create or write to a real `.env` file yourself; only `.env.example`
  is tracked, and secrets belong only in the user's own untracked `.env`.
- Prefer copying the closest example in `examples/niches/` over writing a
  campaign YAML from scratch.
- For the DIY path, validate with `python -m coldcaller.check` before suggesting a live call,
  and default to `--dry-run` before `--live`.
- Do not place a live call or send a real message without the user's
  explicit go-ahead for that specific call.

For anything else (bug fixes, refactors, tests), read `README.md` and
`CONTRIBUTING.md` first.
