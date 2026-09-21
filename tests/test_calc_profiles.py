from __future__ import annotations

import pytest

from crypto_pit.domain.calc import resolve_trade
from crypto_pit.domain.enums import TxType
from crypto_pit.domain.exchange_profiles import get_profile


def test_binance_buy_fee_final_coin() -> None:
    result = resolve_trade(
        exchange="Binance",
        tx_type=TxType.BUY,
        curr_to_pln=1.0,
        value=500.0,
        fee=10.0,
        final_coin=0.00513159,
    )
    assert result == {
        "value": 500.0,
        "fee": 10.0,
        "fee_coin": 0.00010473,
        "coin_amount": 0.00523632,
        "final_coin": 0.00513159,
        "price": 95486.973823,
        "price_pln": 95486.97,
        "fee_pln": 10.0,
        "value_pln": 500.0,
        "curr_to_pln": 1.0,
    }


def test_zonda_buy_coin_amount_fee_coin() -> None:
    result = resolve_trade(
        exchange="Zonda",
        tx_type=TxType.BUY,
        curr_to_pln=4.6682,
        value=20.41,
        coin_amount=0.01266333,
        fee_coin=0.00005446,
    )
    assert result is not None
    assert result["curr_to_pln"] == 4.6682
    assert result["value"] == 20.41
    assert result["value_pln"] == 95.28
    assert result["coin_amount"] == 0.01266333
    assert result["price"] == 1611.740356
    assert result["price_pln"] == 7523.93
    assert result["fee_coin"] == 0.00005446
    assert result["fee"] == pytest.approx(0.08777537978)
    assert result["fee_pln"] == 0.41
    assert result["final_coin"] == 0.01260887


def test_kanga_buy_fee_coin_final_coin() -> None:
    result = resolve_trade(
        exchange="Kanga",
        tx_type=TxType.BUY,
        curr_to_pln=4.1167,
        value=4848.11,
        fee_coin=0.0,
        final_coin=0.17583910,
    )
    assert result is not None
    assert result["value_pln"] == 19958.21
    assert result["coin_amount"] == 0.17583910
    assert result["price"] == 27571.285340
    assert result["price_pln"] == 113502.71
    assert result["fee"] == 0.0
    assert result["fee_coin"] == 0.0
    assert result["final_coin"] == 0.17583910


def test_kanga_buy_price_uses_coin_amount() -> None:
    result = resolve_trade(
        exchange="Kanga",
        tx_type=TxType.BUY,
        curr_to_pln=1.0,
        value=992.39,
        fee_coin=0.00000717,
        final_coin=0.0035928,
    )
    assert result is not None
    assert result["coin_amount"] == 0.00359997
    assert result["price"] == 275666.186107
    assert result["price_pln"] == 275666.19
    assert result["fee"] == pytest.approx(1.9765265543879533)
    assert result["fee_pln"] == 1.98


def test_binance_sell_coin_amount_fee_zero() -> None:
    result = resolve_trade(
        exchange="Binance",
        tx_type=TxType.SELL,
        curr_to_pln=4.7731,
        value=38.56,
        coin_amount=0.00165500,
        fee=0.0,
    )
    assert result is not None
    assert result["value_pln"] == 184.05
    assert result["price"] == 23299.093656
    assert result["price_pln"] == 111208.90
    assert result["fee_coin"] == 0.0
    assert result["final_coin"] == 0.00165500


def test_zonda_sell_coin_amount_fee() -> None:
    result = resolve_trade(
        exchange="Zonda",
        tx_type=TxType.SELL,
        curr_to_pln=1.0,
        value=120.99,
        coin_amount=0.01727618,
        fee=0.53,
    )
    assert result is not None
    assert result["price"] == 7003.284291
    assert result["price_pln"] == 7003.28
    assert result["fee_coin"] == 0.00007568
    assert result["final_coin"] == 0.01720050
    assert result["fee_pln"] == 0.53


@pytest.mark.parametrize("exchange", ["OKX", "Kraken", "Coinbase"])
def test_binance_like_exchanges_share_buy_profile(exchange: str) -> None:
    assert get_profile(exchange, TxType.BUY).id == get_profile("Binance", TxType.BUY).id
    assert (
        get_profile(exchange, TxType.SELL).id == get_profile("Binance", TxType.SELL).id
    )


def test_incomplete_inputs_return_none() -> None:
    assert (
        resolve_trade(
            exchange="Binance",
            tx_type=TxType.BUY,
            curr_to_pln=1.0,
            value=500.0,
            fee=10.0,
        )
        is None
    )
