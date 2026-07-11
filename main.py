"""Daily pipeline: scrape -> optimize -> notify."""
from __future__ import annotations

import yaml

import optimizer
import notifier
from scrapers import frisco, hypermarkets, discounters
from scrapers.base import Offer


def load_config(path: str = "config/shopping_list.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect_offers(cfg: dict) -> list[Offer]:
    offers: list[Offer] = []

    # Full-catalog stores
    for item in cfg["items"]:
        key, unit = item["key"], item["unit"]
        stores = item.get("stores", {})
        if "frisco" in stores:
            offers += frisco.search(key, stores["frisco"]["query"], unit)
        for store_name, cfg_key in (("Auchan", "auchan"), ("Carrefour", "carrefour")):
            if cfg_key in stores:
                offers += hypermarkets.search(
                    store_name, key, stores[cfg_key]["query"], unit
                )

    # Promo-only discounters
    lidl_promos = discounters.fetch_lidl_promos()
    biedronka_promos = discounters.fetch_biedronka_promos()
    for item in cfg["items"]:
        key, unit = item["key"], item["unit"]
        keywords = cfg.get("promo_keywords", {}).get(key, [])
        if not keywords:
            continue
        offers += discounters.search_lidl(lidl_promos, key, keywords, unit)
        offers += discounters.search_biedronka(biedronka_promos, key, keywords, unit)

    return offers


def main() -> None:
    cfg = load_config()
    offers = collect_offers(cfg)

    all_keys = [i["key"] for i in cfg["items"]]
    found_keys = {o.item_key for o in offers}
    missing = [
        i["display"] for i in cfg["items"] if i["key"] not in found_keys
    ]

    winners = optimizer.best_offer_per_item(offers)
    grouped = optimizer.group_by_store(winners)
    total = optimizer.total(winners)
    baseline = optimizer.single_store_baseline(offers)

    msg = notifier.format_message(grouped, total, baseline, missing)
    print(msg)  # visible in Actions logs
    notifier.send(msg)


if __name__ == "__main__":
    main()
