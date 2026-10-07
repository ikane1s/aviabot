import json
from dataclasses import asdict

from flight_price_bot.formatting import format_daily_summary
from tests.factories import make_offer


def row(price: int, *, stops: int = 0) -> dict[str, object]:
    offer = make_offer(f"offer-{price}-{stops}", price, stops=stops)
    return {
        "price_per_person_rub": price,
        "payload_json": json.dumps(asdict(offer), default=str),
    }


def test_daily_summary_reports_movement_and_categories() -> None:
    message, minimum = format_daily_summary(
        [row(24_000, stops=1), row(28_000, stops=0)],
        previous_minimum=26_000,
        live_status="challenge",
    )

    assert minimum == 24_000
    assert "дешевле на 2 000 ₽" in message
    assert "Лучший прямой: 28 000 ₽" in message
    assert "С одной пересадкой: 24 000 ₽" in message
    assert "challenge" in message
