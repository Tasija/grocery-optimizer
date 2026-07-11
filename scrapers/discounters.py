"""Lidl & Biedronka — promo-only sources (no grocery e-commerce in PL).

Strategy: pull current promotions and keyword-match against your list.
An item found here is flagged is_promo=True and usually beats everyone —
but absence of a match means "no data", NOT "not available in store".

Sources worth calibrating (in order of stability):
  Lidl:      https://www.lidl.pl/c/gazetka (promo grid has JSON endpoints;
             the Lidl Plus mobile API also exists but needs auth tokens)
  Biedronka: https://www.biedronka.pl/pl/gazetki + weekly promo pages
  Fallback:  Blix / Moja Gazetka aggregate both (scrape respectfully)
"""
from __future__ import annotations

import httpx

from .base import Offer, derive_unit_price

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}


def _match(name: str, keywords: list[str]) -> bool:
    low = name.lower()
    return any(k.lower() in low for k in keywords)


def search_lidl(promo_index: list[dict], item_key: str, keywords: list[str],
                target_unit: str) -> list[Offer]:
    """promo_index: list of {name, price} dicts from your calibrated
    Lidl promo fetch (see fetch_lidl_promos below)."""
    out = []
    for p in promo_index:
        if _match(p["name"], keywords):
            out.append(Offer(
                store="Lidl", item_key=item_key, product_name=p["name"],
                price=p["price"], unit=target_unit,
                unit_price=derive_unit_price(p["price"], p["name"], target_unit),
                is_promo=True, notes="leaflet promo",
            ))
    return out


def search_biedronka(promo_index: list[dict], item_key: str, keywords: list[str],
                     target_unit: str) -> list[Offer]:
    out = []
    for p in promo_index:
        if _match(p["name"], keywords):
            out.append(Offer(
                store="Biedronka", item_key=item_key, product_name=p["name"],
                price=p["price"], unit=target_unit,
                unit_price=derive_unit_price(p["price"], p["name"], target_unit),
                is_promo=True, notes="leaflet promo",
            ))
    return out


def fetch_lidl_promos() -> list[dict]:
    """TODO (calibration): open lidl.pl/c/gazetka with DevTools, find the
    JSON feed behind the promo grid, and parse name+price here.
    Returning [] keeps the pipeline running without Lidl data."""
    try:
        # placeholder request to verify connectivity; replace with real feed
        httpx.get("https://www.lidl.pl", headers=HEADERS, timeout=15)
    except Exception as e:
        print(f"[lidl] promo fetch failed -> {e}")
    return []


def fetch_biedronka_promos() -> list[dict]:
    """TODO (calibration): same drill for biedronka.pl promo pages."""
    return []
