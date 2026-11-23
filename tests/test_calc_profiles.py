from __future__ import annotations

from decimal import Decimal

import pytest
from crypto_pit.domain.calc import resolve_trade
from crypto_pit.domain.enums import TxType
from crypto_pit.domain.exchange_profiles import get_profile


def _d(value: object) -> object:
    if isinstance(value, float):
        return Decimal(str(value))
    return value


def trade(**kwargs: object):
    return resolve_trade(**{key: _d(value) for key, value in kwargs.items()})  # type: ignore[arg-type]


def eq(actual: object, expected: object) -> None:
    if isinstance(expected, float):
        expected = Decimal(str(expected))
    assert actual == expected


def test_binance_buy_fee_final_coin() -> None:
    result = trade(
        exchange="Binance",
        tx_type=TxType.BUY,
        curr_to_pln=1.0,
        value=500.0,
        fee=10.0,
        final_coin=0.00513159,
    )
    assert result is not None
    expected = {
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
    for key, value in expected.items():
        eq(result[key], value)


def test_zonda_buy_coin_amount_fee_coin() -> None:
    result = trade(
        exchange="Zonda",
        tx_type=TxType.BUY,
        curr_to_pln=4.6682,
        value=20.41,
        coin_amount=0.01266333,
        fee_coin=0.00005446,
    )
    assert result is not None
    eq(result["curr_to_pln"], 4.6682)
    eq(result["value"], 20.41)
    eq(result["value_pln"], 95.28)
    eq(result["coin_amount"], 0.01266333)
    eq(result["price"], 1611.740356)
    eq(result["price_pln"], 7523.93)
    eq(result["fee_coin"], 0.00005446)
    eq(result["fee"], Decimal("0.08777537978776"))
    eq(result["fee_pln"], 0.41)
    eq(result["final_coin"], 0.01260887)


def test_kanga_buy_fee_coin_final_coin() -> None:
    result = trade(
        exchange="Kanga",
        tx_type=TxType.BUY,
        curr_to_pln=4.1167,
        value=4848.11,
        fee_coin=0.0,
        final_coin=0.17583910,
    )
    assert result is not None
    eq(result["value_pln"], 19958.21)
    eq(result["coin_amount"], 0.17583910)
    eq(result["price"], 27571.285340)
    eq(result["price_pln"], 113502.71)
    eq(result["fee"], 0.0)
    eq(result["fee_coin"], 0.0)
    eq(result["final_coin"], 0.17583910)


def test_kanga_buy_price_uses_coin_amount() -> None:
    result = trade(
        exchange="Kanga",
        tx_type=TxType.BUY,
        curr_to_pln=1.0,
        value=992.39,
        fee_coin=0.00000717,
        final_coin=0.0035928,
    )
    assert result is not None
    eq(result["coin_amount"], 0.00359997)
    eq(result["price"], 275666.186107)
    eq(result["price_pln"], 275666.19)
    eq(result["fee"], Decimal("1.97652655438719"))
    eq(result["fee_pln"], 1.98)


def test_binance_sell_coin_amount_fee_zero() -> None:
    result = trade(
        exchange="Binance",
        tx_type=TxType.SELL,
        curr_to_pln=4.7731,
        value=38.56,
        coin_amount=0.00165500,
        fee=0.0,
    )
    assert result is not None
    eq(result["value_pln"], 184.05)
    eq(result["price"], 23299.093656)
    eq(result["price_pln"], 111208.90)
    eq(result["fee_coin"], 0.0)
    eq(result["final_coin"], 0.00165500)


def test_zonda_sell_coin_amount_fee() -> None:
    result = trade(
        exchange="Zonda",
        tx_type=TxType.SELL,
        curr_to_pln=1.0,
        value=120.99,
        coin_amount=0.01727618,
        fee=0.53,
    )
    assert result is not None
    eq(result["price"], 7003.284291)
    eq(result["price_pln"], 7003.28)
    eq(result["fee_coin"], 0.00007568)
    eq(result["final_coin"], 0.01720050)
    eq(result["fee_pln"], 0.53)


@pytest.mark.parametrize("exchange", ["OKX", "Kraken", "Coinbase"])
def test_binance_like_exchanges_share_buy_profile(exchange: str) -> None:
    assert get_profile(exchange, TxType.BUY).id == get_profile("Binance", TxType.BUY).id
    assert (
        get_profile(exchange, TxType.SELL).id == get_profile("Binance", TxType.SELL).id
    )


def test_incomplete_inputs_return_none() -> None:
    assert (
        trade(
            exchange="Binance",
            tx_type=TxType.BUY,
            curr_to_pln=1.0,
            value=500.0,
            fee=10.0,
        )
        is None
    )
