import json
from datetime import date

import httpx
import pytest

from flight_price_bot.providers.travelpayouts import TravelpayoutsProvider


@pytest.mark.asyncio
async def test_provider_normalizes_round_trip_and_uses_token_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Access-Token"] == "test-token"
        assert request.url.params["one_way"] == "false"
        assert request.url.params["origin"] == "OVB"
        return httpx.Response(
            200,
            content=json.dumps(
                {
                    "success": True,
                    "data": [
                        {
                            "origin": "OVB",
                            "destination": "EVN",
                            "price": 24_500,
                            "airline": "S7",
                            "flight_number": "123",
                            "departure_at": "2026-12-16T10:00:00+07:00",
                            "return_at": "2026-12-21T12:00:00+04:00",
                            "transfers": 0,
                            "return_transfers": 1,
                            "duration": 720,
                            "duration_to": 270,
                            "duration_back": 450,
                            "link": "/search/OVB1612EVN21121",
                            "found_at": "2026-10-07T10:00:00+07:00",
                        }
                    ],
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = TravelpayoutsProvider("test-token", client=client)
        offers = await provider.discover(
            origin="OVB",
            destination="EVN",
            departure=date(2026, 12, 16),
            return_date=date(2026, 12, 21),
        )

    assert len(offers) == 1
    offer = offers[0]
    assert offer.price_per_person_rub == 24_500
    assert offer.outbound.stops == 0
    assert offer.inbound.stops == 1
    assert offer.result_url == "https://www.aviasales.ru/search/OVB1612EVN21121"

