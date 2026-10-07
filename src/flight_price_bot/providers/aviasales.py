import hashlib
import re
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from flight_price_bot.domain.models import (
    BaggageStatus,
    BookingShape,
    FlightLeg,
    GroupAvailability,
    Offer,
)

CHALLENGE_MARKERS = ("smartcaptcha.cloud.yandex.ru/advanced",)
PRICE_RE = re.compile(r"^(\d[\d ]*)\s*₽$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")
AIRLINE_RE = re.compile(r"/([A-Z0-9]{2})@", re.IGNORECASE)
AIRPORT_TIMEZONES = {"OVB": "Asia/Novosibirsk", "EVN": "Asia/Yerevan"}


class SearchPageStatus(StrEnum):
    READY = "ready"
    CHALLENGE = "challenge"
    EMPTY_OR_LOADING = "empty_or_loading"
    NAVIGATION_ERROR = "navigation_error"


@dataclass(frozen=True, slots=True)
class SearchPageObservation:
    status: SearchPageStatus
    requested_url: str
    final_url: str
    title: str
    passenger_label_found: bool
    screenshot_path: Path | None
    offers: tuple[Offer, ...] = ()


def build_search_url(
    *, origin: str, destination: str, departure: date, return_date: date, adults: int
) -> str:
    if not 1 <= adults <= 9:
        raise ValueError("adults must be between 1 and 9")
    if return_date <= departure:
        raise ValueError("return date must follow departure date")
    route = f"{origin.upper()}{departure:%d%m}{destination.upper()}{return_date:%d%m}{adults}"
    return f"https://www.aviasales.ru/search/{route}"


def parse_ticket_card(
    *,
    text: str,
    card_id: str,
    image_urls: list[str],
    origin: str,
    destination: str,
    departure: date,
    return_date: date,
    adults: int,
    result_url: str,
    observed_at: datetime,
) -> Offer:
    lines = [_normalize_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    total_price = next(
        int(match.group(1).replace(" ", ""))
        for line in lines
        if (match := PRICE_RE.fullmatch(line))
    )
    price_per_person = round(total_price / adults)

    origin = origin.upper()
    destination = destination.upper()
    outbound_origin = lines.index(origin)
    outbound_destination = lines.index(destination, outbound_origin + 1)
    inbound_origin = lines.index(destination, outbound_destination + 1)
    inbound_destination = lines.index(origin, inbound_origin + 1)
    airline_codes = _airline_codes(image_urls)

    outbound = _parse_leg(
        lines=lines,
        origin_index=outbound_origin,
        destination_index=outbound_destination,
        origin=origin,
        destination=destination,
        expected_departure=departure,
        airline_codes=airline_codes,
    )
    inbound = _parse_leg(
        lines=lines,
        origin_index=inbound_origin,
        destination_index=inbound_destination,
        origin=destination,
        destination=origin,
        expected_departure=return_date,
        airline_codes=airline_codes,
    )
    identity_material = "|".join(
        [
            card_id,
            outbound.departure_at.isoformat(),
            inbound.departure_at.isoformat(),
            ",".join(airline_codes),
        ]
    )
    return Offer(
        identity=hashlib.sha256(identity_material.encode()).hexdigest()[:24],
        outbound=outbound,
        inbound=inbound,
        price_per_person_rub=price_per_person,
        adults_quoted=adults,
        baggage=_baggage_status(lines),
        group_availability=(
            GroupAvailability.CONFIRMED_FOR_FOUR
            if adults >= 4
            else GroupAvailability.ONE_ADULT_ONLY
        ),
        booking_shape=BookingShape.ROUND_TRIP,
        source="aviasales_live",
        result_url=result_url,
        observed_at=observed_at,
        live_verified_at=observed_at,
    )


def _normalize_line(value: str) -> str:
    cleaned = value.replace("\xa0", " ").replace("\u202f", " ").replace("\u2060", "")
    return " ".join(cleaned.split())


def _airline_codes(image_urls: list[str]) -> tuple[str, ...]:
    codes: list[str] = []
    for url in image_urls:
        match = AIRLINE_RE.search(url)
        if match and match.group(1).upper() not in codes:
            codes.append(match.group(1).upper())
    return tuple(codes)


def _parse_leg(
    *,
    lines: list[str],
    origin_index: int,
    destination_index: int,
    origin: str,
    destination: str,
    expected_departure: date,
    airline_codes: tuple[str, ...],
) -> FlightLeg:
    departure_time = _nearest_time_before(lines, origin_index)
    arrival_time = _nearest_time_after(lines, destination_index)
    duration_line = next(
        line for line in lines[origin_index + 1 : destination_index] if "в пути" in line
    )
    duration_minutes = _duration_minutes(duration_line)
    departure_at = _local_datetime(expected_departure, departure_time, origin)
    calculated_arrival = departure_at.astimezone(UTC) + timedelta(minutes=duration_minutes)
    arrival_at = calculated_arrival.astimezone(ZoneInfo(_timezone_for(destination)))
    arrival_at = arrival_at.replace(
        hour=int(arrival_time[:2]), minute=int(arrival_time[3:]), second=0, microsecond=0
    )
    return FlightLeg(
        origin=origin,
        destination=destination,
        departure_at=departure_at,
        arrival_at=arrival_at,
        stops=_stops(duration_line),
        duration_minutes=duration_minutes,
        airline_codes=airline_codes,
    )


def _nearest_time_before(lines: list[str], index: int) -> str:
    return next(line for line in reversed(lines[:index]) if TIME_RE.fullmatch(line))


def _nearest_time_after(lines: list[str], index: int) -> str:
    return next(line for line in lines[index + 1 :] if TIME_RE.fullmatch(line))


def _duration_minutes(value: str) -> int:
    days = re.search(r"(\d+)\s*д", value)
    hours = re.search(r"(\d+)\s*ч", value)
    minutes = re.search(r"(\d+)\s*м", value)
    return (
        (int(days.group(1)) * 24 * 60 if days else 0)
        + (int(hours.group(1)) * 60 if hours else 0)
        + (int(minutes.group(1)) if minutes else 0)
    )


def _stops(value: str) -> int:
    if "прямой" in value:
        return 0
    match = re.search(r"(\d+)\s+пересад", value)
    if not match:
        raise ValueError(f"Cannot parse stops from {value!r}")
    return int(match.group(1))


def _local_datetime(value: date, clock: str, airport: str) -> datetime:
    return datetime(
        value.year,
        value.month,
        value.day,
        int(clock[:2]),
        int(clock[3:]),
        tzinfo=ZoneInfo(_timezone_for(airport)),
    )


def _timezone_for(airport: str) -> str:
    return AIRPORT_TIMEZONES.get(airport, "UTC")


def _baggage_status(lines: list[str]) -> BaggageStatus:
    if any("с багажом" in line.lower() for line in lines):
        return BaggageStatus.NOT_INCLUDED
    if any("багаж" in line.lower() for line in lines):
        return BaggageStatus.INCLUDED
    return BaggageStatus.UNKNOWN


class AviasalesPageProbe:
    def __init__(
        self, profile_dir: Path, *, headless: bool = False, channel: str = "chrome"
    ) -> None:
        self.profile_dir = profile_dir
        self.headless = headless
        self.channel = channel

    async def inspect(
        self,
        *,
        origin: str,
        destination: str,
        departure: date,
        return_date: date,
        adults: int,
        screenshot_path: Path | None = None,
    ) -> SearchPageObservation:
        url = build_search_url(
            origin=origin,
            destination=destination,
            departure=departure,
            return_date=return_date,
            adults=adults,
        )
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        if screenshot_path:
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                str(self.profile_dir),
                channel=self.channel,
                headless=self.headless,
                args=[
                    "--disable-dev-shm-usage",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-background-networking",
                ],
                locale="ru-RU",
                timezone_id="Asia/Novosibirsk",
                viewport={"width": 1440, "height": 1000},
            )
            try:
                page = context.pages[0] if context.pages else await context.new_page()
                navigation_failed = False
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                    with suppress(PlaywrightTimeoutError):
                        await page.locator(
                            '[data-test-id^="bdui-ticket-preview-normal-"]'
                        ).first.wait_for(timeout=35_000)
                        await page.wait_for_timeout(5_000)
                except PlaywrightTimeoutError:
                    navigation_failed = True

                body_text = await page.locator("body").inner_text(timeout=10_000)
                frame_urls = " ".join(frame.url.lower() for frame in page.frames)
                challenge = any(marker in frame_urls for marker in CHALLENGE_MARKERS)
                passenger_labels = (
                    ("1 пассажир",)
                    if adults == 1
                    else (f"{adults} пассажира", f"{adults} пассажиров")
                )
                passenger_label_found = any(
                    label in body_text for label in passenger_labels
                )
                raw_cards = await page.locator(
                    '[data-test-id^="bdui-ticket-preview-normal-"]'
                ).evaluate_all(
                    """
                    cards => cards.map(card => ({
                      id: card.getAttribute('data-test-id') || '',
                      text: (card.innerText || '').trim(),
                      images: Array.from(card.querySelectorAll('img')).map(image => image.src)
                    }))
                    """
                )
                if screenshot_path:
                    await page.screenshot(path=str(screenshot_path), full_page=True)

                has_visible_prices = bool(raw_cards)
                if challenge and not has_visible_prices:
                    status = SearchPageStatus.CHALLENGE
                elif has_visible_prices:
                    status = SearchPageStatus.READY
                elif navigation_failed:
                    status = SearchPageStatus.NAVIGATION_ERROR
                else:
                    status = SearchPageStatus.EMPTY_OR_LOADING

                observed_at = datetime.now(UTC)
                offers: list[Offer] = []
                for card in raw_cards:
                    try:
                        offers.append(
                            parse_ticket_card(
                                text=card["text"],
                                card_id=card["id"],
                                image_urls=card["images"],
                                origin=origin,
                                destination=destination,
                                departure=departure,
                                return_date=return_date,
                                adults=adults,
                                result_url=page.url,
                                observed_at=observed_at,
                            )
                        )
                    except (StopIteration, ValueError):
                        continue

                return SearchPageObservation(
                    status=status,
                    requested_url=url,
                    final_url=page.url,
                    title=await page.title(),
                    passenger_label_found=passenger_label_found,
                    screenshot_path=screenshot_path,
                    offers=tuple(offers),
                )
            finally:
                with suppress(Exception):
                    await context.close()
