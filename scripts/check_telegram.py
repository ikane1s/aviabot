import asyncio

from aiogram import Bot

from flight_price_bot.config import Settings


async def check() -> None:
    settings = Settings()  # type: ignore[call-arg]
    bot = Bot(settings.telegram_bot_token.get_secret_value())
    try:
        me = await bot.get_me()
        print(
            {
                "id": me.id,
                "username": me.username,
                "can_join_groups": me.can_join_groups,
            }
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(check())
