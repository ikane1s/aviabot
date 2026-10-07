from datetime import UTC, datetime, timedelta

from flight_price_bot.domain.models import (
    BaggageStatus,
    BookingShape,
    FlightLeg,
    GroupAvailability,
    Offer,
)


def make_offer(
    identity: str,
    price: int,
    *,
    stops: int = 0,
    baggage: BaggageStatus = BaggageStatus.UNKNOWN,
    availability: GroupAvailability = GroupAvailability.UNKNOWN,
    live_verified_at: datetime | None = None,
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
        live_verified_at=live_verified_at,
    )
