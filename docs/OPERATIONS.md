# Operations guide

## Deployment shape

The intended deployment is one Linux service running the Python application, Google Chrome, and an Xvfb virtual display. Chrome must run in headed mode because the verified headless session did not load usable Aviasales results. Start with a VPS that has at least 1 GB RAM, then measure peak use before reducing resources.

## Required secrets

- `TELEGRAM_BOT_TOKEN`: active bot token stored outside Git.
- `TELEGRAM_TARGET_CHAT_ID`: the approved group.
- `TRAVELPAYOUTS_API_TOKEN`: official Data API token.

Keep secrets in a root-readable service environment file or another host secret store. Never put them in Git or command output shared in chat.

## Health signals

`/status` should report:

- latest completed cycle;
- latest successful Travelpayouts request;
- latest successful live browser verification;
- whether a CAPTCHA cooldown is active;
- latest successful Telegram delivery;
- next planned cycle.

## Expected incidents

### CAPTCHA or access challenge

Send one service warning, record diagnostic metadata without cookies, pause browser checks, and retry after cooldown. Continue daily summaries with an explicit unverified-data warning when useful.

### Aviasales page changed

The verifier should fail closed: do not extract guessed values. Capture a screenshot and sanitized diagnostics locally, then update the isolated provider selectors.

### Price changes during checkout

This is expected. A verified visible price is still not a reservation. Messages must tell the group to open the result promptly and coordinate separate purchases.

### Database corruption or disk loss

The bot can rebuild current state, but historical comparisons and deduplication are lost. Back up the SQLite file after clean checkpoints if history becomes valuable.

