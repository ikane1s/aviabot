# Development guide

## Prerequisites

- Python 3.12 or newer.
- Git.
- Chromium installed through Playwright.

## Local setup on Windows PowerShell

```powershell
cd D:\VsCodeProjects\flight-price-bot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m playwright install chromium
Copy-Item .env.example .env
```

Fill `.env` with the Telegram token, target group chat ID, and Travelpayouts token. Keep the file local and ignored by Git.

For initial group binding, leave `TELEGRAM_TARGET_CHAT_ID=0`, start the bot, add it to the group, and send `/setup` in that group. Put the returned negative chat ID into `.env` and restart the bot. While the value is zero, price and operational commands are disabled.

## Planned verification commands

```powershell
python -m pytest
python -m ruff check .
python -m flight_price_bot
```

## Implementation order

1. Domain models and date-pair generator.
2. Ranking and notification policy with tests.
3. SQLite schema and repositories.
4. Telegram `/status`, `/best`, and `/check` commands.
5. Travelpayouts discovery provider.
6. Aviasales Playwright proof of concept for one date pair.
7. One-adult/four-adult comparison.
8. Scheduler, deduplication, and daily summary.
9. VPS measurement and deployment.

Items 1–8 are implemented. The Travelpayouts adapter is unit tested but awaits a real API token. Live Aviasales extraction works with visible installed Chrome and the persistent browser profile; headless mode is not suitable in the verified environment.

## Live-site development rule

Keep selectors and page interpretation inside the Aviasales provider. Save sanitized HTML fixtures only when allowed and useful; never save cookies, tokens, or personal session data. A selector test is not proof of production behavior, so always run a controlled live smoke check before deployment.

