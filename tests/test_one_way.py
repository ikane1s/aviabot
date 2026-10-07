from datetime import UTC, datetime, timedelta

from flight_price_bot.domain.models import BaggageStatus, FlightLeg, OneWayFare
from flight_price_bot.domain.policy import combine_one_way_fares


def fare(
    identity: str,
    origin: str,
    destination: str,
    departure_at: datetime,
    price: int,
    baggage: BaggageStatus,
) -> OneWayFare:
    return OneWayFare(
        identity=identity,
        leg=FlightLeg(
            origin=origin,
            destination=destination,
            departure_at=departure_at,
            arrival_at=departure_at + timedelta(hours=6),
            stops=0,
            duration_minutes=360,
        ),
        price_per_person_rub=price,
        baggage=baggage,
        source="test",
        result_url="https://example.test",
        observed_at=departure_at,
    )


def test_separate_one_ways_are_combined_per_person() -> None:
    outbound = fare(
        "out",
        "OVB",
        "EVN",
        datetime(2026, 12, 16, tzinfo=UTC),
        11_000,
        BaggageStatus.INCLUDED,
    )
    inbound = fare(
        "back",
        "EVN",
        "OVB",
        datetime(2026, 12, 21, tzinfo=UTC),
        13_000,
        BaggageStatus.UNKNOWN,
    )

    combined = combine_one_way_fares(outbound, inbound)

    assert combined.price_per_person_rub == 24_000
    assert combined.estimated_total_for_four_rub == 96_000
    assert combined.baggage is BaggageStatus.UNKNOWN
