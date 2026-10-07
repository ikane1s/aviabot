# Operations guide

## Deployment shape

The intended deployment is one Linux service running the Python application, Google Chrome, and an Xvfb virtual display. Chrome must run in headed mode because the verified headless session did not load usable Aviasales results. Start with a VPS that has at least 1 GB RAM, then measure peak use before reducing resources.

During local Windows testing, Task Scheduler starts `scripts/run_local.ps1` at user logon. The script restarts the process after failure and writes to `logs/bot.log`. This local mode works only while the computer is on and the user is signed in.

On Linux, `deploy/flight-price-bot-xvfb.service` provides display `:99` without opening an X11 network listener. `deploy/flight-price-bot-tunnel.service` provides a loopback-only SOCKS5 endpoint for Telegram through the foreign gateway. `deploy/flight-price-bot.service` runs the application as the unprivileged `flightbot` user and restarts it after failure. Secrets are read from `/etc/flight-price-bot.env`.

Copy `deploy/flight-price-bot-tunnel.env.example` to
`/etc/flight-price-bot-tunnel.env` and replace the example destination with the
dedicated SSH user and gateway hostname. Keep the real gateway address in the host
configuration rather than Git. The SSH private key and pinned `known_hosts` entry live
under `/var/lib/flight-price-bot/.ssh`.

## Required secrets

- `TELEGRAM_BOT_TOKEN`: active bot token stored outside Git.
- `TELEGRAM_TARGET_CHAT_ID`: the approved group.
- `TELEGRAM_PROXY_URL`: production value `socks5://127.0.0.1:1080`; omit locally when Telegram is directly reachable.
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
