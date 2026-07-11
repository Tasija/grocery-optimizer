"""Shared offer model + unit-price normalization."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Offer:
    store: str
    item_key: str
    product_name: str
    price: float                  # pack price, PLN
    unit: str = ""                # kg / l / szt
    unit_price: float | None = None  # PLN per unit (the ONLY fair comparator)
    is_promo: bool = False
    url: str = ""
    notes: str = ""
    meta: dict = field(default_factory=dict)


# --- unit price extraction -------------------------------------------------

_QTY_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(kg|g|l|ml|szt|sztuk)", re.IGNORECASE
)

_TO_BASE = {  # multiplier to convert to (kg / l / szt)
    "kg": ("kg", 1.0),
    "g": ("kg", 0.001),
    "l": ("l", 1.0),
    "ml": ("l", 0.001),
    "szt": ("szt", 1.0),
    "sztuk": ("szt", 1.0),
}


def derive_unit_price(price: float, product_name: str, target_unit: str) -> float | None:
    """Parse '200g', '1,5l', '10 szt' etc. from a product name and
    return PLN per target_unit. Returns None if quantity can't be parsed —
    the optimizer then falls back to pack price with a warning."""
    m = _QTY_RE.search(product_name)
    if not m:
        return None
    qty = float(m.group(1).replace(",", "."))
    base_unit, mult = _TO_BASE[m.group(2).lower()]
    if base_unit != target_unit:
        return None
    qty_in_base = qty * mult
    if qty_in_base <= 0:
        return None
    return round(price / qty_in_base, 2)
