from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from flight_price_bot.domain.models import (
    BaggageStatus,
    BookingShape,
    FlightLeg,
    GroupAvailability,
    Offer,
)
from flight_price_bot.storage.sqlite import SQLiteStore


def make_offer(identity: str, price: int) -> Offer:
    departure_at = datetime(2026, 12, 16, 10, tzinfo=UTC)
    return_at = datetime(2026, 12, 21, 10, tzinfo=UTC)
    return Offer(
        identity=identity,
        outbound=FlightLeg(
            origin="OVB",
            destination="EVN",
            departure_at=departure_at,
            arrival_at=departure_at + timedelta(hours=5),
            stops=0,
            duration_minutes=300,
        ),
        inbound=FlightLeg(
            origin="EVN",
            destination="OVB",
            departure_at=return_at,
            arrival_at=return_at + timedelta(hours=5),
            stops=0,
            duration_minutes=300,
        ),
        price_per_person_rub=price,
        adults_quoted=1,
        baggage=BaggageStatus.UNKNOWN,
        group_availability=GroupAvailability.UNKNOWN,
        booking_shape=BookingShape.ROUND_TRIP,
        source="test",
        result_url="https://example.test/search",
        observed_at=departure_at,
    )


@pytest.mark.asyncio
async def test_offer_observation_is_idempotent(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "history.db")
    await store.initialize()
    offer = make_offer("same-offer", 24_000)

    assert await store.save_offer(offer)
    assert not await store.save_offer(offer)
    assert await store.count_offer_observations() == 1

