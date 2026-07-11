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

import re
import time

from .base import Offer, derive_unit_price, retry_get

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

LIDL_LEAFLET_LIST = "https://www.lidl.pl/c/nasze-gazetki/s10008614"
LIDL_FLYER_API = "https://endpoints.leaflets.schwarz/v4/flyer"

_LIDL_SLUG_RE = re.compile(r"/l/pl/gazetki/([^/\"?]+)/ar")


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


def fetch_lidl_promos(max_flyers: int = 4) -> list[dict]:
    """Calibrated 2026-07-11. Lidl leaflets run on the Schwarz group leaflet
    platform; each flyer has a public JSON feed (plain httpx works):

        GET https://endpoints.leaflets.schwarz/v4/flyer
            ?flyer_identifier=<slug>&region_id=0

    Flyer slugs come from the overview page (LIDL_LEAFLET_LIST), links of
    the form /l/pl/gazetki/<slug>/ar/0.

    HONESTY CAVEAT: flyer["products"] only contains STRUCTURED entries for
    products sold on lidl.pl (the non-food online shop — clothing, tools).
    Grocery promos are flat page images with alt-text keywords, no
    per-item name+price. So this returns real data, but grocery matches
    will be rare until Lidl exposes food promos structurally (the Lidl Plus
    app API has them, but it needs an authenticated account token).
    """
    try:
        r = retry_get(LIDL_LEAFLET_LIST, headers=HEADERS, timeout=30)
        slugs = list(dict.fromkeys(_LIDL_SLUG_RE.findall(r.text)))[:max_flyers]
    except Exception as e:
        print(f"[lidl] leaflet list fetch failed -> {e}")
        return []

    promos: list[dict] = []
    seen: set[str] = set()
    for slug in slugs:
        time.sleep(1.0)  # stay under ~1 req/s
        try:
            r = retry_get(LIDL_FLYER_API,
                          params={"flyer_identifier": slug, "region_id": 0},
                          headers={**HEADERS, "Accept": "application/json"},
                          timeout=30)
            products = r.json().get("flyer", {}).get("products") or {}
        except Exception as e:
            print(f"[lidl] flyer {slug} fetch failed -> {e}")
            continue
        # dict keyed by uuid when populated, [] when empty
        values = products.values() if isinstance(products, dict) else products
        for p in values:
            name = p.get("title", "")
            try:
                price = float(str(p.get("price")).replace(",", "."))
            except (TypeError, ValueError):
                continue
            if name and name.lower() not in seen:
                seen.add(name.lower())
                promos.append({"name": name, "price": price})
    return promos


def fetch_biedronka_promos() -> list[dict]:
    """Calibrated 2026-07-11: NO parseable feed exists.

    What was checked:
    - biedronka.pl/pl/gazetki is a JS shell; rendered in headless Chromium
      it shows leaflet tiles that are pure page images (JPG viewer), with
      no product JSON behind them.
    - The only site XHRs are api/index/userdata and api/shop/shippingcenter
      (store locations) — no promo data.
    - Structured promo prices exist only inside the Moja Biedronka mobile
      app API, which requires an authenticated account token.

    Returning [] on purpose — no data beats fake data. Revisit if Biedronka
    ever ships a web version of the app's offer browser.
    """
    return []
