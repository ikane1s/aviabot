from datetime import UTC, date, datetime

import pytest

from flight_price_bot.domain.models import BaggageStatus, GroupAvailability
from flight_price_bot.providers.aviasales import (
    build_hot_tickets_url,
    build_search_url,
    parse_hot_ticket_candidate,
    parse_ticket_card,
)

DIRECT_CARD = """Самый дешёвый
144 968 ₽
Оптимальный
199 608 ₽ с багажом 23 кг — 4 шт
Ручная кладь 10 кг — 4 шт
12:30
Новосибирск
16 дек, ср
OVB
5 ⁠ч 10 ⁠м в пути, прямой
EVN
14:40
Ереван
16 дек, ср
15:40
Ереван
21 дек, пн
EVN
4 ⁠ч 35 ⁠м в пути, прямой
OVB
23:15
Новосибирск
21 дек, пн"""


def test_search_url_encodes_four_adults() -> None:
    url = build_search_url(
        origin="OVB",
        destination="EVN",
        departure=date(2026, 12, 16),
        return_date=date(2026, 12, 21),
        adults=4,
    )

    assert url == "https://www.aviasales.ru/search/OVB1612EVN21124"


def test_search_url_rejects_impossible_return() -> None:
    with pytest.raises(ValueError):
        build_search_url(
            origin="OVB",
            destination="EVN",
            departure=date(2026, 12, 21),
            return_date=date(2026, 12, 16),
            adults=4,
        )


def test_hot_ticket_link_extracts_first_price_and_round_trip_dates() -> None:
    candidate = parse_hot_ticket_candidate(
        href=(
            "https://www.aviasales.ru/search/OVB1412EVN20121"
            "?expected_price=31305&utm_source=explore-hot_tickets"
        ),
        text="31\u202f305 ₽ 40\u202f132 ₽",
        origin="OVB",
        destination="EVN",
        departure_year=2026,
    )

    assert build_hot_tickets_url(origin="OVB", destination="EVN") == (
        "https://www.aviasales.ru/hottickets/ovb/evn"
    )
    assert candidate.departure == date(2026, 12, 14)
    assert candidate.return_date == date(2026, 12, 20)
    assert candidate.price_per_person_rub == 31_305


def test_parse_four_adult_card_normalizes_total_to_per_person() -> None:
    observed_at = datetime(2026, 10, 7, 8, tzinfo=UTC)
    offer = parse_ticket_card(
        text=DIRECT_CARD,
        card_id="bdui-ticket-preview-normal-stable",
        image_urls=["https://img.avs.io/pics/al_square/S7@avif?rs=fit:120:120"],
        origin="OVB",
        destination="EVN",
        departure=date(2026, 12, 16),
        return_date=date(2026, 12, 21),
        adults=4,
        result_url="https://www.aviasales.ru/search/example",
        observed_at=observed_at,
    )

    assert offer.price_per_person_rub == 36_242
    assert offer.group_availability is GroupAvailability.CONFIRMED_FOR_FOUR
    assert offer.baggage is BaggageStatus.NOT_INCLUDED
    assert offer.outbound.stops == 0
    assert offer.outbound.duration_minutes == 310
    assert offer.outbound.airline_codes == ("S7",)
    assert offer.inbound.duration_minutes == 275
    assert offer.outbound.departure_at.hour == 12
    assert offer.inbound.departure_at.hour == 15

