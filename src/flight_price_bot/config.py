from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: SecretStr
    telegram_target_chat_id: int
    travelpayouts_api_token: SecretStr | None = None

    app_timezone: str = "Asia/Novosibirsk"
    database_path: Path = Path("data/flight_price_bot.db")
    headless_browser: bool = False
    live_pairs_per_cycle: int = Field(default=3, ge=1, le=14)
    check_interval_minutes: int = Field(default=120, ge=60, le=360)
    daily_summary_hour: int = Field(default=10, ge=0, le=23)

    origin: str = "OVB"
    destination: str = "EVN"
    concert_date: date = date(2026, 12, 19)
    departure_start: date = date(2026, 12, 15)
    departure_end: date = date(2026, 12, 18)
    return_start: date = date(2026, 12, 20)
    return_end: date = date(2026, 12, 23)
    travelers: int = 4

    spectacular_price_rub: int = 20_000
    excellent_price_rub: int = 25_000
    good_price_rub: int = 30_000
    maximum_price_rub: int = 35_000
    preferred_max_leg_minutes: int = 12 * 60

    @field_validator("app_timezone")
    @classmethod
    def timezone_must_exist(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    @field_validator("origin", "destination")
    @classmethod
    def airport_code_must_be_iata(cls, value: str) -> str:
        normalized = value.upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("airport code must contain three Latin letters")
        return normalized

