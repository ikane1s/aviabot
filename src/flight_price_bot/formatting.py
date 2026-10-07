import json
from datetime import datetime
from zoneinfo import ZoneInfo

from flight_price_bot.cycle import CycleResult
from flight_price_bot.domain.models import (
    BaggageStatus,
    BookingShape,
    GroupAvailability,
    Offer,
)
from flight_price_bot.domain.policy import (
    DEFAULT_PRICE_THRESHOLDS,
    PriceThresholds,
    classify_price,
)


def format_cycle_result(result: CycleResult) -> str:
    cached = {
        "not_configured": "не настроен",
        "success": "работает",
        "error": "ошибка",
        "cooldown": "используются недавние данные",
    }.get(result.cached_source_status, result.cached_source_status)
    live = {
        "ready": "страница доступна",
        "challenge": "SmartCaptcha, включена пауза",
        "empty_or_loading": "выдача не загрузилась",
        "navigation_error": "ошибка браузера",
    }.get(result.live_status, result.live_status)
    return (
        "Проверка завершена.\n"
        f"Travelpayouts: {cached}; найдено {result.cached_offers_found}, "
        f"новых наблюдений {result.cached_offers_saved}.\n"
        f"Aviasales: {live}; найдено {result.live_offers_found}, "
        f"новых наблюдений {result.live_offers_saved}."
    )


def format_offer_alert(
    offer: Offer,
    *,
    thresholds: PriceThresholds = DEFAULT_PRICE_THRESHOLDS,
    timezone: str = "Asia/Novosibirsk",
) -> str:
    level = {
        "excellent": "Отличная цена",
        "good": "Хорошая цена",
        "acceptable": "Допустимая цена",
        "over_budget": "Выше установленного максимума",
    }[classify_price(offer.price_per_person_rub, thresholds).value]
    route_type = (
        "единый билет туда-обратно"
        if offer.booking_shape is BookingShape.ROUND_TRIP
        else "два отдельных билета"
    )
    availability = {
        GroupAvailability.CONFIRMED_FOR_FOUR: "вариант найден для четырёх взрослых",
        GroupAvailability.ONE_ADULT_ONLY: "цена найдена только для одного взрослого",
        GroupAvailability.UNKNOWN: "наличие для четырёх пока не подтверждено",
    }[offer.group_availability]
    baggage = {
        BaggageStatus.INCLUDED: "багаж включён",
        BaggageStatus.NOT_INCLUDED: "без зарегистрированного багажа",
        BaggageStatus.UNKNOWN: "багаж нужно проверить",
    }[offer.baggage]
    stops = (
        "прямые рейсы"
        if offer.is_direct
        else f"пересадки: туда {offer.outbound.stops}, обратно {offer.inbound.stops}"
    )
    verified = (
        _format_time(offer.live_verified_at, timezone)
        if offer.live_verified_at
        else "живой проверкой не подтверждено"
    )
    return (
        f"{level}: {offer.price_per_person_rub:,} ₽ на человека\n"
        f"Ориентир на четверых: {offer.estimated_total_for_four_rub:,} ₽\n"
        f"{offer.departure_date:%d.%m.%Y} — {offer.return_date:%d.%m.%Y}, "
        f"{offer.nights} ночей\n"
        f"{route_type}; {stops}; {baggage}\n"
        f"{availability}\n"
        f"Проверка: {verified}\n"
        f"{offer.result_url}"
    ).replace(",", " ")


def _format_time(value: datetime, timezone: str) -> str:
    localized = value.astimezone(ZoneInfo(timezone))
    return localized.strftime("%d.%m.%Y %H:%M")


def format_daily_summary(
    rows: list[dict[str, object]],
    *,
    previous_minimum: int | None,
    live_status: str,
) -> tuple[str, int | None]:
    parsed = [(_row_price(row), json.loads(str(row["payload_json"]))) for row in rows]
    parsed.sort(key=lambda item: item[0])
    if not parsed:
        return (
            "Ежедневная сводка OVB ↔ EVN\n"
            "Предложений в базе пока нет.\n"
            f"Живая проверка Aviasales: {live_status}.",
            None,
        )

    minimum = parsed[0][0]
    direct = next(
        (
            price
            for price, payload in parsed
            if payload["outbound"]["stops"] == 0 and payload["inbound"]["stops"] == 0
        ),
        None,
    )
    one_stop = next(
        (
            price
            for price, payload in parsed
            if max(payload["outbound"]["stops"], payload["inbound"]["stops"]) == 1
        ),
        None,
    )
    baggage = next(
        (price for price, payload in parsed if payload["baggage"] == "included"),
        None,
    )
    group = next(
        (
            price
            for price, payload in parsed
            if payload["group_availability"] == "confirmed_for_four"
        ),
        None,
    )
    movement = _format_movement(minimum, previous_minimum)
    lines = [
        "Ежедневная сводка OVB ↔ EVN",
        f"Минимум: {_rub(minimum)}{movement}",
        f"Лучший прямой: {_rub_or_dash(direct)}",
        f"С одной пересадкой: {_rub_or_dash(one_stop)}",
        f"С багажом: {_rub_or_dash(baggage)}",
        f"Подтверждено для четырёх: {_rub_or_dash(group)}",
        f"Живая проверка Aviasales: {live_status}.",
    ]
    return "\n".join(lines), minimum


def _row_price(row: dict[str, object]) -> int:
    return int(row["price_per_person_rub"])


def _rub(value: int) -> str:
    return f"{value:,} ₽".replace(",", " ")


def _rub_or_dash(value: int | None) -> str:
    return _rub(value) if value is not None else "нет данных"


def _format_movement(current: int, previous: int | None) -> str:
    if previous is None:
        return ""
    difference = current - previous
    if difference == 0:
        return " (без изменений)"
    direction = "дороже" if difference > 0 else "дешевле"
    return f" ({direction} на {_rub(abs(difference))})"

