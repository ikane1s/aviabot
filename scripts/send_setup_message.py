import asyncio

from aiogram import Bot

from flight_price_bot.config import Settings


async def send() -> None:
    settings = Settings()  # type: ignore[call-arg]
    if settings.telegram_target_chat_id == 0:
        raise RuntimeError("Telegram target chat is not configured")
    bot = Bot(settings.telegram_bot_token.get_secret_value())
    try:
        message = await bot.send_message(
            settings.telegram_target_chat_id,
            "Бот привязан к группе и запущен. Первая проверка выполнена: "
            "Aviasales показал SmartCaptcha, поэтому живая проверка поставлена "
            "на безопасную паузу. Для проверки состояния используйте /status.",
        )
        print({"chat_id": message.chat.id, "message_id": message.message_id})
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(send())
