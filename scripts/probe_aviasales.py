"""Controlled diagnostic for one Aviasales search page.

This script does not bypass access challenges. It records a screenshot and a
small text summary so selectors can be designed from observed page behavior.
"""

import argparse
import asyncio
import json
import re
import sys
from contextlib import suppress
from pathlib import Path

from playwright.async_api import BrowserContext, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

PRICE_PATTERN = re.compile(r"(?:\d{1,3}(?:[\s\u00a0]\d{3})+|\d{4,6})\s*[₽Р]")
CHALLENGE_MARKERS = (
    "smartcaptcha.cloud.yandex.ru/advanced",
)


async def probe(
    url: str,
    output_dir: Path,
    *,
    headless: bool,
    channel: str | None,
    profile_dir: Path | None,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = output_dir / "aviasales-probe.png"

    async with async_playwright() as playwright:
        context_options = {
            "locale": "ru-RU",
            "timezone_id": "Asia/Novosibirsk",
            "viewport": {"width": 1440, "height": 1000},
        }
        browser = None
        context: BrowserContext
        if profile_dir:
            profile_dir.mkdir(parents=True, exist_ok=True)
            context = await playwright.chromium.launch_persistent_context(
                str(profile_dir),
                channel=channel,
                headless=headless,
                **context_options,
            )
        else:
            browser = await playwright.chromium.launch(channel=channel, headless=headless)
            context = await browser.new_context(**context_options)
        page = await context.new_page()
        response_status: int | None = None
        navigation_error: str | None = None

        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            response_status = response.status if response else None
            with suppress(PlaywrightTimeoutError):
                await page.wait_for_load_state("networkidle", timeout=30_000)
            await page.wait_for_timeout(15_000)
        except PlaywrightTimeoutError as error:
            navigation_error = type(error).__name__

        body_text = await page.locator("body").inner_text(timeout=10_000)
        normalized_text = " ".join(body_text.split())
        lower_text = normalized_text.lower()
        frame_urls = [frame.url for frame in page.frames]
        challenge_surface = " ".join([lower_text, *frame_urls]).lower()
        prices = sorted(set(PRICE_PATTERN.findall(body_text)))[:30]
        challenge_detected = (
            any(marker in challenge_surface for marker in CHALLENGE_MARKERS) and not prices
        )
        await page.screenshot(path=str(screenshot_path), full_page=True)

        result = {
            "requested_url": url,
            "final_url": page.url,
            "title": await page.title(),
            "response_status": response_status,
            "navigation_error": navigation_error,
            "challenge_detected": challenge_detected,
            "frame_urls": frame_urls,
            "visible_prices": prices,
            "text_sample": normalized_text[:3_000],
            "screenshot": str(screenshot_path.resolve()),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        await context.close()
        if browser:
            await browser.close()

    return 2 if challenge_detected else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts"))
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--channel", choices=("chrome", "msedge"))
    parser.add_argument("--profile-dir", type=Path)
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    raise SystemExit(
        asyncio.run(
            probe(
                args.url,
                args.output_dir,
                headless=not args.headed,
                channel=args.channel,
                profile_dir=args.profile_dir,
            )
        )
    )


if __name__ == "__main__":
    main()

