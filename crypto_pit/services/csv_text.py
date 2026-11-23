from __future__ import annotations

from decimal import Decimal

from crypto_pit.domain.money import (
    DecimalError,
    decimal_to_text,
    parse_decimal,
    quantize,
)


def format_decimal(value: Decimal | int, places: int | None = None) -> str:
    if isinstance(value, bool):
        raise DecimalError("niepoprawna liczba")
    number = value if isinstance(value, Decimal) else Decimal(value)
    if places is not None:
        number = quantize(number, places)
    return decimal_to_text(number).replace(".", ",")


def parse_cell_decimal(text: str) -> Decimal:
    return parse_decimal(text)
