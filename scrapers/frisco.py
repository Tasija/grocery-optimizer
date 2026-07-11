"""Frisco.pl — the friendliest source: JSON search API behind the site.

NOTE: verify the endpoint in DevTools (Network tab -> search for a product
on frisco.pl and copy the request). The shape below matches their
historical public API; adjust field paths if they've shipped changes.
"""
from __future__ import annotations

import httpx

from .base import Offer, derive_unit_price

SEARCH_URL = "https://www.frisco.pl/app/commerce/api/v1/offer/products/query"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept": "application/json",
}


def search(item_key: str, query: str, target_unit: str, limit: int = 5) -> list[Offer]:
    params = {
        "search": query,
        "pageIndex": 1,
        "pageSize": limit,
        "language": "pl",
        "disableAutocorrect": "false",
    }
    try:
        r = httpx.get(SEARCH_URL, params=params, headers=HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[frisco] {item_key}: request failed -> {e}")
        return []

    offers: list[Offer] = []
    for prod in data.get("products", []):
        p = prod.get("product", prod)
        name = p.get("name", {})
        if isinstance(name, dict):
            name = name.get("pl", "") or next(iter(name.values()), "")
        price_info = p.get("price", {})
        price = price_info.get("price") or price_info.get("grossPrice")
        if price is None:
            continue
        price = float(price)

        # Frisco often ships unit price directly — prefer it when present
        unit_price = None
        gramm = p.get("grammage") or {}
        if isinstance(price_info.get("unitPrice"), (int, float)):
            unit_price = float(price_info["unitPrice"])
        if unit_price is None:
            unit_price = derive_unit_price(price, str(name), target_unit)

        offers.append(Offer(
            store="Frisco",
            item_key=item_key,
            product_name=str(name),
            price=price,
            unit=target_unit,
            unit_price=unit_price,
            is_promo=bool(p.get("promotion") or price_info.get("isPromoPrice")),
            url=f"https://www.frisco.pl/pid,{p.get('id') or p.get('productId', '')}",
            meta={"grammage": gramm},
        ))
    return offers
