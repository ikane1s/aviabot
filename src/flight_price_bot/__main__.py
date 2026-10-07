import asyncio

from flight_price_bot.app import run_bot


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()

