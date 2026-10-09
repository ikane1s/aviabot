# Project context

Last updated: 9 October 2026.

## Goal

Help four friends find inexpensive flights from Novosibirsk to Yerevan for a concert on 19 December 2026. The bot posts findings to their Telegram group and provides a link for immediate manual purchase.

## Confirmed trip parameters

- Origin: Novosibirsk, city/airport code `OVB`.
- Destination: Yerevan, city/airport code `EVN`.
- Concert: 19 December 2026.
- Departure window: 14–18 December 2026.
- Initial return window: 20–23 December 2026.
- Preferred stay: five days; 4–7 days is acceptable.
- Travelers: four adults.
- Each traveler purchases separately.
- Prefer the same itinerary for all four.
- Checked baggage is not required, but offers that include baggage are welcome.
- Direct flights are preferred. One reasonable connection is acceptable when the price is attractive.
- Very long and overnight connections should be deprioritized, not silently mixed with convenient offers.

## Price policy

- Up to 25,000 RUB per person round trip: excellent, urgent alert.
- 25,001–30,000 RUB: good alert.
- 30,001–35,000 RUB: acceptable alert.
- Above 35,000 RUB: no ordinary alert; include the best result in the daily summary.
- Compare a single round-trip booking with two separately purchased one-way tickets.
- Always show price per person and an estimated total for four.

## Availability policy

The bot checks both one adult and four adults:

- A matching four-adult result means the same itinerary appears available for the group at the time of verification.
- A result visible only for one adult is still useful, but it must be labeled as uncertain for all four.
- Do not claim an exact remaining seat count unless the source explicitly provides it.
- Separate purchases can consume the cheapest fare bucket between transactions; messages must warn users to coordinate purchases.

## Source policy

- Travelpayouts Data API is a discovery source based on cached searches.
- The Aviasales hot-tickets page is another discovery source. Its displayed price is
  a hint only and never triggers an alert by itself.
- Aviasales browser search is the live verification source.
- A live result can still change during checkout. Notifications are signals to verify and purchase, not price guarantees.
- CAPTCHA or blocked browser access is an observable health condition. It is not a reason to bypass site protection.

## Open questions

- Travelpayouts API token.
- Final VPS choice after measuring Chromium memory use.

## Implemented foundation

- Environment-based configuration with secret values hidden from normal representation.
- Domain models for legs, offers, baggage, booking shape, and group availability.
- Price classification and valid concert-window rules.
- Independent best-offer views for overall, direct, one-stop, baggage, and four-adult availability.
- Narrow provider interfaces for cached discovery and live browser verification.
- Telegram command shell restricted to the configured group.
- Initial automated tests for approved price and trip rules.

## Verified on 7 October 2026

- Telegram token is valid for `@Aviabot_bot_bot`, and the bot may join groups.
- Target group was discovered through `/setup`, saved in local `.env`, and restricted as the only operational chat.
- Outbound Telegram delivery succeeded; the setup message and first daily summary reached the group.
- Aviasales search links correctly encode one and four adults.
- Headless Chromium received Yandex SmartCaptcha, while visible installed Google Chrome loaded current result cards normally with the persistent profile.
- An invisible reCAPTCHA frame exists on successful result pages. It is not treated as a challenge; only the visible Yandex SmartCaptcha surface blocks a run.
- Live extraction was verified for one and four adults. A four-adult result displays the combined total, which the bot normalizes to a per-person price.
- A controlled cycle checked three date pairs and stored 29 live offers. The verified 16–21 December direct S7 option was 36,242 RUB per person and therefore above the ordinary alert ceiling.
- Automated suite: 28 tests passing; Ruff clean.

## Added on 9 October 2026

- The route-specific Aviasales hot-tickets page is checked at most once every six
  hours with December and round-trip filters.
- A hot-ticket candidate inside the approved date window and at or below 35,000 RUB
  may add one priority pair to the next ordinary Aviasales verification.
- Hot-ticket prices are not stored as live offers and cannot trigger Telegram alerts
  until the ordinary search page confirms them.
- A live page check showed a direct 14–20 December option around 31,305 RUB. The
  approved departure window was widened to 14 December so this pair can receive a
  live verification.

