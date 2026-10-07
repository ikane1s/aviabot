import asyncio
import logging

from flight_price_bot.app import run_bot


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
