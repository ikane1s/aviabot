from datetime import date

import pytest

from flight_price_bot.domain.search_window import dates_between, generate_date_pairs


def test_approved_window_produces_only_valid_concert_trips() -> None:
    pairs = generate_date_pairs(
        departure_start=date(2026, 12, 15),
        departure_end=date(2026, 12, 18),
        return_start=date(2026, 12, 20),
        return_end=date(2026, 12, 23),
        concert=date(2026, 12, 19),
    )

    assert pairs
    assert all(pair.departure <= date(2026, 12, 19) < pair.return_date for pair in pairs)
    assert all(3 <= pair.nights <= 7 for pair in pairs)


def test_dates_between_rejects_reversed_range() -> None:
    with pytest.raises(ValueError):
        list(dates_between(date(2026, 12, 2), date(2026, 12, 1)))

