from __future__ import annotations

from decimal import Decimal

from crypto_pit.datetime_fmt import parse_naive
from crypto_pit.domain.enums import TxType
from crypto_pit.domain.models import Transaction
from crypto_pit.domain.pit38 import round_pit_amount
from crypto_pit.services.calculator import settle_years


def _transaction(tx_type: TxType, *, value_pln: str, fee_pln: str = "0") -> Transaction:
    return Transaction(
        date=parse_naive("2025-01-01 00:00", "%Y-%m-%d %H:%M"),
        type=tx_type,
        asset="BTC",
        amount=Decimal(1),
        value_pln=Decimal(value_pln),
        fee_pln=Decimal(fee_pln),
    )


def test_buy_cost_is_total_amount_debited_from_account() -> None:
    buy = _transaction(TxType.BUY, value_pln="1000", fee_pln="10")

    assert buy.pit_cost() == Decimal(1000)


def test_sale_commission_is_tax_cost() -> None:
    sale = _transaction(TxType.SELL, value_pln="120.99", fee_pln="0.53")

    assert sale.pit_revenue() == Decimal("120.99")
    assert sale.pit_cost() == Decimal("0.53")


def test_pit_amount_rounding_discards_under_fifty_groszy() -> None:
    assert round_pit_amount(Decimal("120.49")) == 120


def test_pit_amount_rounding_increases_fifty_groszy_or_more() -> None:
    assert round_pit_amount(Decimal("120.50")) == 121


def test_year_settlement_includes_sale_commission_in_current_costs() -> None:
    settlement = settle_years(
        [
            _transaction(TxType.BUY, value_pln="1000"),
            _transaction(TxType.SELL, value_pln="120.99", fee_pln="0.53"),
        ]
    )[0]

    assert settlement.revenue == 121
    assert settlement.costs_current == 1001
    assert settlement.carried_forward == 880
