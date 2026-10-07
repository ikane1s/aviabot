import asyncio
import json
import logging
from contextlib import suppress
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import BotCommand, Message

from flight_price_bot.config import Settings
from flight_price_bot.cycle import SearchCycle
from flight_price_bot.domain.models import GroupAvailability, Offer
from flight_price_bot.domain.policy import PriceThresholds
from flight_price_bot.formatting import (
    format_cycle_result,
    format_daily_summary,
    format_offer_alert,
)
from flight_price_bot.notifications import offer_notification_key
from flight_price_bot.storage.sqlite import SQLiteStore

logger = logging.getLogger(__name__)


def build_router(settings: Settings, store: SQLiteStore, cycle: SearchCycle) -> Router:
    router = Router(name="control")

    def allowed(message: Message) -> bool:
        return message.chat.id == settings.telegram_target_chat_id

    @router.message(Command("setup"))
    async def setup_command(message: Message) -> None:
        if settings.telegram_target_chat_id != 0:
            if allowed(message):
                await message.answer("Этот чат уже привязан к боту.")
            return
        if message.chat.type == "private":
            await message.answer(
                "Добавьте меня в нужную группу и отправьте там команду /setup."
            )
            return
        await store.set_state("setup_candidate_chat_id", str(message.chat.id))
        await store.set_state("setup_candidate_chat_title", message.chat.title or "")
        await message.answer(
            "Группа найдена. Передайте владельцу проекта этот ID: "
            f"<code>{message.chat.id}</code>",
            parse_mode="HTML",
        )

    @router.message(Command("start", "help"))
    async def help_command(message: Message) -> None:
        if not allowed(message):
            return
        await message.answer(
            "Бот отслеживает OVB ↔ EVN для четырёх взрослых. "
            "Команды: /status, /best, /check."
        )

    @router.message(Command("status"))
    async def status_command(message: Message) -> None:
        if not allowed(message):
            return
        cached = await store.latest_run("travelpayouts")
        live = await store.latest_run("aviasales_browser")
        observations = await store.count_offer_observations()
        await message.answer(
            "Мониторинг запущен.\n"
            f"Наблюдений в базе: {observations}.\n"
            f"Travelpayouts: {_run_status(cached)}.\n"
            f"Aviasales: {_run_status(live)}."
        )

    @router.message(Command("best"))
    async def best_command(message: Message) -> None:
        if not allowed(message):
            return
        rows = await store.cheapest_observations()
        if not rows:
            await message.answer("В базе пока нет предложений.")
            return
        lines = ["Лучшие наблюдения:"]
        for row in rows:
            payload = json.loads(str(row["payload_json"]))
            departure = payload["outbound"]["departure_at"][:10]
            return_date = payload["inbound"]["departure_at"][:10]
            lines.append(
                f"• {int(row['price_per_person_rub']):,} ₽ · "
                f"{departure} → {return_date} · {row['source']}"
            )
        await message.answer("\n".join(lines).replace(",", " "))

    @router.message(Command("check"))
    async def check_command(message: Message) -> None:
        if not allowed(message):
            return
        if cycle.running:
            await message.answer("Проверка уже выполняется.")
            return
        await message.answer("Начинаю проверку. Это может занять около минуты.")
        result = await cycle.run()
        await message.answer(format_cycle_result(result))
        await _send_offer_alerts(
            bot=message.bot,
            settings=settings,
            store=store,
            offers=result.alert_offers,
        )

    return router


def _run_status(run: dict[str, str | None] | None) -> str:
    if run is None:
        return "ещё не проверялся"
    finished = run.get("finished_at") or run.get("started_at") or "время неизвестно"
    return f"{run.get('status', 'unknown')}, {finished}"


async def _scheduled_checks(
    cycle: SearchCycle,
    interval_minutes: int,
    *,
    bot: Bot,
    settings: Settings,
    store: SQLiteStore,
) -> None:
    while True:
        try:
            result = await cycle.run()
            await _send_offer_alerts(
                bot=bot,
                settings=settings,
                store=store,
                offers=result.alert_offers,
            )
        except Exception:
            logger.exception("Scheduled search cycle failed")
        await _send_daily_summary_if_due(bot=bot, settings=settings, store=store)
        await asyncio.sleep(interval_minutes * 60)


async def _send_offer_alerts(
    *, bot: Bot, settings: Settings, store: SQLiteStore, offers: tuple[Offer, ...]
) -> None:
    thresholds = PriceThresholds(
        excellent=settings.excellent_price_rub,
        good=settings.good_price_rub,
        maximum=settings.maximum_price_rub,
    )
    preferred: dict[str, Offer] = {}
    for offer in offers:
        current = preferred.get(offer.identity)
        if current is None or (
            offer.group_availability is GroupAvailability.CONFIRMED_FOR_FOUR
            and current.group_availability is not GroupAvailability.CONFIRMED_FOR_FOUR
        ):
            preferred[offer.identity] = offer

    for offer in sorted(preferred.values(), key=lambda item: item.price_per_person_rub):
        key = offer_notification_key(offer, thresholds)
        reserved = await store.reserve_notification(
            key=key,
            notification_type="price_alert",
            payload={
                "identity": offer.identity,
                "price_per_person_rub": offer.price_per_person_rub,
            },
        )
        if not reserved:
            continue
        message = await bot.send_message(
            settings.telegram_target_chat_id,
            format_offer_alert(
                offer,
                thresholds=thresholds,
                timezone=settings.app_timezone,
                spectacular_price_rub=settings.spectacular_price_rub,
            ),
        )
        await store.mark_notification_delivered(key, message.message_id)


async def _send_daily_summary_if_due(
    *,
    bot: Bot,
    settings: Settings,
    store: SQLiteStore,
) -> None:
    local_now = datetime.now(ZoneInfo(settings.app_timezone))
    local_date = local_now.date().isoformat()
    if local_now.hour < settings.daily_summary_hour:
        return
    if await store.daily_snapshot_exists(local_date):
        return
    rows = await store.cheapest_observations(limit=1_000)
    previous = await store.previous_daily_minimum(local_date)
    live = await store.latest_run("aviasales_browser")
    live_status = str(live["status"]) if live else "ещё не запускалась"
    text, minimum = format_daily_summary(
        rows,
        previous_minimum=previous,
        live_status=live_status,
    )
    message = await bot.send_message(settings.telegram_target_chat_id, text)
    await store.save_daily_snapshot(
        local_date=local_date,
        minimum_price_rub=minimum,
        payload={"telegram_message_id": message.message_id, "live_status": live_status},
    )


async def run_bot() -> None:
    settings = Settings()  # type: ignore[call-arg]
    store = SQLiteStore(settings.database_path)
    await store.initialize()
    cycle = SearchCycle(settings, store)
    bot = Bot(token=settings.telegram_bot_token.get_secret_value())
    await bot.set_my_commands(
        [
            BotCommand(command="status", description="Состояние мониторинга"),
            BotCommand(command="best", description="Лучшие найденные варианты"),
            BotCommand(command="check", description="Запустить проверку"),
            BotCommand(command="setup", description="Показать ID группы при настройке"),
            BotCommand(command="help", description="Как работает бот"),
        ]
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(build_router(settings, store, cycle))
    schedule_task = None
    if settings.telegram_target_chat_id != 0:
        schedule_task = asyncio.create_task(
            _scheduled_checks(
                cycle,
                settings.check_interval_minutes,
                bot=bot,
                settings=settings,
                store=store,
            )
        )
    try:
        await dispatcher.start_polling(bot)
    finally:
        if schedule_task:
            schedule_task.cancel()
            with suppress(asyncio.CancelledError):
                await schedule_task
        await bot.session.close()

