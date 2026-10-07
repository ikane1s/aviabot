"""Open a persistent Chrome profile for a user-completed access challenge."""

import asyncio
import re
import sys
from datetime import date
from pathlib import Path

from playwright.async_api import async_playwright

from flight_price_bot.providers.aviasales import CHALLENGE_MARKERS, build_search_url

PRICE_PATTERN = re.compile(r"(?:\d{1,3}(?:[\s\u00a0]\d{3})+|\d{4,6})\s*₽")


async def bootstrap() -> None:
    url = build_search_url(
        origin="OVB",
        destination="EVN",
        departure=date(2026, 12, 16),
        return_date=date(2026, 12, 21),
        adults=1,
    )
    profile = Path("data/browser-profile")
    profile.mkdir(parents=True, exist_ok=True)
    screenshot = Path("artifacts/profile-bootstrap-result.png")
    screenshot.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            str(profile),
            channel="chrome",
            headless=False,
            locale="ru-RU",
            timezone_id="Asia/Novosibirsk",
            viewport={"width": 1440, "height": 1000},
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        print("Chrome opened. Complete the challenge manually if it is shown.", flush=True)

        ready = False
        for attempt in range(300):
            frame_surface = " ".join(frame.url.lower() for frame in page.frames)
            challenge = any(marker in frame_surface for marker in CHALLENGE_MARKERS)
            body_text = await page.locator("body").inner_text(timeout=10_000)
            prices = PRICE_PATTERN.findall(body_text)
            if attempt % 5 == 0:
                await page.screenshot(path=str(screenshot), full_page=True)
                print(
                    {
                        "elapsed_seconds": attempt * 2,
                        "challenge": challenge,
                        "price_count": len(prices),
                        "body_length": len(body_text),
                    },
                    flush=True,
                )
            if prices:
                ready = True
                break
            await page.wait_for_timeout(2_000)

        body_text = await page.locator("body").inner_text(timeout=10_000)
        prices = sorted(set(PRICE_PATTERN.findall(body_text)))[:20]
        await page.screenshot(path=str(screenshot), full_page=True)
        print(
            {
                "ready": ready,
                "final_url": page.url,
                "prices": prices,
                "screenshot": str(screenshot.resolve()),
            },
            flush=True,
        )
        await context.close()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(bootstrap())
