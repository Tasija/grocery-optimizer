"""Pure-logic tests for scrapers/base.py:derive_unit_price — no network."""
import pytest

from scrapers.base import derive_unit_price


class TestDeriveUnitPrice:
    @pytest.mark.parametrize("price,name,unit,expected", [
        (5.99, "Masło extra 200g", "kg", 29.95),
        (5.99, "Masło extra 0,2 kg", "kg", 29.95),
        (13.89, "Filet z piersi z kurczaka 1 kg", "kg", 13.89),
        (3.29, "Mleko 2% UHT 1l", "l", 3.29),
        (4.50, "Śmietanka 330 ml", "l", 13.64),
        (2.99, "Napój 1,5l", "l", 1.99),
        (13.29, "Jaja L 10 szt.", "szt", 1.33),
        (13.29, "Jaja kurze 10 sztuk", "szt", 1.33),
    ])
    def test_parses_quantity_from_name(self, price, name, unit, expected):
        assert derive_unit_price(price, name, unit) == expected

    def test_comma_decimal_quantity(self):
        assert derive_unit_price(7.50, "Ser żółty 0,25 kg", "kg") == 30.00

    def test_no_quantity_in_name_returns_none(self):
        assert derive_unit_price(5.99, "Masło extra", "kg") is None

    def test_unit_mismatch_returns_none(self):
        # grams in the name, litres requested — not comparable
        assert derive_unit_price(5.99, "Masło extra 200g", "l") is None

    def test_zero_quantity_returns_none(self):
        assert derive_unit_price(5.99, "Dziwny produkt 0 g", "kg") is None

    def test_case_insensitive_units(self):
        assert derive_unit_price(5.99, "Masło 200G", "kg") == 29.95
