import hashlib

from flight_price_bot.domain.models import Offer
from flight_price_bot.domain.policy import (
    DEFAULT_PRICE_THRESHOLDS,
    PriceThresholds,
    classify_price,
)


def offer_notification_key(
    offer: Offer,
    thresholds: PriceThresholds = DEFAULT_PRICE_THRESHOLDS,
) -> str:
    level = classify_price(offer.price_per_person_rub, thresholds).value
    verification = "live" if offer.live_verified_at else "cached"
    material = "|".join(
        [
            offer.identity,
            str(offer.price_per_person_rub // 500),
            level,
            offer.group_availability.value,
            verification,
        ]
    )
    return hashlib.sha256(material.encode()).hexdigest()

