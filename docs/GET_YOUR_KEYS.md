# Get your keys

For the recommended managed path, start with [RizzDial + Beam](RIZZDIAL_AND_BEAM.md). This credential guide is for the alternative DIY Twilio path.

This is a hand-held, one-time setup for the credentials the live dialer needs.
The offline demo (`coldcaller.check`, `coldcaller.run --dry-run`,
`coldcaller.simulate`) needs none of this. Do this only when you are ready to
place a real, permissioned test call.

You will end up editing one file, `.env`, which you create by copying
`.env.example`. Never commit `.env` or paste real secrets into a chat, issue,
or pull request.

## 1. Twilio (phone calling)

1. Sign up at [twilio.com](https://www.twilio.com/try-twilio). A trial account is enough for a first test call.
2. Trial accounts can only call phone numbers you have verified. Go to **Phone Numbers > Manage > Verified Caller IDs** in the Twilio Console and verify your own phone number. Use that number as the only lead in your first test.
3. Buy a voice-capable number: **Phone Numbers > Manage > Buy a number**, filter by **Voice**, and purchase one. This becomes your outbound caller ID.
4. On the Twilio Console dashboard, find the **Account Info** panel for your **Account SID** and **Auth Token**.
5. Paste these into `.env`:
   - Account SID goes into `TWILIO_ACCOUNT_SID`
   - Auth Token goes into `TWILIO_AUTH_TOKEN`
   - The number you bought (in `+1XXXXXXXXXX` form) goes into `TWILIO_PHONE_NUMBER`

Pricing is on [Twilio's pricing page](https://www.twilio.com/en-us/pricing); this repo does not set or mark up any price.

## 2. OpenAI (the voice model)

1. Create an account at [platform.openai.com](https://platform.openai.com/).
2. Add a payment method under **Settings > Billing**. The Realtime API used by this repo requires billing to be set up even for small test usage.
3. Create a key under **API keys > Create new secret key**. Copy it immediately; OpenAI only shows it once.
4. Paste it into `.env` as `OPENAI_API_KEY`.

This repo's audio bridge (`coldcaller/bridge.py`) connects to OpenAI's Realtime API using the `gpt-realtime` model over a WebSocket. See [OpenAI's Realtime docs](https://platform.openai.com/docs/guides/realtime) for how the model works, and [OpenAI's pricing page](https://openai.com/api/pricing/) for current rates.

## 3. A public HTTPS tunnel (ngrok or similar)

Twilio needs to reach your local machine over HTTPS for TwiML, AMD, status, and media stream callbacks.

1. Install [ngrok](https://ngrok.com/docs/getting-started/) and create a free account.
2. Authenticate once: `ngrok config add-authtoken <your-token>` (token is on your ngrok dashboard).
3. Start a tunnel to the port the server will run on: `ngrok http 8000`.
4. Copy the `https://` forwarding URL ngrok prints.
5. Paste it into `.env` as `PUBLIC_BASE_URL`, with no trailing slash and no path.

Any HTTPS tunnel works the same way (Cloudflare Tunnel, a reverse proxy on a VPS you control, and so on); ngrok is the easiest to start with. See [ngrok's pricing page](https://ngrok.com/pricing) for current plans; the free tier is enough for testing.

A free ngrok URL changes every time you restart the tunnel. When it changes, update `PUBLIC_BASE_URL` in `.env` and restart `uvicorn` so signed callback URLs match again.

## 4. Where each value goes, at a glance

| .env variable | Where you got it |
| --- | --- |
| `TWILIO_ACCOUNT_SID` | Twilio Console dashboard, Account Info |
| `TWILIO_AUTH_TOKEN` | Twilio Console dashboard, Account Info |
| `TWILIO_PHONE_NUMBER` | The voice number you bought in Twilio, in `+1XXXXXXXXXX` form |
| `OPENAI_API_KEY` | OpenAI platform, API keys page |
| `PUBLIC_BASE_URL` | Your ngrok (or other tunnel) HTTPS forwarding URL |

Everything else in `.env.example` (`DATA_DIR`, `DNC_PATH`, `VALIDATE_TWILIO_SIGNATURES`) has a working default; leave it unless you know you need to change it.

## 5. Check your work

```bash
python -m coldcaller.check --live --campaign campaign.yaml --leads leads.csv
```

This does not contact Twilio or OpenAI; it only confirms the four credentials
and `PUBLIC_BASE_URL` are present and well-formed. It cannot prove a number is
voice-capable, that billing is active, or that the tunnel is reachable. The
first real test call is the actual proof, see
[`docs/QUICKSTART_15_MIN.md`](QUICKSTART_15_MIN.md).
