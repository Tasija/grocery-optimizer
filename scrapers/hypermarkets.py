"""Auchan (zakupy.auchan.pl) + Carrefour (carrefour.pl).

Calibrated 2026-07-11. Reality differs from the original XHR-intercept plan:
BOTH sites server-side-render search results into the initial HTML document,
and their product XHRs only fire on client-side route changes (typing in the
search box), never on a direct URL load. Parsing the SSR state blob is
therefore both simpler and more stable than driving the search UI:

  Auchan:    GET https://zakupy.auchan.pl/search?q=...  (plain httpx works —
             the AWS WAF passes document GETs)
             -> window.__INITIAL_STATE__ JSON:
                ordered ids:  data.search.catalogue.data.productGroups[0].products
                entities:     data.products.productEntities[id]
                price:        price.current.amount (str), price.original.amount
                promo:        original != current
                unit price:   price.unit.current.amount + price.unit.label
                              ("fop.price.per.kg" / "fop.price.per.litre")

  Carrefour: https://www.carrefour.pl/szukaj?q=...  (403 to plain httpx ->
             Playwright headless Chromium with pl-PL locale + realistic UA
             passes; no consent interaction needed, data ships in the doc)
             -> <script id="__NEXT_DATA__"> JSON:
                products:     props.initialState.products.data.content
                price:        actualSku.amount.actualGrossPrice (float)
                promo:        actualSku.promotion (bool)
                unit price:   actualSku.grammageWithUnitString, e.g.
                              "4,25 zł/1 l" (parsed below)

If either site changes its SSR framework, re-run a capture of the search
page and re-pin the paths above.
"""
from __future__ import annotations

import json
import re
import urllib.parse

from playwright.sync_api import sync_playwright

from .base import Offer, derive_unit_price, retry_get

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")

HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "pl-PL,pl;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

AUCHAN_SEARCH = "https://zakupy.auchan.pl/search?q={q}"
CARREFOUR_SEARCH = "https://www.carrefour.pl/szukaj?q={q}"

_INITIAL_STATE_RE = re.compile(
    r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*(?:;|</script>)", re.S)
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)

_AUCHAN_UNIT = {"fop.price.per.kg": "kg", "fop.price.per.litre": "l",
                "fop.price.per.piece": "szt"}

# "4,25 zł/1 l", "29,90 zł/1 kg", "1,33 zł/1 szt."
_CARREFOUR_UNIT_RE = re.compile(
    r"(\d+(?:,\d+)?)\s*zł\s*/\s*(\d+(?:,\d+)?)?\s*(kg|g|l|ml|szt)", re.I)

_UNIT_MULT = {"kg": ("kg", 1.0), "g": ("kg", 0.001), "l": ("l", 1.0),
              "ml": ("l", 0.001), "szt": ("szt", 1.0)}


def search(store: str, item_key: str, query: str, target_unit: str,
           limit: int = 5, headless: bool = True) -> list[Offer]:
    if store == "Auchan":
        return _search_auchan(item_key, query, target_unit, limit)
    if store == "Carrefour":
        return _search_carrefour(item_key, query, target_unit, limit, headless)
    raise ValueError(f"unknown store: {store}")


# --- Auchan ------------------------------------------------------------------

def _search_auchan(item_key: str, query: str, target_unit: str,
                   limit: int) -> list[Offer]:
    url = AUCHAN_SEARCH.format(q=urllib.parse.quote(query))
    try:
        r = retry_get(url, headers=HEADERS, timeout=30)
        m = _INITIAL_STATE_RE.search(r.text)
        if not m:
            print(f"[Auchan] {item_key}: no __INITIAL_STATE__ in response "
                  "(WAF challenge or SSR change) — skipping")
            return []
        state = json.loads(m.group(1))
    except Exception as e:
        print(f"[Auchan] {item_key}: request failed -> {e}")
        return []

    groups = (state.get("data", {}).get("search", {}).get("catalogue", {})
              .get("data", {}).get("productGroups") or [])
    ids: list[str] = groups[0].get("products", []) if groups else []
    entities = state.get("data", {}).get("products", {}).get("productEntities", {})

    offers: list[Offer] = []
    for pid in ids[:limit]:
        p = entities.get(pid)
        if not p or not p.get("available", True):
            continue
        price_info = p.get("price", {})
        current = (price_info.get("current") or {}).get("amount")
        if current is None:
            continue
        price = float(current)
        original = (price_info.get("original") or {}).get("amount")
        is_promo = original is not None and float(original) != price

        unit_price = None
        unit_info = price_info.get("unit") or {}
        if _AUCHAN_UNIT.get(unit_info.get("label", "")) == target_unit:
            amt = (unit_info.get("current") or {}).get("amount")
            if amt is not None:
                unit_price = float(amt)
        name = p.get("name", "")
        if unit_price is None:
            unit_price = derive_unit_price(price, name, target_unit)

        offers.append(Offer(
            store="Auchan", item_key=item_key, product_name=name,
            price=price, unit=target_unit, unit_price=unit_price,
            is_promo=is_promo,
            meta={"retailerProductId": p.get("retailerProductId")},
        ))
    return offers


# --- Carrefour ----------------------------------------------------------------

def _carrefour_unit_price(sku: dict, price: float, name: str,
                          target_unit: str) -> float | None:
    m = _CARREFOUR_UNIT_RE.search(sku.get("grammageWithUnitString") or "")
    if m:
        amount = float(m.group(1).replace(",", "."))
        qty = float((m.group(2) or "1").replace(",", "."))
        base_unit, mult = _UNIT_MULT[m.group(3).lower()]
        if base_unit == target_unit and qty * mult > 0:
            return round(amount / (qty * mult), 2)
    return derive_unit_price(price, name, target_unit)


def _search_carrefour(item_key: str, query: str, target_unit: str,
                      limit: int, headless: bool) -> list[Offer]:
    url = CARREFOUR_SEARCH.format(q=urllib.parse.quote(query))
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            ctx = browser.new_context(
                locale="pl-PL", user_agent=UA,
                viewport={"width": 1366, "height": 900},
                extra_http_headers={"Accept-Language": "pl-PL,pl;q=0.9"},
            )
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            html = page.content()
            browser.close()
    except Exception as e:
        print(f"[Carrefour] {item_key}: navigation failed -> {e}")
        return []

    m = _NEXT_DATA_RE.search(html)
    if not m:
        print(f"[Carrefour] {item_key}: no __NEXT_DATA__ in page "
              "(blocked or SSR change) — skipping")
        return []
    try:
        data = json.loads(m.group(1))
        content = (data["props"]["initialState"]["products"]["data"]
                   .get("content") or [])
    except (KeyError, json.JSONDecodeError) as e:
        print(f"[Carrefour] {item_key}: payload shape changed -> {e}")
        return []

    offers: list[Offer] = []
    for p in content[:limit]:
        sku = p.get("actualSku") or {}
        if not p.get("active", True) or sku.get("status") not in (None, "ENABLED"):
            continue
        price = (sku.get("amount") or {}).get("actualGrossPrice")
        if price is None:
            continue
        price = float(price)
        name = p.get("displayName") or p.get("name", "")
        offers.append(Offer(
            store="Carrefour", item_key=item_key, product_name=name,
            price=price, unit=target_unit,
            unit_price=_carrefour_unit_price(sku, price, name, target_unit),
            is_promo=bool(sku.get("promotion")),
            url=f"https://www.carrefour.pl{p['url']}" if p.get("url") else "",
        ))
    return offers
