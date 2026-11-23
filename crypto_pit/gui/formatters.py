from __future__ import annotations

from decimal import Decimal

from crypto_pit.datetime_fmt import fmt_datetime, parse_datetime
from crypto_pit.domain.money import decimal_to_text, parse_decimal, quantize

__all__ = [
    "fmt_datetime",
    "fmt_money",
    "fmt_money_compact",
    "fmt_qty",
    "fmt_rate",
    "parse_datetime",
    "parse_decimal",
]


def _decimal(value: Decimal | int) -> Decimal:
    if isinstance(value, bool):
        raise TypeError("niepoprawna liczba")
    return value if isinstance(value, Decimal) else Decimal(value)


def fmt_money(value: Decimal | int | None) -> str:
    if value is None:
        return "—"
    amount = quantize(_decimal(value), 2)
    sign = "-" if amount < 0 else ""
    text = f"{abs(amount):,.2f}".replace(",", " ").replace(".", ",")
    return f"{sign}{text}"


def fmt_money_compact(value: Decimal | int) -> str:
    return f"{quantize(_decimal(value), 2):.2f}".replace(".", ",")


def fmt_qty(value: Decimal | int, digits: int = 8) -> str:
    return decimal_to_text(quantize(_decimal(value), digits))


def fmt_rate(value: Decimal | int | None) -> str:
    if value is None:
        return "—"
    amount = _decimal(value)
    if amount >= 1000:
        return fmt_money(amount)
    return decimal_to_text(quantize(amount, 8))
