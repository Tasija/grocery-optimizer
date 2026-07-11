"""Pick the cheapest offer per item (by unit price), group results by store,
and compute what the split-shopping saves vs. the best single store."""
from __future__ import annotations

from collections import defaultdict

from scrapers.base import Offer


def best_offer_per_item(offers: list[Offer]) -> dict[str, Offer]:
    """For each item, keep the offer with the lowest comparable price.
    Prefers unit_price; falls back to pack price when quantity unparseable."""
    by_item: dict[str, list[Offer]] = defaultdict(list)
    for o in offers:
        by_item[o.item_key].append(o)

    winners: dict[str, Offer] = {}
    for key, group in by_item.items():
        def sort_key(o: Offer):
            # unit-price comparisons first; pack-price-only offers rank after
            return (o.unit_price is None, o.unit_price if o.unit_price is not None else o.price)
        group.sort(key=sort_key)
        winners[key] = group[0]
    return winners


def group_by_store(winners: dict[str, Offer]) -> dict[str, list[Offer]]:
    grouped: dict[str, list[Offer]] = defaultdict(list)
    for o in winners.values():
        grouped[o.store].append(o)
    return dict(grouped)


def single_store_baseline(offers: list[Offer]) -> tuple[str, float] | None:
    """Cheapest single store that covers ALL items — the savings benchmark.
    Best offer per store+item is picked by unit price (same rule as
    best_offer_per_item); the store total sums the real pack prices."""
    # store -> item -> (comparable, pack_price)
    by_store_item: dict[str, dict[str, tuple[tuple[bool, float], float]]] = defaultdict(dict)
    all_items = {o.item_key for o in offers}
    for o in offers:
        comparable = (o.unit_price is None,
                      o.unit_price if o.unit_price is not None else o.price)
        cur = by_store_item[o.store].get(o.item_key)
        if cur is None or comparable < cur[0]:
            by_store_item[o.store][o.item_key] = (comparable, o.price)

    candidates = {
        store: sum(pack for _, pack in items.values())
        for store, items in by_store_item.items()
        if set(items) == all_items
    }
    if not candidates:
        return None
    store = min(candidates, key=candidates.get)
    return store, round(candidates[store], 2)


def total(winners: dict[str, Offer]) -> float:
    return round(sum(o.price for o in winners.values()), 2)
