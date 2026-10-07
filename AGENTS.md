# AGENTS.md

## Purpose

This repository contains a private Telegram bot that monitors flight prices for a group trip from Novosibirsk to Yerevan around a concert on 19 December 2026.

Read these files before changing code:

1. `docs/PROJECT_CONTEXT.md` — confirmed product decisions and open questions.
2. `docs/PRODUCT_SPEC.md` — search rules and notification behavior.
3. `docs/ARCHITECTURE.md` — components, data flow, and boundaries.
4. `docs/DECISIONS.md` — decisions that should not be silently reversed.
5. `docs/DEVELOPMENT.md` — local setup and verification.

## Non-negotiable rules

- Never commit or print Telegram, Travelpayouts, proxy, or other credentials.
- The user explicitly authorized the Telegram token shared during planning. It is stored only in ignored `.env`; never copy it into tracked files, logs, commits, or responses.
- Do not implement CAPTCHA bypass, fingerprint spoofing, proxy rotation, or other protection evasion.
- Use the official Travelpayouts Data API only as discovery. A price alert must be based on a fresh browser check on Aviasales whenever that check succeeds.
- If live verification fails, label the result as unverified. Never present a cached price as currently bookable.
- Search sequentially and conservatively. Do not increase request frequency without documenting the reason.
- Four adults buy separately, but the bot should try to confirm that all four can use the same itinerary.
- Store and display prices per person. Also show the estimated total for four people.
- Keep the bot deployable as one small process with SQLite. Do not add Redis, PostgreSQL, or a service mesh without a demonstrated need.

## Engineering conventions

- Python 3.12+.
- Async I/O for Telegram, HTTP, scheduling, and browser orchestration.
- Domain rules stay independent of Telegram and Playwright.
- External providers implement narrow interfaces and return normalized domain models.
- Every notification decision must be explainable from stored facts: price, dates, stops, duration, baggage information, passenger count, source, and verification time.
- Add tests for ranking, deduplication, date-window rules, and notification thresholds. Avoid tests that merely mirror implementation.
- Preserve user changes and inspect the working tree before editing.

## Definition of done for a feature

- Product behavior matches `docs/PRODUCT_SPEC.md`.
- Secrets remain outside version control.
- Relevant tests pass.
- User-facing behavior and operational impact are documented.
- Any live-site uncertainty is reported explicitly.

