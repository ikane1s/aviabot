import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from flight_price_bot.domain.models import Offer

SCHEMA = """
CREATE TABLE IF NOT EXISTS search_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS offer_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    identity TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    adults_quoted INTEGER NOT NULL,
    price_per_person_rub INTEGER NOT NULL,
    source TEXT NOT NULL,
    live_verified_at TEXT,
    payload_json TEXT NOT NULL,
    UNIQUE(identity, observed_at, adults_quoted, source)
);

CREATE INDEX IF NOT EXISTS idx_offer_observations_price
ON offer_observations(price_per_person_rub, observed_at);

CREATE TABLE IF NOT EXISTS notifications (
    deduplication_key TEXT PRIMARY KEY,
    notification_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    delivered_at TEXT,
    telegram_message_id INTEGER,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_snapshots (
    local_date TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    minimum_price_rub INTEGER,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.path) as connection:
            await connection.execute("PRAGMA journal_mode=WAL")
            await connection.executescript(SCHEMA)
            await connection.commit()

    async def save_offer(self, offer: Offer) -> bool:
        payload = json.dumps(asdict(offer), ensure_ascii=False, default=str)
        async with aiosqlite.connect(self.path) as connection:
            cursor = await connection.execute(
                """
                INSERT OR IGNORE INTO offer_observations (
                    identity,
                    observed_at,
                    adults_quoted,
                    price_per_person_rub,
                    source,
                    live_verified_at,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    offer.identity,
                    offer.observed_at.isoformat(),
                    offer.adults_quoted,
                    offer.price_per_person_rub,
                    offer.source,
                    offer.live_verified_at.isoformat() if offer.live_verified_at else None,
                    payload,
                ),
            )
            await connection.commit()
            return cursor.rowcount == 1

    async def record_search_run(
        self,
        *,
        source: str,
        status: str,
        started_at: datetime,
        detail: str | None = None,
    ) -> int:
        finished_at = datetime.now(UTC)
        async with aiosqlite.connect(self.path) as connection:
            cursor = await connection.execute(
                """
                INSERT INTO search_runs (started_at, finished_at, source, status, detail)
                VALUES (?, ?, ?, ?, ?)
                """,
                (started_at.isoformat(), finished_at.isoformat(), source, status, detail),
            )
            await connection.commit()
            if cursor.lastrowid is None:
                raise RuntimeError("SQLite did not return a search run id")
            return cursor.lastrowid

    async def count_offer_observations(self) -> int:
        async with aiosqlite.connect(self.path) as connection:
            cursor = await connection.execute("SELECT COUNT(*) FROM offer_observations")
            row = await cursor.fetchone()
            return int(row[0]) if row else 0

    async def set_state(self, key: str, value: str) -> None:
        now = datetime.now(UTC).isoformat()
        async with aiosqlite.connect(self.path) as connection:
            await connection.execute(
                """
                INSERT INTO app_state (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now),
            )
            await connection.commit()

    async def get_state(self, key: str) -> str | None:
        async with aiosqlite.connect(self.path) as connection:
            cursor = await connection.execute(
                "SELECT value FROM app_state WHERE key = ?",
                (key,),
            )
            row = await cursor.fetchone()
            return str(row[0]) if row else None

    async def delete_state(self, key: str) -> None:
        async with aiosqlite.connect(self.path) as connection:
            await connection.execute("DELETE FROM app_state WHERE key = ?", (key,))
            await connection.commit()

    async def latest_run(self, source: str) -> dict[str, str | None] | None:
        async with aiosqlite.connect(self.path) as connection:
            connection.row_factory = aiosqlite.Row
            cursor = await connection.execute(
                """
                SELECT started_at, finished_at, status, detail
                FROM search_runs
                WHERE source = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (source,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def cheapest_observations(self, limit: int = 5) -> list[dict[str, object]]:
        async with aiosqlite.connect(self.path) as connection:
            connection.row_factory = aiosqlite.Row
            cursor = await connection.execute(
                """
                SELECT identity, observed_at, price_per_person_rub, source, payload_json
                FROM offer_observations
                ORDER BY price_per_person_rub ASC, observed_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def reserve_notification(
        self,
        *,
        key: str,
        notification_type: str,
        payload: dict[str, object],
    ) -> bool:
        async with aiosqlite.connect(self.path) as connection:
            cursor = await connection.execute(
                """
                INSERT OR IGNORE INTO notifications (
                    deduplication_key,
                    notification_type,
                    created_at,
                    payload_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    key,
                    notification_type,
                    datetime.now(UTC).isoformat(),
                    json.dumps(payload, ensure_ascii=False, default=str),
                ),
            )
            await connection.commit()
            return cursor.rowcount == 1

    async def mark_notification_delivered(self, key: str, message_id: int) -> None:
        async with aiosqlite.connect(self.path) as connection:
            await connection.execute(
                """
                UPDATE notifications
                SET delivered_at = ?, telegram_message_id = ?
                WHERE deduplication_key = ?
                """,
                (datetime.now(UTC).isoformat(), message_id, key),
            )
            await connection.commit()

    async def save_daily_snapshot(
        self,
        *,
        local_date: str,
        minimum_price_rub: int | None,
        payload: dict[str, object],
    ) -> None:
        async with aiosqlite.connect(self.path) as connection:
            await connection.execute(
                """
                INSERT OR REPLACE INTO daily_snapshots (
                    local_date, created_at, minimum_price_rub, payload_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    local_date,
                    datetime.now(UTC).isoformat(),
                    minimum_price_rub,
                    json.dumps(payload, ensure_ascii=False, default=str),
                ),
            )
            await connection.commit()

    async def previous_daily_minimum(self, before_local_date: str) -> int | None:
        async with aiosqlite.connect(self.path) as connection:
            cursor = await connection.execute(
                """
                SELECT minimum_price_rub
                FROM daily_snapshots
                WHERE local_date < ? AND minimum_price_rub IS NOT NULL
                ORDER BY local_date DESC
                LIMIT 1
                """,
                (before_local_date,),
            )
            row = await cursor.fetchone()
            return int(row[0]) if row else None

    async def daily_snapshot_exists(self, local_date: str) -> bool:
        async with aiosqlite.connect(self.path) as connection:
            cursor = await connection.execute(
                "SELECT 1 FROM daily_snapshots WHERE local_date = ?",
                (local_date,),
            )
            return await cursor.fetchone() is not None


