from datetime import date

from flight_price_bot.domain.search_window import generate_date_pairs


def test_approved_window_has_twelve_combinations_for_four_to_seven_days() -> None:
    pairs = generate_date_pairs(
        departure_start=date(2026, 12, 15),
        departure_end=date(2026, 12, 18),
        return_start=date(2026, 12, 20),
        return_end=date(2026, 12, 23),
        concert=date(2026, 12, 19),
        min_nights=4,
        max_nights=7,
    )

    assert len(pairs) == 12
    assert min(pair.nights for pair in pairs) == 4
    assert max(pair.nights for pair in pairs) == 7

