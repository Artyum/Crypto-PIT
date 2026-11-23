from __future__ import annotations

from decimal import Decimal

import pytest
from crypto_pit.datetime_fmt import fmt_datetime, parse_datetime, parse_naive
from crypto_pit.domain.calc import ValidationError, _to_result, resolve_trade
from crypto_pit.domain.enums import TxType, normalize_tx_type
from crypto_pit.domain.exchange_profiles import (
    _coin_amount_fee,
    _coin_amount_fee_coin,
    _fee_coin_final_coin,
    _fee_final_coin,
    get_profile,
    has_profile,
)
from crypto_pit.domain.models import Transaction, YearSettlement
from crypto_pit.domain.pit38 import pit38_short_header
from crypto_pit.gui.formatters import (
    fmt_money,
    fmt_money_compact,
    fmt_qty,
    parse_decimal,
)
from crypto_pit.services.calculator import line_impact, settle_years


def _num(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise TypeError(type(value))
    return Decimal(str(value)) if isinstance(value, float) else Decimal(value)


def _tx(**overrides: object) -> Transaction:
    data: dict[str, object] = {
        "date": parse_naive("2024-06-01 12:00", "%Y-%m-%d %H:%M"),
        "type": TxType.BUY,
        "asset": "btc",
        "amount": Decimal(1),
        "value_pln": Decimal(100),
        "fee_pln": Decimal(1),
        "note": "linia\ndruga",
        "currency": "",
    }
    data.update(overrides)
    for key in (
        "amount",
        "value_pln",
        "fee_pln",
        "value",
        "curr_to_pln",
        "coin_amount",
        "price",
        "price_pln",
        "fee_coin",
        "fee",
        "final_coin",
    ):
        if key in data:
            data[key] = _num(data[key])
    return Transaction(**data)  # type: ignore[arg-type]


def test_datetime_roundtrip_and_other_cost() -> None:
    parsed = parse_datetime(" 2024-01-02T03:04:05 ")
    assert fmt_datetime(parsed) == "2024-01-02 03:04"
    other = _tx(type=TxType.OTHER)
    assert other.pit_cost() == 0
    with pytest.raises(ValueError):
        normalize_tx_type(None)
    with pytest.raises(ValueError):
        normalize_tx_type("  ")
    with pytest.raises(ValueError, match="nieznany"):
        normalize_tx_type("nieznany")
    settlement = YearSettlement(
        year=2024,
        revenue=1,
        costs_current=2,
        costs_prior=3,
        costs_total=5,
        income=0,
        carried_forward=4,
        tax_19=0,
        tx_count=1,
        buy_count=1,
        sell_count=0,
        other_count=0,
    )
    assert settlement.pit_fields()["przychod"] == 1
    assert pit38_short_header("nieznane") == "nieznane"


def test_calc_validation_and_profiles() -> None:
    base = {
        "value": Decimal(10),
        "fee": Decimal(1),
        "fee_coin": Decimal("0.1"),
        "coin_amount": Decimal(2),
        "final_coin": Decimal(1),
        "price": Decimal(4),
    }
    with pytest.raises(ValidationError):
        _to_result({**base, "value": Decimal(0)}, Decimal(1))
    with pytest.raises(ValidationError):
        _to_result({**base, "fee": Decimal(-1)}, Decimal(1))
    with pytest.raises(ValidationError):
        _to_result({**base, "coin_amount": Decimal(0)}, Decimal(1))
    with pytest.raises(ValidationError):
        _to_result(base, Decimal(0))
    with pytest.raises(ValidationError):
        _to_result({**base, "price": Decimal(0)}, Decimal(1))
    with pytest.raises(ValidationError):
        _to_result({**base, "fee_coin": Decimal(-1)}, Decimal(1))
    with pytest.raises(ValidationError):
        _to_result({**base, "final_coin": Decimal(0)}, Decimal(1))

    with pytest.raises(ValidationError):
        resolve_trade(exchange="nieznana", tx_type=TxType.BUY, curr_to_pln=1, value=1)
    assert (
        resolve_trade(exchange="Binance", tx_type=TxType.BUY, curr_to_pln=1, value=None)
        is None
    )
    with pytest.raises(ValidationError):
        resolve_trade(
            exchange="Binance",
            tx_type=TxType.BUY,
            curr_to_pln=1,
            value=10,
            fee=10,
            final_coin=1,
        )
    with pytest.raises(ValueError):
        _fee_final_coin(value=10, fee=10, final_coin=1)
    with pytest.raises(ValueError):
        _coin_amount_fee_coin(value=10, coin_amount=0, fee_coin=0)
    with pytest.raises(ValueError):
        _coin_amount_fee_coin(value=10, coin_amount=1, fee_coin=2)
    with pytest.raises(ValueError):
        _fee_coin_final_coin(value=10, fee_coin=-1, final_coin=1)
    with pytest.raises(ValueError):
        _coin_amount_fee(value=10, coin_amount=0, fee=0)
    with pytest.raises(ValueError):
        _coin_amount_fee(
            value=Decimal(10), coin_amount=Decimal("0.0000001"), fee=Decimal(10)
        )
    with pytest.raises(KeyError):
        get_profile("Kanga", TxType.SELL)
    assert has_profile("Zonda", TxType.BUY)
    assert not has_profile("Kanga", TxType.OTHER)


def test_settle_empty_profit_and_line_impact() -> None:
    assert settle_years([]) == []
    buy = _tx(value_pln=100, fee_pln=0)
    sell = _tx(type=TxType.SELL, value_pln=500, fee_pln=10)
    other = _tx(
        type=TxType.OTHER,
        value_pln=5,
        date=parse_naive("2026-01-01 00:00", "%Y-%m-%d %H:%M"),
    )
    years = {row.year: row for row in settle_years([buy, sell, other])}
    assert years[2024].income > 0
    assert years[2024].carried_forward == 0
    assert years[2025].tx_count == 0
    assert years[2026].other_count == 1
    impact = line_impact(_tx(id=None))
    assert impact["id"] == 0
    assert impact["asset"] == "BTC"
    assert "linia" in str(impact["note"])


def test_formatters() -> None:
    assert fmt_money(None) == "—"
    assert fmt_money(Decimal("1234.5")) == "1 234,50"
    assert fmt_money_compact(Decimal("1.2")) == "1,20"
    assert fmt_qty(Decimal(0)) == "0"
    assert fmt_qty(Decimal("1.5")) == "1.5"
    assert parse_decimal(" 1 234,5 ") == Decimal("1234.5")
    with pytest.raises(ValueError):
        parse_decimal(" \u00a0 ")
