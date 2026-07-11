"""Frisco.pl — the friendliest source: JSON search API behind the site.

Calibrated 2026-07-11 against the live endpoint. Response shape:
  { "products": [ { "product": {
        "id": "125923",
        "name": {"pl": "...", "en": "..."},
        "price": {"price": 3.29,
                  # only present when discounted:
                  "priceBeforeDiscount": 27.89, "discountPercent": 18, ...},
        "grammage": 1.0,            # pack size in unitOfMeasure
        "unitOfMeasure": "Kilogram" | "Litre" | "Piece",
        "isAvailable": true, ...
  }}, ...]}

Promo detection: the top-level "promotions" list stays EMPTY even for
discounted items — the real signal is "priceBeforeDiscount" inside "price".
Unit price: grammage+unitOfMeasure is exact for kg/l; for "Piece" grammage
is 1.0 even on multipacks (e.g. eggs x10), so we fall back to parsing the
quantity out of the product name.
"""
from __future__ import annotations

from .base import Offer, derive_unit_price, retry_get

SEARCH_URL = "https://www.frisco.pl/app/commerce/api/v1/offer/products/query"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept": "application/json",
}

_UOM_TO_UNIT = {"Kilogram": "kg", "Litre": "l"}


def search(item_key: str, query: str, target_unit: str, limit: int = 5) -> list[Offer]:
    params = {
        "search": query,
        "pageIndex": 1,
        "pageSize": limit,
        "language": "pl",
        "disableAutocorrect": "false",
    }
    try:
        r = retry_get(SEARCH_URL, params=params, headers=HEADERS, timeout=20)
        data = r.json()
    except Exception as e:
        print(f"[frisco] {item_key}: request failed -> {e}")
        return []

    offers: list[Offer] = []
    for prod in data.get("products", []):
        p = prod.get("product", prod)
        if not p.get("isAvailable", True):
            continue
        name = p.get("name", {})
        if isinstance(name, dict):
            name = name.get("pl", "") or next(iter(name.values()), "")
        price_info = p.get("price", {})
        price = price_info.get("price")
        if price is None:
            continue
        price = float(price)

        unit_price = None
        grammage = p.get("grammage")
        if (_UOM_TO_UNIT.get(p.get("unitOfMeasure", "")) == target_unit
                and grammage and grammage > 0):
            unit_price = round(price / float(grammage), 2)
        if unit_price is None:
            unit_price = derive_unit_price(price, str(name), target_unit)

        offers.append(Offer(
            store="Frisco",
            item_key=item_key,
            product_name=str(name),
            price=price,
            unit=target_unit,
            unit_price=unit_price,
            is_promo="priceBeforeDiscount" in price_info,
            url=f"https://www.frisco.pl/pid,{p.get('id') or p.get('productId', '')}",
            meta={"grammage": grammage, "uom": p.get("unitOfMeasure")},
        ))
    return offers
