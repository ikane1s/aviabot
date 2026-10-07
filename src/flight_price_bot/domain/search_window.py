from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta

from flight_price_bot.domain.policy import is_valid_trip_window


@dataclass(frozen=True, slots=True)
class DatePair:
    departure: date
    return_date: date

    @property
    def nights(self) -> int:
        return (self.return_date - self.departure).days


def dates_between(start: date, end: date) -> Iterator[date]:
    if end < start:
        raise ValueError("end date must not precede start date")

    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def generate_date_pairs(
    *,
    departure_start: date,
    departure_end: date,
    return_start: date,
    return_end: date,
    concert: date,
    min_nights: int = 3,
    max_nights: int = 7,
) -> list[DatePair]:
    return [
        DatePair(departure=departure, return_date=return_date)
        for departure in dates_between(departure_start, departure_end)
        for return_date in dates_between(return_start, return_end)
        if is_valid_trip_window(
            departure,
            return_date,
            concert,
            min_nights=min_nights,
            max_nights=max_nights,
        )
    ]

