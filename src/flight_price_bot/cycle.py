import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from flight_price_bot.config import Settings
from flight_price_bot.domain.models import Offer
from flight_price_bot.domain.policy import combine_one_way_fares
from flight_price_bot.domain.search_window import DatePair, generate_date_pairs
from flight_price_bot.providers.aviasales import (
    AviasalesHotTicketsProbe,
    AviasalesPageProbe,
    HotTicketCandidate,
    SearchPageObservation,
    SearchPageStatus,
)
from flight_price_bot.providers.travelpayouts import TravelpayoutsProvider
from flight_price_bot.storage.sqlite import SQLiteStore


@dataclass(frozen=True, slots=True)
class CycleResult:
    cached_offers_found: int
    cached_offers_saved: int
    cached_source_status: str
    live_status: str
    live_url: str | None
    live_offers_found: int = 0
    live_offers_saved: int = 0
    hot_tickets_found: int = 0
    hot_tickets_status: str = "not_run"
    alert_offers: tuple[Offer, ...] = ()


class SearchCycle:
    browser_cooldown = timedelta(hours=24)
    cached_discovery_cooldown = timedelta(hours=6)
    hot_tickets_cooldown = timedelta(hours=6)

    def __init__(self, settings: Settings, store: SQLiteStore) -> None:
        self.settings = settings
        self.store = store
        self._lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self._lock.locked()

    async def run(self) -> CycleResult:
        async with self._lock:
            cached_found, cached_saved, cached_status = await self._run_cached_discovery()
            hot_candidates, hot_status = await self._run_hot_ticket_discovery()
            priority_pairs = self._priority_pairs_from_hot_tickets(hot_candidates)
            live_observation, live_saved = await self._run_live_probe(
                priority_pairs=priority_pairs
            )
            alert_offers = tuple(
                offer
                for offer in live_observation.offers
                if offer.price_per_person_rub <= self.settings.maximum_price_rub
            )
            return CycleResult(
                cached_offers_found=cached_found,
                cached_offers_saved=cached_saved,
                cached_source_status=cached_status,
                live_status=live_observation.status.value,
                live_url=live_observation.final_url or None,
                live_offers_found=len(live_observation.offers),
                live_offers_saved=live_saved,
                hot_tickets_found=len(hot_candidates),
                hot_tickets_status=hot_status,
                alert_offers=alert_offers,
            )

    def date_pairs(self) -> list[DatePair]:
        pairs = generate_date_pairs(
            departure_start=self.settings.departure_start,
            departure_end=self.settings.departure_end,
            return_start=self.settings.return_start,
            return_end=self.settings.return_end,
            concert=self.settings.concert_date,
            min_nights=self.settings.minimum_trip_days,
            max_nights=self.settings.maximum_trip_days,
        )
        return sorted(
            pairs,
            key=lambda pair: (
                abs(pair.nights - self.settings.preferred_trip_days),
                pair.departure,
                pair.return_date,
            ),
        )

    async def _run_cached_discovery(self) -> tuple[int, int, str]:
        token = self.settings.travelpayouts_api_token
        if token is None or not token.get_secret_value():
            return 0, 0, "not_configured"

        now = datetime.now(UTC)
        next_attempt_raw = await self.store.get_state("cached_next_attempt_at")
        if next_attempt_raw and datetime.fromisoformat(next_attempt_raw) > now:
            return 0, 0, "cooldown"

        started_at = now
        found = 0
        saved = 0
        provider = TravelpayoutsProvider(token.get_secret_value())
        status = "success"
        detail: str | None = None
        try:
            pairs = self.date_pairs()
            for pair in pairs:
                offers = await provider.discover(
                    origin=self.settings.origin,
                    destination=self.settings.destination,
                    departure=pair.departure,
                    return_date=pair.return_date,
                )
                found += len(offers)
                for offer in offers:
                    saved += int(await self.store.save_offer(offer))

            outbound_by_date = {}
            for departure in sorted({pair.departure for pair in pairs}):
                outbound_by_date[departure] = await provider.discover_one_way(
                    origin=self.settings.origin,
                    destination=self.settings.destination,
                    departure=departure,
                )
            inbound_by_date = {}
            for return_date in sorted({pair.return_date for pair in pairs}):
                inbound_by_date[return_date] = await provider.discover_one_way(
                    origin=self.settings.destination,
                    destination=self.settings.origin,
                    departure=return_date,
                )
            for pair in pairs:
                outbound_fares = sorted(
                    outbound_by_date[pair.departure],
                    key=lambda fare: fare.price_per_person_rub,
                )[:3]
                inbound_fares = sorted(
                    inbound_by_date[pair.return_date],
                    key=lambda fare: fare.price_per_person_rub,
                )[:3]
                for outbound in outbound_fares:
                    for inbound in inbound_fares:
                        found += 1
                        combined = combine_one_way_fares(outbound, inbound)
                        saved += int(await self.store.save_offer(combined))
        except Exception as error:  # provider boundary records a categorized failure
            status = "error"
            detail = type(error).__name__
        finally:
            await provider.close()

        await self.store.record_search_run(
            source="travelpayouts",
            status=status,
            started_at=started_at,
            detail=detail,
        )
        if status == "success":
            await self.store.set_state(
                "cached_next_attempt_at",
                (now + self.cached_discovery_cooldown).isoformat(),
            )
        return found, saved, status

    async def _run_hot_ticket_discovery(
        self,
    ) -> tuple[tuple[HotTicketCandidate, ...], str]:
        now = datetime.now(UTC)
        browser_next_attempt = await self.store.get_state("browser_next_attempt_at")
        if browser_next_attempt and datetime.fromisoformat(browser_next_attempt) > now:
            return (), "browser_cooldown"
        next_attempt = await self.store.get_state("hot_tickets_next_attempt_at")
        if next_attempt and datetime.fromisoformat(next_attempt) > now:
            return (), "cooldown"

        started_at = now
        probe = AviasalesHotTicketsProbe(
            Path("data/browser-profile"),
            headless=self.settings.headless_browser,
        )
        try:
            observation = await probe.inspect(
                origin=self.settings.origin,
                destination=self.settings.destination,
                departure_month=self.settings.departure_start,
            )
        except Exception as error:
            await self.store.record_search_run(
                source="aviasales_hot_tickets",
                status="error",
                started_at=started_at,
                detail=type(error).__name__,
            )
            return (), "error"

        await self.store.record_search_run(
            source="aviasales_hot_tickets",
            status=observation.status.value,
            started_at=started_at,
            detail=f"{len(observation.candidates)} candidates; {observation.final_url}"[:500],
        )
        if observation.status is SearchPageStatus.CHALLENGE:
            await self.store.set_state(
                "browser_next_attempt_at", (now + self.browser_cooldown).isoformat()
            )
        elif observation.status is SearchPageStatus.READY:
            await self.store.set_state(
                "hot_tickets_next_attempt_at",
                (now + self.hot_tickets_cooldown).isoformat(),
            )
        return observation.candidates, observation.status.value

    def _priority_pairs_from_hot_tickets(
        self, candidates: tuple[HotTicketCandidate, ...]
    ) -> tuple[DatePair, ...]:
        approved = {
            (pair.departure, pair.return_date): pair for pair in self.date_pairs()
        }
        matching = [
            (candidate.price_per_person_rub, approved[key])
            for candidate in candidates
            if candidate.price_per_person_rub <= self.settings.maximum_price_rub
            if (key := (candidate.departure, candidate.return_date)) in approved
        ]
        matching.sort(key=lambda item: item[0])
        return tuple(pair for _, pair in matching[:1])

    async def _run_live_probe(
        self, *, priority_pairs: tuple[DatePair, ...] = ()
    ) -> tuple[SearchPageObservation, int]:
        next_attempt_raw = await self.store.get_state("browser_next_attempt_at")
        now = datetime.now(UTC)
        if next_attempt_raw and datetime.fromisoformat(next_attempt_raw) > now:
            return SearchPageObservation(
                status=SearchPageStatus.CHALLENGE,
                requested_url="",
                final_url="",
                title="cooldown",
                passenger_label_found=False,
                screenshot_path=None,
            ), 0

        pairs = self.date_pairs()
        cursor_raw = await self.store.get_state("browser_pair_cursor")
        cursor = int(cursor_raw or "0") % len(pairs)
        rotating_pairs = [
            pairs[(cursor + offset) % len(pairs)]
            for offset in range(min(self.settings.live_pairs_per_cycle, len(pairs)))
        ]
        selected_pairs = list(priority_pairs)
        selected_pairs.extend(pair for pair in rotating_pairs if pair not in selected_pairs)
        started_at = datetime.now(UTC)
        probe = AviasalesPageProbe(
            Path("data/browser-profile"),
            headless=self.settings.headless_browser,
        )
        try:
            observations: list[SearchPageObservation] = []
            failures: list[str] = []
            saved = 0
            for index, pair in enumerate(selected_pairs):
                observation, error_name = await self._inspect_with_retry(
                    probe=probe,
                    pair=pair,
                    adults=1,
                    screenshot_path=(
                        Path("artifacts/latest-live-check.png")
                        if index == len(selected_pairs) - 1
                        else None
                    ),
                )
                if error_name:
                    failures.append(
                        f"{pair.departure:%Y-%m-%d}/{pair.return_date:%Y-%m-%d}:"
                        f"{error_name}"
                    )
                if observation is None:
                    continue
                observations.append(observation)
                for offer in observation.offers:
                    saved += int(await self.store.save_offer(offer))

                cheapest = min(
                    (offer.price_per_person_rub for offer in observation.offers),
                    default=None,
                )
                if cheapest is not None and cheapest <= self.settings.maximum_price_rub:
                    group_observation, group_error = await self._inspect_with_retry(
                        probe=probe,
                        pair=pair,
                        adults=self.settings.travelers,
                    )
                    if group_error:
                        failures.append(
                            f"{pair.departure:%Y-%m-%d}/{pair.return_date:%Y-%m-%d}:"
                            f"group:{group_error}"
                        )
                    if group_observation is not None:
                        observations.append(group_observation)
                        for offer in group_observation.offers:
                            saved += int(await self.store.save_offer(offer))

                if observation.status is SearchPageStatus.CHALLENGE:
                    break

            await self.store.set_state(
                "browser_pair_cursor",
                str((cursor + len(rotating_pairs)) % len(pairs)),
            )
            if not observations:
                detail = "; ".join(failures) or "no observations"
                await self.store.record_search_run(
                    source="aviasales_browser",
                    status="error",
                    started_at=started_at,
                    detail=detail[:500],
                )
                return SearchPageObservation(
                    status=SearchPageStatus.NAVIGATION_ERROR,
                    requested_url="",
                    final_url="",
                    title=detail[:100],
                    passenger_label_found=False,
                    screenshot_path=None,
                ), saved
            ready = [
                observation
                for observation in observations
                if observation.status is SearchPageStatus.READY
            ]
            representative = ready[-1] if ready else observations[-1]
            observation = SearchPageObservation(
                status=representative.status,
                requested_url=representative.requested_url,
                final_url=representative.final_url,
                title=representative.title,
                passenger_label_found=representative.passenger_label_found,
                screenshot_path=representative.screenshot_path,
                offers=tuple(
                    offer for item in observations for offer in item.offers
                ),
            )
        except Exception as error:  # browser boundary records a categorized failure
            await self.store.record_search_run(
                source="aviasales_browser",
                status="error",
                started_at=started_at,
                detail=type(error).__name__,
            )
            return SearchPageObservation(
                status=SearchPageStatus.NAVIGATION_ERROR,
                requested_url="",
                final_url="",
                title=type(error).__name__,
                passenger_label_found=False,
                screenshot_path=None,
            ), 0

        if observation.status is SearchPageStatus.CHALLENGE:
            await self.store.set_state(
                "browser_next_attempt_at",
                (now + self.browser_cooldown).isoformat(),
            )
        elif observation.status is SearchPageStatus.READY:
            await self.store.delete_state("browser_next_attempt_at")
        await self.store.record_search_run(
            source="aviasales_browser",
            status=observation.status.value,
            started_at=started_at,
            detail=(
                f"{len(observation.offers)} offers; failed={len(failures)}; "
                f"{'; '.join(failures)}; {observation.final_url}"
            )[:500],
        )
        return observation, saved

    async def _inspect_with_retry(
        self,
        *,
        probe: AviasalesPageProbe,
        pair: DatePair,
        adults: int,
        screenshot_path: Path | None = None,
    ) -> tuple[SearchPageObservation | None, str | None]:
        last_error = "navigation_error"
        for attempt in range(2):
            try:
                observation = await probe.inspect(
                    origin=self.settings.origin,
                    destination=self.settings.destination,
                    departure=pair.departure,
                    return_date=pair.return_date,
                    adults=adults,
                    screenshot_path=screenshot_path,
                )
            except Exception as error:  # isolate one route from the rest of the cycle
                last_error = type(error).__name__
            else:
                if observation.status not in {
                    SearchPageStatus.NAVIGATION_ERROR,
                    SearchPageStatus.EMPTY_OR_LOADING,
                }:
                    return observation, None
                last_error = observation.status.value
            if attempt == 0:
                await asyncio.sleep(3)
        return None, last_error

