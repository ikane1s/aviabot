# Architecture

## Overview

The first version is one asynchronous Python process with five logical layers:

```text
Scheduler / Telegram commands
            |
            v
      Search orchestrator
       /             \
Travelpayouts       Aviasales browser
discovery           live verification
       \             /
        Normalizer + policy engine
                  |
            SQLite history
                  |
          Telegram notifier
```

## Components

### Scheduler

Runs the two-hour search cycle and the daily summary using `asyncio` and timezone-aware datetimes. It prevents overlapping cycles. A separate scheduling service is unnecessary for one bot.

### Search orchestrator

Generates valid date combinations, runs discovery, selects candidates worth live verification, and keeps browser activity sequential.

### Travelpayouts provider

Uses the official Data API to discover cached candidates. It never marks a price as live. The provider exposes normalized candidates and source timestamps.

### Aviasales browser verifier

Uses Playwright with visible Google Chrome and a persistent local profile. Headless mode did not load usable results in the verified environment. It performs ordinary searches for one adult, repeats attractive date pairs for four adults, waits for result cards, and extracts visible prices and itineraries.

The verifier must detect consent dialogs, empty results, navigation failures, and CAPTCHA pages. It must not attempt protection bypass. Selectors belong only in this provider so UI changes do not affect domain logic.

### Domain policy engine

Normalizes round trips and paired one-way offers. It classifies price level, convenience, baggage state, and group availability. It produces separate views for cheapest overall, best direct, best one-stop, best with baggage, and best confirmed for four.

### SQLite store

SQLite runs in WAL mode. Proposed tables:

- `search_runs`: cycle timestamps, source outcomes, and error categories.
- `offers`: normalized observations with price and itinerary identity.
- `live_verifications`: passenger count, visible price, result URL, and timestamp.
- `notifications`: deduplication key, message type, and delivery status.
- `daily_snapshots`: selected summary facts for day-to-day comparison.
- `app_state`: cooldowns and operational markers.

### Telegram bot

Uses long polling, which avoids a public HTTPS endpoint. The notifier formats messages and uses idempotency keys. Command handlers validate the configured chat ID.

## Search strategy

Running every date and passenger combination through a browser would be wasteful. Each cycle uses two stages:

1. Discovery ranks cached candidates and recent known combinations.
2. Live verification checks three rotating date pairs. When a one-adult price is at or below 35,000 RUB, the same dates are checked for four adults.

The 14 approved combinations are covered in about five cycles. With the current two-hour interval, a complete rotation takes roughly ten hours even without Travelpayouts data.

## Resource target

- One process.
- One Chromium page at a time.
- No concurrent live searches.
- SQLite on local disk.
- Long polling instead of a web server.
- Start testing with at least 1 GB RAM because Chromium is the dominant memory consumer. Measure before choosing a smaller VPS.

## Security boundaries

- Secrets are environment variables loaded from `.env` locally or from the service manager in production.
- Browser profile data is private operational state and stays outside Git.
- Logs must redact tokens, query headers, cookies, and sensitive URLs.
- Telegram commands are limited to the configured chat.

