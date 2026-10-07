# Product specification

## Search cycle

The default cycle runs every two hours. It may be reduced to one hour after observing stable site behavior.

For every valid departure/return pair, the system considers:

1. Round-trip results for one adult.
2. The same round-trip search for four adults when a useful candidate exists.
3. Separate one-way outbound and return results when their combined price may beat the round trip.
4. Direct itineraries.
5. Itineraries with one connection in either direction.

The date generator must ensure that the traveler is in Yerevan on 19 December 2026 and that the return occurs after the concert.

## Convenience rules

- Direct is preferred.
- One connection is acceptable.
- Target maximum journey time per direction: 12 hours.
- Overnight connections and journeys above 12 hours are displayed only when the saving is exceptional.
- Two or more connections are excluded from normal alerts.
- Baggage inclusion is a positive attribute, not a requirement.
- Missing baggage information must be displayed as unknown rather than inferred.

## Alerts

The message tone follows the price:

- up to 20,000 RUB: maximum urgency, alarm and fire emoji, and an immediate call to buy;
- 20,001–25,000 RUB: highly enthusiastic excellent-price alert;
- 25,001–30,000 RUB: positive good-price alert;
- 30,001–35,000 RUB: calm notification that the offer fits the agreed limit;
- above 35,000 RUB: no ordinary alert, only daily-summary comparison.

An alert includes:

- alert level: excellent, good, or acceptable;
- price per person and estimated total for four;
- exact dates and number of nights;
- whether this is a round trip or two separate tickets;
- airline and flight numbers when available;
- stops and total duration in each direction;
- baggage status: included, not included, or unknown;
- group availability: confirmed in four-adult search or uncertain;
- live verification timestamp in Asia/Novosibirsk;
- direct link to repeat the search on Aviasales.

Do not repeat the same offer every cycle. Send another alert when at least one condition is true:

- price decreased materially;
- convenience improved;
- four-adult availability changed from uncertain to confirmed;
- baggage became included at a comparable price;
- the previous alert is old enough that a repeat is operationally useful.

The exact material-change values remain configurable. Initial proposal: 1,000 RUB or 5%, whichever is smaller.

## Daily summary

Send one summary per day even when every result exceeds 35,000 RUB. It includes:

- cheapest result overall;
- cheapest direct result;
- cheapest reasonable one-stop result;
- cheapest result with baggage when baggage data is known;
- best result confirmed for four adults;
- price movement compared with the previous daily summary;
- time and outcome of the latest live check;
- a health warning if live verification is blocked or failing.

## Telegram commands

- `/status` — last successful cycle, next scheduled cycle, source health, and CAPTCHA state.
- `/best` — current best normalized offers.
- `/check` — request one manual cycle, protected against repeated concurrent execution.
- `/help` — concise explanation of alert labels.

Only the configured group is allowed to trigger operational commands.

## Failure behavior

- API failure: record it, retry with bounded backoff, and keep the last known state.
- Browser failure: do not label prices as live verified.
- CAPTCHA: record the time, notify the group once, pause browser checks for a cooldown, then retry normally.
- Telegram failure: preserve the pending notification and retry without duplicating it.
- Empty results: treat them as an observation, not proof that no flights exist.

