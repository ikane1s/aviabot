from datetime import UTC, date, datetime, timedelta

import pytest

from flight_price_bot.domain.models import (
    BaggageStatus,
    BookingShape,
    FlightLeg,
    GroupAvailability,
    Offer,
    PriceLevel,
)
from flight_price_bot.domain.policy import classify_price, is_valid_trip_window, select_best_offers


@pytest.mark.parametrize(
    ("price", "expected"),
    [
        (20_000, PriceLevel.EXCELLENT),
        (25_000, PriceLevel.EXCELLENT),
        (25_001, PriceLevel.GOOD),
        (30_000, PriceLevel.GOOD),
        (30_001, PriceLevel.ACCEPTABLE),
        (35_000, PriceLevel.ACCEPTABLE),
        (35_001, PriceLevel.OVER_BUDGET),
    ],
)
def test_price_levels_match_product_policy(price: int, expected: PriceLevel) -> None:
    assert classify_price(price) is expected


def test_trip_must_contain_concert_and_last_three_to_seven_nights() -> None:
    concert = date(2026, 12, 19)

    assert is_valid_trip_window(date(2026, 12, 16), date(2026, 12, 21), concert)
    assert not is_valid_trip_window(date(2026, 12, 20), date(2026, 12, 23), concert)
    assert not is_valid_trip_window(date(2026, 12, 18), date(2026, 12, 20), concert)
    assert not is_valid_trip_window(date(2026, 12, 12), date(2026, 12, 21), concert)


def make_offer(
    identity: str,
    price: int,
    *,
    stops: int = 0,
    baggage: BaggageStatus = BaggageStatus.UNKNOWN,
    availability: GroupAvailability = GroupAvailability.UNKNOWN,
) -> Offer:
    departure_at = datetime(2026, 12, 16, 10, tzinfo=UTC)
    return_at = datetime(2026, 12, 21, 10, tzinfo=UTC)
    return Offer(
        identity=identity,
        outbound=FlightLeg(
            origin="OVB",
            destination="EVN",
            departure_at=departure_at,
            arrival_at=departure_at + timedelta(hours=5),
            stops=stops,
            duration_minutes=300,
        ),
        inbound=FlightLeg(
            origin="EVN",
            destination="OVB",
            departure_at=return_at,
            arrival_at=return_at + timedelta(hours=5),
            stops=stops,
            duration_minutes=300,
        ),
        price_per_person_rub=price,
        adults_quoted=4 if availability is GroupAvailability.CONFIRMED_FOR_FOUR else 1,
        baggage=baggage,
        group_availability=availability,
        booking_shape=BookingShape.ROUND_TRIP,
        source="test",
        result_url="https://example.test/search",
        observed_at=departure_at,
    )


def test_best_views_keep_price_and_convenience_tradeoffs_visible() -> None:
    cheapest_connection = make_offer("connection", 21_000, stops=1)
    direct = make_offer("direct", 24_000)
    baggage = make_offer("baggage", 25_000, baggage=BaggageStatus.INCLUDED)
    group = make_offer(
        "group",
        26_000,
        availability=GroupAvailability.CONFIRMED_FOR_FOUR,
    )

    best = select_best_offers([direct, cheapest_connection, baggage, group])

    assert best.overall is cheapest_connection
    assert best.direct is direct
    assert best.one_stop is cheapest_connection
    assert best.with_baggage is baggage
    assert best.confirmed_for_four is group

