from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from crypto_pit.datetime_fmt import make_local_datetime
from crypto_pit.domain.enums import TxType
from crypto_pit.domain.models import Transaction

RANGE_ERROR = "Data od jest późniejsza niż data do."


@dataclass(frozen=True)
class DcaPurchase:
    date: datetime
    quantity: Decimal
    value_pln: Decimal
    unit_price: Decimal


@dataclass(frozen=True)
class DcaRow:
    asset: str
    count: int
    total_pln: Decimal
    total_qty: Decimal
    dca: Decimal


@dataclass(frozen=True)
class DcaResult:
    rows: tuple[DcaRow, ...]
    purchases_by_asset: dict[str, tuple[DcaPurchase, ...]]
    total_purchases: int
    error: str


def _inclusive_day_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = make_local_datetime(date_from.year, date_from.month, date_from.day)
    next_day = date_to + timedelta(days=1)
    end = make_local_datetime(next_day.year, next_day.month, next_day.day)
    return start, end


def _positive_finite(value: Decimal) -> Decimal | None:
    if value.is_finite() and value > 0:
        return value
    return None


def _is_naive_buy(tx: Transaction) -> bool:
    return (
        tx.type == TxType.BUY
        and isinstance(tx.date, datetime)
        and tx.date.tzinfo is None
    )


def _buy_parts(tx: Transaction) -> tuple[str, Decimal, Decimal] | None:
    if not _is_naive_buy(tx):
        return None
    symbol = str(tx.asset or "").strip().upper()
    if not symbol:
        return None
    value = _positive_finite(tx.value_pln)
    quantity = _positive_finite(tx.final_coin)
    if value is None or quantity is None:
        return None
    return symbol, value, quantity


def average_purchase_cost(
    transactions: Sequence[Transaction],
    date_from: date,
    date_to: date,
) -> DcaResult:
    if date_from > date_to:
        return DcaResult((), {}, 0, RANGE_ERROR)
    start, end = _inclusive_day_bounds(date_from, date_to)
    grouped: dict[str, list[DcaPurchase]] = {}
    for tx in transactions:
        parts = _buy_parts(tx)
        if parts is None or not (start <= tx.date < end):
            continue
        symbol, value, quantity = parts
        grouped.setdefault(symbol, []).append(
            DcaPurchase(
                date=tx.date,
                quantity=quantity,
                value_pln=value,
                unit_price=value / quantity,
            )
        )
    rows: list[DcaRow] = []
    purchases: dict[str, tuple[DcaPurchase, ...]] = {}
    total = 0
    for symbol in sorted(grouped):
        items = tuple(sorted(grouped[symbol], key=lambda item: item.date))
        total_pln = sum((item.value_pln for item in items), start=Decimal(0))
        total_qty = sum((item.quantity for item in items), start=Decimal(0))
        rows.append(
            DcaRow(
                asset=symbol,
                count=len(items),
                total_pln=total_pln,
                total_qty=total_qty,
                dca=total_pln / total_qty,
            )
        )
        purchases[symbol] = items
        total += len(items)
    return DcaResult(tuple(rows), purchases, total, "")


@dataclass(frozen=True)
class DcaQuery:
    result: DcaResult
    message: str


def dca_year_bounds(year: int) -> tuple[str, str]:
    return date(year, 1, 1).isoformat(), date(year, 12, 31).isoformat()


def buy_years(transactions: Sequence[Transaction]) -> tuple[int, ...]:
    years = {tx.date.year for tx in transactions if _is_naive_buy(tx)}
    return tuple(sorted(years))


def default_dca_dates(
    transactions: Sequence[Transaction], today: date
) -> tuple[str, str]:
    moments = [tx.date for tx in transactions if _is_naive_buy(tx)]
    if not moments:
        return "", today.isoformat()
    return min(moments).date().isoformat(), max(moments).date().isoformat()


def parse_dca_day(text: str) -> date | None:
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        return None


def query_dca(
    transactions: Sequence[Transaction],
    date_from_text: str,
    date_to_text: str,
) -> DcaQuery:
    empty = DcaResult((), {}, 0, "")
    has_buys = any(_buy_parts(tx) is not None for tx in transactions)
    end_text = date_to_text.strip()
    start_text = date_from_text.strip()
    if not end_text:
        return DcaQuery(empty, "Podaj datę do.")
    date_to = parse_dca_day(end_text)
    if date_to is None:
        return DcaQuery(empty, "Nieprawidłowa data.")
    if not start_text:
        message = "Podaj datę od." if has_buys else "Brak zakupów."
        return DcaQuery(empty, message)
    date_from = parse_dca_day(start_text)
    if date_from is None:
        return DcaQuery(empty, "Nieprawidłowa data.")
    result = average_purchase_cost(transactions, date_from, date_to)
    if result.error:
        return DcaQuery(result, result.error)
    if result.rows:
        return DcaQuery(result, "")
    if has_buys:
        return DcaQuery(result, "W tym zakresie nie ma zakupów.")
    return DcaQuery(result, "Brak zakupów.")
