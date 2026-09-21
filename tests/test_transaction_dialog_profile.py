from __future__ import annotations

from crypto_pit.domain.enums import TxType
from crypto_pit.domain.exchange_profiles import get_profile
from crypto_pit.gui.dialogs import (
    migrate_profile_inputs,
    value_input_labels,
    visible_input_fields,
)


def test_visible_fields_binance_buy() -> None:
    assert visible_input_fields("Binance", TxType.BUY) == ("final_coin", "fee")


def test_visible_fields_zonda_buy() -> None:
    assert visible_input_fields("Zonda", TxType.BUY) == ("coin_amount", "fee_coin")


def test_visible_fields_kanga_buy() -> None:
    assert visible_input_fields("Kanga", TxType.BUY) == ("final_coin", "fee_coin")


def test_visible_fields_binance_sell() -> None:
    assert visible_input_fields("Binance", TxType.SELL) == ("coin_amount", "fee")


def test_sale_value_is_described_as_gross_before_commission() -> None:
    assert value_input_labels("Zonda", TxType.SELL) == (
        "Wartość sprzedaży brutto",
        "Kwota uzyskana ze sprzedaży przed potrąceniem prowizji.",
    )


def test_visible_fields_coinbase_matches_binance() -> None:
    assert visible_input_fields("Coinbase", TxType.BUY) == visible_input_fields(
        "Binance", TxType.BUY
    )


def test_migrate_keeps_shared_coin_amount() -> None:
    old_p = get_profile("Zonda", TxType.BUY)
    new_p = get_profile("Zonda", TxType.SELL)
    values = {
        "fee": None,
        "fee_coin": 0.00005446,
        "coin_amount": 0.01266333,
        "final_coin": None,
    }
    migrated = migrate_profile_inputs(values, old_p, new_p)
    assert migrated["coin_amount"] == 0.01266333
    assert migrated["fee"] is None
    assert migrated["fee_coin"] is None
    assert migrated["final_coin"] is None


def test_migrate_clears_when_no_overlap() -> None:
    old_p = get_profile("Binance", TxType.BUY)
    new_p = get_profile("Zonda", TxType.BUY)
    values = {
        "fee": 10.0,
        "fee_coin": None,
        "coin_amount": None,
        "final_coin": 0.00513159,
    }
    migrated = migrate_profile_inputs(values, old_p, new_p)
    assert migrated == {
        "fee": None,
        "fee_coin": None,
        "coin_amount": None,
        "final_coin": None,
    }
