from __future__ import annotations

from datetime import date

import pytest

from crypto_pit.datetime_fmt import parse_naive
from crypto_pit.domain.enums import TxType
from crypto_pit.domain.models import Transaction
from crypto_pit.services.dca import (
    RANGE_ERROR,
    average_purchase_cost,
    buy_years,
    dca_year_bounds,
    default_dca_dates,
    query_dca,
)


def _tx(
    when: str,
    *,
    tx_type: TxType = TxType.BUY,
    asset: str = "BTC",
    value_pln: float = 100.0,
    final_coin: float = 1.0,
    fee_pln: float = 0.0,
) -> Transaction:
    return Transaction(
        date=parse_naive(when, "%Y-%m-%d %H:%M"),
        type=tx_type,
        asset=asset,
        amount=final_coin,
        value_pln=value_pln,
        fee_pln=fee_pln,
        final_coin=final_coin,
    )


def test_dca_weights_cheaper_purchase_by_quantity() -> None:
    result = average_purchase_cost(
        [
            _tx("2024-01-01 10:00", asset="btc", value_pln=100_000, final_coin=1),
            _tx("2024-02-01 10:00", asset=" BTC ", value_pln=100_000, final_coin=2),
        ],
        date(2024, 1, 1),
        date(2024, 12, 31),
    )

    assert result.error == ""
    assert result.total_purchases == 2
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row.asset == "BTC"
    assert row.count == 2
    assert row.total_pln == pytest.approx(200_000)
    assert row.total_qty == pytest.approx(3)
    assert row.dca == pytest.approx(200_000 / 3)
    assert result.purchases_by_asset["BTC"][1].quantity == pytest.approx(2)


def test_range_includes_both_end_days_and_excludes_neighbours() -> None:
    result = average_purchase_cost(
        [
            _tx("2024-03-09 23:59", value_pln=1, final_coin=1),
            _tx("2024-03-10 00:00", value_pln=10, final_coin=1),
            _tx("2024-03-12 23:59", value_pln=30, final_coin=1),
            _tx("2024-03-13 00:00", value_pln=1000, final_coin=1),
        ],
        date(2024, 3, 10),
        date(2024, 3, 12),
    )

    assert result.total_purchases == 2
    assert result.rows[0].total_pln == pytest.approx(40)
    assert result.rows[0].dca == pytest.approx(20)


def test_sell_and_other_are_ignored() -> None:
    result = average_purchase_cost(
        [
            _tx("2024-05-01 12:00", value_pln=80, final_coin=2),
            _tx("2024-05-01 13:00", tx_type=TxType.SELL, value_pln=500, final_coin=2),
            _tx("2024-05-02 13:00", tx_type=TxType.OTHER, value_pln=500, final_coin=2),
        ],
        date(2024, 5, 1),
        date(2024, 5, 2),
    )

    assert result.total_purchases == 1
    assert result.rows[0].dca == pytest.approx(40)
    assert len(result.purchases_by_asset["BTC"]) == 1


def test_fee_pln_does_not_increase_cost() -> None:
    result = average_purchase_cost(
        [_tx("2024-06-01 09:00", value_pln=100, final_coin=1, fee_pln=5)],
        date(2024, 6, 1),
        date(2024, 6, 1),
    )

    purchase = result.purchases_by_asset["BTC"][0]
    assert result.rows[0].dca == pytest.approx(100)
    assert result.rows[0].total_pln == pytest.approx(100)
    assert purchase.quantity == pytest.approx(1)
    assert purchase.unit_price == pytest.approx(100)


def test_invalid_buy_is_skipped_and_valid_neighbour_remains() -> None:
    invalid = _tx("2024-07-01 10:00", asset="ETH", value_pln=10, final_coin=1)
    invalid.value_pln = None  # type: ignore[assignment]
    result = average_purchase_cost(
        [
            _tx("2024-07-01 11:00", asset="ETH", value_pln=50, final_coin=2),
            _tx("2024-07-01 12:00", asset="ETH", value_pln=-10, final_coin=1),
            _tx("2024-07-01 13:00", asset="ETH", value_pln=float("nan"), final_coin=1),
            _tx("2024-07-01 14:00", asset="ETH", value_pln=float("inf"), final_coin=1),
            _tx("2024-07-01 15:00", asset="ETH", value_pln=10, final_coin=0),
            _tx("2024-07-01 16:00", asset="ETH", value_pln=10, final_coin=-1),
            _tx("2024-07-01 17:00", asset="  ", value_pln=10, final_coin=1),
            invalid,
        ],
        date(2024, 7, 1),
        date(2024, 7, 1),
    )

    assert result.error == ""
    assert result.total_purchases == 1
    assert result.rows[0].asset == "ETH"
    assert result.rows[0].dca == pytest.approx(25)
    assert result.purchases_by_asset["ETH"][0].unit_price == pytest.approx(25)


def test_no_buys_returns_empty_result() -> None:
    result = average_purchase_cost([], date(2024, 1, 1), date(2024, 1, 31))

    assert result.rows == ()
    assert result.purchases_by_asset == {}
    assert result.total_purchases == 0
    assert result.error == ""


def test_reversed_range_returns_error_without_rows() -> None:
    result = average_purchase_cost(
        [_tx("2024-08-01 10:00", value_pln=100, final_coin=1)],
        date(2024, 8, 2),
        date(2024, 8, 1),
    )

    assert result.error == RANGE_ERROR
    assert result.rows == ()
    assert result.total_purchases == 0


def test_year_bounds_cover_full_calendar_year() -> None:
    assert dca_year_bounds(2024) == ("2024-01-01", "2024-12-31")
    assert buy_years(
        [
            _tx("2023-12-31 23:59"),
            _tx("2024-01-01 00:00"),
            _tx("2024-06-01 00:00", tx_type=TxType.SELL),
        ]
    ) == (2023, 2024)


def test_default_dates_span_buys_only() -> None:
    today = date(2026, 11, 19)

    assert default_dca_dates([], today) == ("", "2026-11-19")
    assert default_dca_dates(
        [
            _tx("2024-02-02 08:00"),
            _tx("2024-01-05 08:00"),
            _tx("2024-06-01 08:00", tx_type=TxType.SELL),
        ],
        today,
    ) == ("2024-01-05", "2024-02-02")


def test_query_explains_empty_invalid_and_reversed_input() -> None:
    buy = _tx("2024-04-01 10:00")

    assert query_dca([buy], "2024-04-01", "").message == "Podaj datę do."
    assert query_dca([buy], "2024-04-01", "zle").message == "Nieprawidłowa data."
    assert query_dca([buy], "", "2024-04-01").message == "Podaj datę od."
    assert query_dca([], "", "2024-04-01").message == "Brak zakupów."
    assert query_dca([buy], "2024-05-01", "2024-04-01").message == RANGE_ERROR
    outside = query_dca([buy], "2024-05-01", "2024-05-02")
    assert outside.message == "W tym zakresie nie ma zakupów."
    assert outside.result.total_purchases == 0
    inside = query_dca([buy], "2024-04-01", "2024-04-01")
    assert inside.message == ""
    assert inside.result.total_purchases == 1
