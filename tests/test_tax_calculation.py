from __future__ import annotations

from crypto_pit.datetime_fmt import parse_naive
from crypto_pit.domain.enums import TxType
from crypto_pit.domain.models import Transaction
from crypto_pit.domain.pit38 import round_pit_amount
from crypto_pit.services.calculator import settle_years


def _transaction(
    tx_type: TxType, *, value_pln: float, fee_pln: float = 0.0
) -> Transaction:
    return Transaction(
        date=parse_naive("2025-01-01 00:00", "%Y-%m-%d %H:%M"),
        type=tx_type,
        asset="BTC",
        amount=1.0,
        value_pln=value_pln,
        fee_pln=fee_pln,
    )


def test_buy_cost_is_total_amount_debited_from_account() -> None:
    buy = _transaction(TxType.BUY, value_pln=1000.0, fee_pln=10.0)

    assert buy.pit_cost() == 1000.0


def test_sale_commission_is_tax_cost() -> None:
    sale = _transaction(TxType.SELL, value_pln=120.99, fee_pln=0.53)

    assert sale.pit_revenue() == 120.99
    assert sale.pit_cost() == 0.53


def test_pit_amount_rounding_discards_under_fifty_groszy() -> None:
    assert round_pit_amount(120.49) == 120


def test_pit_amount_rounding_increases_fifty_groszy_or_more() -> None:
    assert round_pit_amount(120.50) == 121


def test_year_settlement_includes_sale_commission_in_current_costs() -> None:
    settlement = settle_years(
        [
            _transaction(TxType.BUY, value_pln=1000.0),
            _transaction(TxType.SELL, value_pln=120.99, fee_pln=0.53),
        ]
    )[0]

    assert settlement.revenue == 121
    assert settlement.costs_current == 1001
    assert settlement.carried_forward == 880
