from collections.abc import Sequence
from datetime import date
from typing import Protocol

from flight_price_bot.domain.models import Offer


class DiscoveryProvider(Protocol):
    async def discover(
        self,
        *,
        origin: str,
        destination: str,
        departure: date,
        return_date: date,
    ) -> Sequence[Offer]: ...


class LiveVerifier(Protocol):
    async def verify(
        self,
        *,
        origin: str,
        destination: str,
        departure: date,
        return_date: date,
        adults: int,
    ) -> Sequence[Offer]: ...

