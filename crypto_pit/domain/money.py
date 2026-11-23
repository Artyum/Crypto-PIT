from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_CURRENCY = re.compile(r"^[A-Z]{3}$")
_NUMBER = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")


class DecimalError(ValueError):
    pass


def parse_decimal(value: object) -> Decimal:
    if isinstance(value, bool | float):
        raise DecimalError("oczekiwano Decimal")
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, int):
        number = Decimal(value)
    elif isinstance(value, str):
        text = (
            value.strip()
            .replace("\u00a0", "")
            .replace(" ", "")
            .replace("−", "-")
            .replace(",", ".")
        )
        if not _NUMBER.fullmatch(text):
            raise DecimalError("niepoprawna liczba")
        try:
            number = Decimal(text)
        except InvalidOperation as exc:
            raise DecimalError("niepoprawna liczba") from exc
    else:
        raise DecimalError("niepoprawna liczba")
    if not number.is_finite():
        raise DecimalError("liczba musi być skończona")
    return number


def decimal_from_legacy_real(value: float) -> Decimal:
    if not math.isfinite(value):
        raise DecimalError("liczba musi być skończona")
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise DecimalError("niepoprawna liczba") from exc


def quantize(value: Decimal, places: int) -> Decimal:
    number = parse_decimal(value)
    quantum = Decimal(1).scaleb(-places)
    return number.quantize(quantum, rounding=ROUND_HALF_UP)


def decimal_to_text(value: Decimal) -> str:
    text = format(parse_decimal(value), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in {"", "-", "-0"}:
        return "0"
    return text


def currency_code(value: object) -> str:
    if not isinstance(value, str):
        raise DecimalError("niepoprawny kod waluty")
    code = value.strip().upper()
    if _CURRENCY.fullmatch(code) is None:
        raise DecimalError(f"niepoprawny kod waluty: {value}")
    return code
