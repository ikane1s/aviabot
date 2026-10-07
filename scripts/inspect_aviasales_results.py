"""Inspect visible Aviasales result markup without saving page secrets."""

import asyncio
import json
import sys
from argparse import ArgumentParser
from datetime import date

from playwright.async_api import async_playwright

from flight_price_bot.providers.aviasales import build_search_url


async def inspect(adults: int) -> None:
    url = build_search_url(
        origin="OVB",
        destination="EVN",
        departure=date(2026, 12, 16),
        return_date=date(2026, 12, 21),
        adults=adults,
    )
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            "data/browser-profile",
            channel="chrome",
            headless=False,
            locale="ru-RU",
            timezone_id="Asia/Novosibirsk",
            viewport={"width": 1440, "height": 1000},
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(30_000)
        elements = await page.locator("body").evaluate(
            """
            body => Array.from(body.querySelectorAll('*'))
              .filter(el => el.children.length === 0 && (el.innerText || '').includes('₽'))
              .slice(0, 100)
              .map(el => {
                const marked = el.closest('[data-test-id], [data-testid]');
                return {
                  tag: el.tagName,
                  className: String(el.className || '').slice(0, 300),
                  text: (el.innerText || '').trim().slice(0, 500),
                  testId: marked?.getAttribute('data-test-id') ||
                    marked?.getAttribute('data-testid'),
                  markedTag: marked?.tagName,
                  markedClass: String(marked?.className || '').slice(0, 300)
                };
              })
            """
        )
        result_cards = await page.locator(
            '[data-test-id*="ticket"], [data-testid*="ticket"], '
            '[data-test-id*="search-result"], [data-testid*="search-result"]'
        ).count()
        test_ids = await page.locator("body").evaluate(
            """
            body => [...new Set(
              Array.from(body.querySelectorAll('[data-test-id], [data-testid]'))
                .map(el => el.getAttribute('data-test-id') || el.getAttribute('data-testid'))
                .filter(Boolean)
            )].sort()
            """
        )
        ticket_cards = await page.locator(
            '[data-test-id^="bdui-ticket-preview-normal-"]'
        ).evaluate_all(
            """
            cards => cards.slice(0, 3).map(card => ({
              testId: card.getAttribute('data-test-id'),
              text: (card.innerText || '').trim().slice(0, 5000),
              hrefs: Array.from(card.querySelectorAll('a[href]'))
                .map(link => link.href).slice(0, 10),
              childTestIds: [...new Set(
                Array.from(card.querySelectorAll('[data-test-id], [data-testid]'))
                  .map(el => el.getAttribute('data-test-id') || el.getAttribute('data-testid'))
                  .filter(Boolean)
              )].sort(),
              images: Array.from(card.querySelectorAll('img'))
                .map(image => ({alt: image.alt, src: image.src})).slice(0, 10)
            }))
            """
        )
        print(
            json.dumps(
                {
                    "url": page.url,
                    "title": await page.title(),
                    "possible_result_cards": result_cards,
                    "frame_urls": [frame.url for frame in page.frames],
                    "test_ids": test_ids,
                    "ticket_cards": ticket_cards,
                    "price_elements": elements,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        await context.close()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--adults", type=int, default=1, choices=range(1, 10))
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(inspect(args.adults))
