import hashlib
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urljoin

import httpx

from flight_price_bot.domain.models import (
    BaggageStatus,
    BookingShape,
    FlightLeg,
    GroupAvailability,
    Offer,
    OneWayFare,
)


class TravelpayoutsError(RuntimeError):
    pass


class TravelpayoutsProvider:
    endpoint = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"

    def __init__(self, token: str, client: httpx.AsyncClient | None = None) -> None:
        if not token:
            raise ValueError("Travelpayouts token is required")
        self._token = token
        self._client = client or httpx.AsyncClient(timeout=30, follow_redirects=True)
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def discover(
        self,
        *,
        origin: str,
        destination: str,
        departure: date,
        return_date: date,
    ) -> list[Offer]:
        response = await self._client.get(
            self.endpoint,
            headers={"X-Access-Token": self._token, "Accept-Encoding": "gzip, deflate"},
            params={
                "origin": origin,
                "destination": destination,
                "departure_at": departure.isoformat(),
                "return_at": return_date.isoformat(),
                "one_way": "false",
                "direct": "false",
                "currency": "rub",
                "market": "ru",
                "sorting": "price",
                "limit": 100,
                "page": 1,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            raise TravelpayoutsError(str(payload.get("error") or "unsuccessful response"))

        offers: list[Offer] = []
        for item in payload.get("data", []):
            offer = self._normalize(item)
            if offer is not None:
                offers.append(offer)
        return offers

    async def discover_one_way(
        self,
        *,
        origin: str,
        destination: str,
        departure: date,
    ) -> list[OneWayFare]:
        response = await self._client.get(
            self.endpoint,
            headers={"X-Access-Token": self._token, "Accept-Encoding": "gzip, deflate"},
            params={
                "origin": origin,
                "destination": destination,
                "departure_at": departure.isoformat(),
                "one_way": "true",
                "direct": "false",
                "currency": "rub",
                "market": "ru",
                "sorting": "price",
                "limit": 100,
                "page": 1,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("success"):
            raise TravelpayoutsError(str(payload.get("error") or "unsuccessful response"))
        fares: list[OneWayFare] = []
        for item in payload.get("data", []):
            fare = self._normalize_one_way(item)
            if fare is not None:
                fares.append(fare)
        return fares

    def _normalize(self, item: dict[str, object]) -> Offer | None:
        departure_at = _parse_datetime(item.get("departure_at"))
        return_at = _parse_datetime(item.get("return_at"))
        if departure_at is None or return_at is None:
            return None

        duration_total = _positive_int(item.get("duration"), fallback=0)
        duration_to = _positive_int(item.get("duration_to"), fallback=duration_total // 2)
        duration_back = _positive_int(
            item.get("duration_back"),
            fallback=max(duration_total - duration_to, 0),
        )
        price = _positive_int(item.get("price"), fallback=0)
        if price == 0:
            return None

        origin = str(item.get("origin") or "")
        destination = str(item.get("destination") or "")
        airline = str(item.get("airline") or "")
        flight_number = str(item.get("flight_number") or "")
        raw_link = str(item.get("link") or "")
        identity_material = "|".join(
            [
                origin,
                destination,
                departure_at.isoformat(),
                return_at.isoformat(),
                airline,
                flight_number,
            ]
        )
        identity = hashlib.sha256(identity_material.encode()).hexdigest()[:24]
        observed_at = _parse_datetime(item.get("found_at")) or datetime.now(UTC)

        return Offer(
            identity=identity,
            outbound=FlightLeg(
                origin=origin,
                destination=destination,
                departure_at=departure_at,
                arrival_at=departure_at + timedelta(minutes=duration_to),
                stops=_non_negative_int(item.get("transfers")),
                duration_minutes=duration_to,
                airline_codes=(airline,) if airline else (),
                flight_numbers=(flight_number,) if flight_number else (),
            ),
            inbound=FlightLeg(
                origin=destination,
                destination=origin,
                departure_at=return_at,
                arrival_at=return_at + timedelta(minutes=duration_back),
                stops=_non_negative_int(item.get("return_transfers")),
                duration_minutes=duration_back,
            ),
            price_per_person_rub=price,
            adults_quoted=1,
            baggage=BaggageStatus.UNKNOWN,
            group_availability=GroupAvailability.UNKNOWN,
            booking_shape=BookingShape.ROUND_TRIP,
            source="travelpayouts_cache",
            result_url=urljoin("https://www.aviasales.ru", raw_link),
            observed_at=observed_at,
        )

    def _normalize_one_way(self, item: dict[str, object]) -> OneWayFare | None:
        departure_at = _parse_datetime(item.get("departure_at"))
        price = _positive_int(item.get("price"), fallback=0)
        if departure_at is None or price == 0:
            return None

        origin = str(item.get("origin") or "")
        destination = str(item.get("destination") or "")
        duration = _positive_int(item.get("duration"), fallback=0)
        airline = str(item.get("airline") or "")
        flight_number = str(item.get("flight_number") or "")
        raw_link = str(item.get("link") or "")
        identity_material = "|".join(
            [origin, destination, departure_at.isoformat(), airline, flight_number]
        )
        identity = hashlib.sha256(identity_material.encode()).hexdigest()[:24]
        return OneWayFare(
            identity=identity,
            leg=FlightLeg(
                origin=origin,
                destination=destination,
                departure_at=departure_at,
                arrival_at=departure_at + timedelta(minutes=duration),
                stops=_non_negative_int(item.get("transfers")),
                duration_minutes=duration,
                airline_codes=(airline,) if airline else (),
                flight_numbers=(flight_number,) if flight_number else (),
            ),
            price_per_person_rub=price,
            baggage=BaggageStatus.UNKNOWN,
            source="travelpayouts_cache_one_way",
            result_url=urljoin("https://www.aviasales.ru", raw_link),
            observed_at=_parse_datetime(item.get("found_at")) or datetime.now(UTC),
        )


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _non_negative_int(value: object) -> int:
    try:
        return max(int(value), 0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _positive_int(value: object, *, fallback: int) -> int:
    parsed = _non_negative_int(value)
    return parsed if parsed > 0 else fallback

