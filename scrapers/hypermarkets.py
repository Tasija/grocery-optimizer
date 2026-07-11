"""Auchan (zakupy.auchan.pl) + Carrefour (carrefour.pl) — Playwright based.

Both sites render search results client-side and rotate anti-bot defenses,
so the robust play (which you know better than anyone) is:
  1. Open the search URL in Playwright,
  2. Intercept the XHR/fetch response that carries the product JSON,
  3. Parse JSON instead of scraping DOM (survives CSS refactors).

Selectors/endpoints below are STARTING POINTS — run once with headless=False,
watch the Network tab, and pin the real response URL patterns. That's a
15-minute calibration job, then it's stable.
"""
from __future__ import annotations

import json
import re

from playwright.sync_api import sync_playwright

from .base import Offer, derive_unit_price

STORES = {
    "Auchan": {
        "search_url": "https://zakupy.auchan.pl/shop/search?text={q}",
        # substring of the XHR that returns product listings:
        "xhr_marker": "/api/v2/products",
    },
    "Carrefour": {
        "search_url": "https://www.carrefour.pl/szukaj?q={q}",
        "xhr_marker": "search",  # refine after one calibration run
    },
}

_PRICE_RE = re.compile(r"(\d+[.,]\d{2})")


def search(store: str, item_key: str, query: str, target_unit: str,
           limit: int = 5, headless: bool = True) -> list[Offer]:
    cfg = STORES[store]
    captured: list[dict] = []
    offers: list[Offer] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless)
        ctx = browser.new_context(locale="pl-PL")
        page = ctx.new_page()

        def on_response(resp):
            if cfg["xhr_marker"] in resp.url and "json" in (resp.headers.get("content-type") or ""):
                try:
                    captured.append(resp.json())
                except Exception:
                    pass

        page.on("response", on_response)
        try:
            page.goto(cfg["search_url"].format(q=query), wait_until="networkidle", timeout=45000)
        except Exception as e:
            print(f"[{store}] {item_key}: navigation issue -> {e}")

        # Fallback: scrape product tiles from DOM if no JSON captured
        if not captured:
            tiles = page.locator("[data-testid*=product], article, li.product-item")
            count = min(tiles.count(), limit)
            for i in range(count):
                text = tiles.nth(i).inner_text()
                m = _PRICE_RE.search(text.replace("\xa0", " "))
                if not m:
                    continue
                price = float(m.group(1).replace(",", "."))
                name = text.split("\n")[0][:120]
                offers.append(Offer(
                    store=store, item_key=item_key, product_name=name,
                    price=price, unit=target_unit,
                    unit_price=derive_unit_price(price, name, target_unit),
                    notes="DOM fallback — pin the XHR endpoint for reliability",
                ))
        browser.close()

    # Parse captured JSON payloads (structure differs per store — adapt
    # after your calibration run; this handles common shapes)
    for payload in captured:
        products = (
            payload.get("products")
            or payload.get("results")
            or payload.get("data", {}).get("products")
            or []
        )
        for p in products[:limit]:
            name = p.get("name") or p.get("title") or ""
            price = (
                p.get("price", {}).get("value")
                if isinstance(p.get("price"), dict) else p.get("price")
            )
            if price is None:
                continue
            price = float(price)
            offers.append(Offer(
                store=store, item_key=item_key, product_name=name,
                price=price, unit=target_unit,
                unit_price=derive_unit_price(price, name, target_unit),
                is_promo=bool(p.get("promo") or p.get("discount")),
            ))
    return offers
