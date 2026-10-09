from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from flight_price_bot.cycle import SearchCycle
from flight_price_bot.domain.search_window import generate_date_pairs
from flight_price_bot.providers.aviasales import (
    HotTicketCandidate,
    SearchPageObservation,
    SearchPageStatus,
)


def test_approved_window_has_fourteen_combinations_for_four_to_seven_days() -> None:
    pairs = generate_date_pairs(
        departure_start=date(2026, 12, 14),
        departure_end=date(2026, 12, 18),
        return_start=date(2026, 12, 20),
        return_end=date(2026, 12, 23),
        concert=date(2026, 12, 19),
        min_nights=4,
        max_nights=7,
    )

    assert len(pairs) == 14
    assert min(pair.nights for pair in pairs) == 4
    assert max(pair.nights for pair in pairs) == 7


class FakeStore:
    def __init__(self) -> None:
        self.state: dict[str, str] = {}
        self.runs: list[dict[str, object]] = []

    async def get_state(self, key: str) -> str | None:
        return self.state.get(key)

    async def set_state(self, key: str, value: str) -> None:
        self.state[key] = value

    async def delete_state(self, key: str) -> None:
        self.state.pop(key, None)

    async def save_offer(self, offer: object) -> bool:
        return True

    async def record_search_run(self, **values: object) -> int:
        self.runs.append(values)
        return len(self.runs)


class FailingFirstPairProbe:
    calls = 0

    def __init__(self, profile_dir: Path, *, headless: bool) -> None:
        pass

    async def inspect(self, **values: object) -> SearchPageObservation:
        type(self).calls += 1
        if type(self).calls <= 2:
            raise ConnectionError("temporary network failure")
        return SearchPageObservation(
            status=SearchPageStatus.READY,
            requested_url="https://example.test/requested",
            final_url="https://example.test/result",
            title="ready",
            passenger_label_found=True,
            screenshot_path=None,
        )


@pytest.mark.asyncio
async def test_one_failed_pair_does_not_abort_remaining_pairs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        departure_start=date(2026, 12, 14),
        departure_end=date(2026, 12, 18),
        return_start=date(2026, 12, 20),
        return_end=date(2026, 12, 23),
        concert_date=date(2026, 12, 19),
        minimum_trip_days=4,
        maximum_trip_days=7,
        preferred_trip_days=5,
        live_pairs_per_cycle=3,
        headless_browser=False,
        origin="OVB",
        destination="EVN",
        travelers=4,
        maximum_price_rub=35_000,
    )
    store = FakeStore()
    monkeypatch.setattr("flight_price_bot.cycle.AviasalesPageProbe", FailingFirstPairProbe)
    FailingFirstPairProbe.calls = 0

    observation, _ = await SearchCycle(settings, store)._run_live_probe()

    assert observation.status is SearchPageStatus.READY
    assert FailingFirstPairProbe.calls == 4
    assert store.state["browser_pair_cursor"] == "3"
    assert store.runs[-1]["status"] == "ready"
    assert "failed=1" in str(store.runs[-1]["detail"])


def test_hot_ticket_prioritization_keeps_only_approved_cheap_pair() -> None:
    settings = SimpleNamespace(
        departure_start=date(2026, 12, 14),
        departure_end=date(2026, 12, 18),
        return_start=date(2026, 12, 20),
        return_end=date(2026, 12, 23),
        concert_date=date(2026, 12, 19),
        minimum_trip_days=4,
        maximum_trip_days=7,
        preferred_trip_days=5,
        maximum_price_rub=35_000,
    )
    candidates = (
        HotTicketCandidate(
            departure=date(2026, 12, 14),
            return_date=date(2026, 12, 20),
            price_per_person_rub=31_305,
            result_url="https://example.test/approved-hot-ticket",
        ),
        HotTicketCandidate(
            departure=date(2026, 12, 15),
            return_date=date(2026, 12, 20),
            price_per_person_rub=32_000,
            result_url="https://example.test/approved",
        ),
        HotTicketCandidate(
            departure=date(2026, 12, 16),
            return_date=date(2026, 12, 21),
            price_per_person_rub=36_000,
            result_url="https://example.test/too-expensive",
        ),
    )

    priority = SearchCycle(settings, FakeStore())._priority_pairs_from_hot_tickets(
        candidates
    )

    assert [(pair.departure, pair.return_date) for pair in priority] == [
        (date(2026, 12, 14), date(2026, 12, 20))
    ]

