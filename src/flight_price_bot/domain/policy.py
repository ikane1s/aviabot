import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from flight_price_bot.domain.models import (
    BaggageStatus,
    BookingShape,
    GroupAvailability,
    Offer,
    OneWayFare,
    PriceLevel,
)


@dataclass(frozen=True, slots=True)
class PriceThresholds:
    excellent: int = 25_000
    good: int = 30_000
    maximum: int = 35_000

    def __post_init__(self) -> None:
        if not 0 < self.excellent <= self.good <= self.maximum:
            raise ValueError("price thresholds must be positive and ordered")


@dataclass(frozen=True, slots=True)
class BestOffers:
    overall: Offer | None
    direct: Offer | None
    one_stop: Offer | None
    with_baggage: Offer | None
    confirmed_for_four: Offer | None


DEFAULT_PRICE_THRESHOLDS = PriceThresholds()


def classify_price(
    price_rub: int,
    thresholds: PriceThresholds = DEFAULT_PRICE_THRESHOLDS,
) -> PriceLevel:
    if price_rub <= thresholds.excellent:
        return PriceLevel.EXCELLENT
    if price_rub <= thresholds.good:
        return PriceLevel.GOOD
    if price_rub <= thresholds.maximum:
        return PriceLevel.ACCEPTABLE
    return PriceLevel.OVER_BUDGET


def should_send_ordinary_alert(
    offer: Offer,
    thresholds: PriceThresholds = DEFAULT_PRICE_THRESHOLDS,
) -> bool:
    return classify_price(offer.price_per_person_rub, thresholds) is not PriceLevel.OVER_BUDGET


def is_valid_trip_window(
    departure: date,
    return_date: date,
    concert: date = date(2026, 12, 19),
    min_nights: int = 3,
    max_nights: int = 7,
) -> bool:
    nights = (return_date - departure).days
    return departure <= concert < return_date and min_nights <= nights <= max_nights


def select_best_offers(offers: Iterable[Offer]) -> BestOffers:
    observed = list(offers)

    def cheapest(items: Iterable[Offer]) -> Offer | None:
        return min(items, key=lambda item: item.price_per_person_rub, default=None)

    return BestOffers(
        overall=cheapest(observed),
        direct=cheapest(offer for offer in observed if offer.is_direct),
        one_stop=cheapest(
            offer
            for offer in observed
            if max(offer.outbound.stops, offer.inbound.stops) == 1
        ),
        with_baggage=cheapest(
            offer for offer in observed if offer.baggage is BaggageStatus.INCLUDED
        ),
        confirmed_for_four=cheapest(
            offer
            for offer in observed
            if offer.group_availability is GroupAvailability.CONFIRMED_FOR_FOUR
        ),
    )


def combine_one_way_fares(outbound: OneWayFare, inbound: OneWayFare) -> Offer:
    if outbound.leg.destination != inbound.leg.origin:
        raise ValueError("inbound flight must start at the outbound destination")
    if inbound.leg.destination != outbound.leg.origin:
        raise ValueError("inbound flight must return to the outbound origin")
    if inbound.leg.departure_at <= outbound.leg.departure_at:
        raise ValueError("inbound departure must follow outbound departure")

    baggage = (
        BaggageStatus.INCLUDED
        if outbound.baggage is BaggageStatus.INCLUDED
        and inbound.baggage is BaggageStatus.INCLUDED
        else BaggageStatus.NOT_INCLUDED
        if BaggageStatus.NOT_INCLUDED in (outbound.baggage, inbound.baggage)
        else BaggageStatus.UNKNOWN
    )
    identity_material = f"{outbound.identity}|{inbound.identity}"
    identity = hashlib.sha256(identity_material.encode()).hexdigest()[:24]
    return Offer(
        identity=identity,
        outbound=outbound.leg,
        inbound=inbound.leg,
        price_per_person_rub=(
            outbound.price_per_person_rub + inbound.price_per_person_rub
        ),
        adults_quoted=1,
        baggage=baggage,
        group_availability=GroupAvailability.UNKNOWN,
        booking_shape=BookingShape.SEPARATE_ONE_WAYS,
        source=f"{outbound.source}+{inbound.source}",
        result_url=outbound.result_url,
        observed_at=max(outbound.observed_at, inbound.observed_at),
    )

