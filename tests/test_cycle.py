from datetime import date

from flight_price_bot.domain.search_window import generate_date_pairs


def test_approved_window_has_fourteen_combinations() -> None:
    pairs = generate_date_pairs(
        departure_start=date(2026, 12, 15),
        departure_end=date(2026, 12, 18),
        return_start=date(2026, 12, 20),
        return_end=date(2026, 12, 23),
        concert=date(2026, 12, 19),
    )

    assert len(pairs) == 14

