from datetime import UTC, datetime

from flight_price_bot.domain.models import BaggageStatus, GroupAvailability
from flight_price_bot.formatting import format_offer_alert
from flight_price_bot.notifications import offer_notification_key
from tests.factories import make_offer


def test_alert_explains_price_group_and_live_status() -> None:
    offer = make_offer(
        "live-offer",
        24_000,
        baggage=BaggageStatus.INCLUDED,
        availability=GroupAvailability.CONFIRMED_FOR_FOUR,
        live_verified_at=datetime(2026, 10, 7, 5, 30, tzinfo=UTC),
    )

    message = format_offer_alert(offer)

    assert "Отличная цена: 24 000 ₽" in message
    assert "96 000 ₽" in message
    assert "вариант найден для четырёх" in message
    assert "багаж включён" in message
    assert "07.10.2026 12:30" in message


def test_notification_key_changes_for_meaningful_price_bucket() -> None:
    cheaper = make_offer("same", 24_000)
    costlier = make_offer("same", 25_000)

    assert offer_notification_key(cheaper) != offer_notification_key(costlier)

