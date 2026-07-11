"""Pure-logic tests for optimizer.py — no network."""
from scrapers.base import Offer
import optimizer


def offer(store, key, price, unit_price=None, name="x"):
    return Offer(store=store, item_key=key, product_name=name,
                 price=price, unit="kg", unit_price=unit_price)


class TestBestOfferPerItem:
    def test_picks_lowest_unit_price(self):
        offers = [
            offer("A", "butter", 5.99, unit_price=29.95),
            offer("B", "butter", 6.50, unit_price=26.00),  # dearer pack, cheaper /kg
        ]
        winners = optimizer.best_offer_per_item(offers)
        assert winners["butter"].store == "B"

    def test_unit_priced_offers_beat_pack_price_only(self):
        offers = [
            offer("A", "butter", 1.00, unit_price=None),  # cheap but incomparable
            offer("B", "butter", 6.00, unit_price=30.00),
        ]
        winners = optimizer.best_offer_per_item(offers)
        assert winners["butter"].store == "B"

    def test_falls_back_to_pack_price_when_no_unit_prices(self):
        offers = [
            offer("A", "butter", 7.00),
            offer("B", "butter", 6.00),
        ]
        winners = optimizer.best_offer_per_item(offers)
        assert winners["butter"].store == "B"

    def test_one_winner_per_item(self):
        offers = [
            offer("A", "butter", 6.00, unit_price=30.00),
            offer("B", "milk", 3.00, unit_price=3.00),
            offer("A", "milk", 3.50, unit_price=3.50),
        ]
        winners = optimizer.best_offer_per_item(offers)
        assert set(winners) == {"butter", "milk"}
        assert winners["milk"].store == "B"


class TestGroupByStore:
    def test_groups_winners(self):
        winners = {
            "butter": offer("A", "butter", 6.00),
            "milk": offer("B", "milk", 3.00),
            "eggs": offer("A", "eggs", 13.00),
        }
        grouped = optimizer.group_by_store(winners)
        assert {o.item_key for o in grouped["A"]} == {"butter", "eggs"}
        assert [o.item_key for o in grouped["B"]] == ["milk"]


class TestSingleStoreBaseline:
    def test_cheapest_full_coverage_store_wins(self):
        offers = [
            offer("A", "butter", 6.00), offer("A", "milk", 4.00),
            offer("B", "butter", 5.00), offer("B", "milk", 3.00),
            offer("C", "butter", 1.00),  # cheapest butter but no milk
        ]
        assert optimizer.single_store_baseline(offers) == ("B", 8.00)

    def test_none_when_no_store_covers_everything(self):
        offers = [offer("A", "butter", 6.00), offer("B", "milk", 3.00)]
        assert optimizer.single_store_baseline(offers) is None

    def test_sums_pack_price_of_best_unit_price_offer(self):
        offers = [
            # per-kg cheaper option costs more per pack: baseline must sum
            # the pack price of the unit-price winner (6.50), not 5.99
            offer("A", "butter", 5.99, unit_price=29.95),
            offer("A", "butter", 6.50, unit_price=26.00),
            offer("A", "milk", 3.00, unit_price=3.00),
        ]
        assert optimizer.single_store_baseline(offers) == ("A", 9.50)


class TestTotal:
    def test_sums_winner_pack_prices(self):
        winners = {
            "butter": offer("A", "butter", 6.00),
            "milk": offer("B", "milk", 3.45),
        }
        assert optimizer.total(winners) == 9.45
