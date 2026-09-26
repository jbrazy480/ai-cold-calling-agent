# Contributing

Use Python 3.11 or newer on Linux or macOS. Install requirements-dev.txt and run
`pytest -q`, `python -m coldcaller.run --dry-run`, and `python -m coldcaller.simulate`.
Keep tests offline. Add focused tests when changing guards, provider protocol, or
state handling. Use fake numbers and placeholder credentials in examples.

Do not include .env, real lead data, or runtime state in changes. Explain the
behavior change and verification in your pull request. For demo changes, run
`python scripts/make_demo_gif.py`. Keep documentation factual and plain.
