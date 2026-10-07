# Flight Price Bot

Private Telegram bot for monitoring flights from Novosibirsk (`OVB`) to Yerevan (`EVN`) around 19 December 2026.

The bot searches round trips and separate one-way tickets, compares direct and reasonable one-stop options, checks availability for one and four adults, and posts useful findings to a Telegram group. The target price is as low as possible; 35,000 RUB per person round trip is the hard notification ceiling.

The preferred trip length is five days, with an accepted range of four to seven days.

## Current status

SQLite persistence, two-hour scheduling, commands, daily summaries, Travelpayouts adapters, round-trip and separate one-way comparison, notification deduplication, and live Aviasales extraction are implemented. A visible Chrome session with a persistent profile loads current result cards; the bot rotates through three date pairs per cycle and verifies attractive dates for four adults. Travelpayouts discovery remains optional and requires an API token.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Fill the local `.env`, then run:

```powershell
python -m flight_price_bot
```

The browser verifier uses installed Google Chrome in visible mode. Linux deployment
files and the optional SSH gateway configuration are documented in
[`docs/OPERATIONS.md`](docs/OPERATIONS.md).

## Proposed stack

- Python 3.12
- aiogram 3 for Telegram long polling
- Playwright with Chromium for live Aviasales verification
- httpx for Travelpayouts Data API access
- SQLite through aiosqlite for price history, deduplication, and health state
- pydantic-settings for environment configuration
- pytest and Ruff for verification

This runs as one process and does not need a public domain, webhook, Redis, or PostgreSQL.

## Documentation

- [Project context](docs/PROJECT_CONTEXT.md)
- [Product specification](docs/PRODUCT_SPEC.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Technical decisions](docs/DECISIONS.md)
- [Development guide](docs/DEVELOPMENT.md)
- [Operations guide](docs/OPERATIONS.md)

## Security note

The Telegram token is stored only in ignored local `.env`. It was previously pasted into a chat and the user explicitly authorized continued use for development. Rotate it before broader or production use, and never copy it into source code, documentation, commits, or logs.

