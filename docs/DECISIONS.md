# Decision log

## 2026-10-07 — Python single-process application

Use Python 3.12, aiogram, Playwright, httpx, and SQLite in one process. This minimizes server cost and operational work for one route and one group.

## 2026-10-07 — Hybrid discovery and live verification

Use Travelpayouts cached data to discover candidates and browser searches on Aviasales to verify current visible prices. Cached results alone are insufficient for alerts described as current.

## 2026-10-07 — Conservative browser automation

Run searches sequentially with a persistent browser profile. Detect CAPTCHA and back off. Do not add stealth plugins, CAPTCHA solving, fingerprint spoofing, or rotating proxies.

## 2026-10-07 — Flexible itinerary policy

Direct flights are preferred, but a single reasonable connection and baggage-inclusive offers are valid. The system produces multiple best-of categories instead of collapsing every tradeoff into one unexplained score.

## 2026-10-07 — Separate purchase, shared itinerary

Four adults purchase separately. Search one adult to detect the lowest fare and four adults to estimate whether the group can use the same itinerary. Never infer an exact seat count from this comparison.

## 2026-10-07 — Telegram long polling

Use long polling for the first release. A webhook, public domain, and TLS termination add no useful value for this private bot.

## 2026-10-07 — Telegram token handling

The user explicitly authorized continued development use of the token pasted into planning chat. It is kept only in ignored `.env` and excluded from tracked files and logs. Rotation remains appropriate before broader or production use.

## 2026-10-07 — Visible Chrome for live checks

Headless browser runs received Yandex SmartCaptcha, while visible installed Chrome with the persistent profile loaded result cards normally. Production therefore runs Chrome in headed mode, using a virtual display on a Linux server. An invisible reCAPTCHA iframe on a successful page is not a blocking challenge. The detector only treats the visible Yandex SmartCaptcha surface as `challenge` when no result cards are available.

## 2026-10-07 — Rotating live coverage

Check three of the 14 valid date pairs per two-hour cycle. Query one adult first and repeat dates at or below the 35,000 RUB threshold for four adults. Aviasales displays a combined four-person total, so normalize it to a per-person price before comparison and notification.

## 2026-10-08 — Telegram through a restricted SSH tunnel

The Russian production VPS cannot reliably reach the Telegram Bot API. Keep the bot and
visible Chrome on that VPS, but send only Telegram traffic through a SOCKS5 endpoint on
`127.0.0.1:1080`. A systemd-managed SSH tunnel connects to a dedicated, key-only account
on the foreign gateway. Aviasales traffic remains direct.
