from __future__ import annotations

from crypto_pit.datetime_fmt import fmt_datetime, parse_datetime

__all__ = [
    "fmt_datetime",
    "fmt_money",
    "fmt_money_compact",
    "fmt_qty",
    "parse_datetime",
    "parse_float",
]


def fmt_money(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:,.2f}".replace(",", " ").replace(".", ",")


def fmt_money_compact(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")


def fmt_qty(value: float, digits: int = 8) -> str:
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return text if text else "0"


def parse_float(text: str) -> float:
    s = text.strip().replace(" ", "").replace("\u00a0", "").replace(",", ".")
    if not s:
        return 0.0
    return float(s)
