from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class PriceLevel(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    OVER_BUDGET = "over_budget"


class BaggageStatus(StrEnum):
    INCLUDED = "included"
    NOT_INCLUDED = "not_included"
    UNKNOWN = "unknown"


class GroupAvailability(StrEnum):
    CONFIRMED_FOR_FOUR = "confirmed_for_four"
    ONE_ADULT_ONLY = "one_adult_only"
    UNKNOWN = "unknown"


class BookingShape(StrEnum):
    ROUND_TRIP = "round_trip"
    SEPARATE_ONE_WAYS = "separate_one_ways"


@dataclass(frozen=True, slots=True)
class FlightLeg:
    origin: str
    destination: str
    departure_at: datetime
    arrival_at: datetime
    stops: int
    duration_minutes: int
    airline_codes: tuple[str, ...] = ()
    flight_numbers: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Offer:
    identity: str
    outbound: FlightLeg
    inbound: FlightLeg
    price_per_person_rub: int
    adults_quoted: int
    baggage: BaggageStatus
    group_availability: GroupAvailability
    booking_shape: BookingShape
    source: str
    result_url: str
    observed_at: datetime
    live_verified_at: datetime | None = None

    @property
    def departure_date(self) -> date:
        return self.outbound.departure_at.date()

    @property
    def return_date(self) -> date:
        return self.inbound.departure_at.date()

    @property
    def nights(self) -> int:
        return (self.return_date - self.departure_date).days

    @property
    def estimated_total_for_four_rub(self) -> int:
        return self.price_per_person_rub * 4

    @property
    def total_stops(self) -> int:
        return self.outbound.stops + self.inbound.stops

    @property
    def is_direct(self) -> bool:
        return self.total_stops == 0


@dataclass(frozen=True, slots=True)
class OneWayFare:
    identity: str
    leg: FlightLeg
    price_per_person_rub: int
    baggage: BaggageStatus
    source: str
    result_url: str
    observed_at: datetime

