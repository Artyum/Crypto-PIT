from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

PIT38_SECTION = "E"
PIT38_NEW_FIELDS_FROM_YEAR = 2025

PIT38_FIELD_KEYS = (
    "przychod",
    "koszty_biezace",
    "koszty_lat_ubieglych",
    "dochod",
    "koszty_do_przeniesienia",
    "podatek_19",
)

_SHORT_LABELS: dict[str, str] = {
    "przychod": "Przychód",
    "koszty_biezace": "Koszty roku",
    "koszty_lat_ubieglych": "Koszty lat ub.",
    "dochod": "Dochód",
    "koszty_do_przeniesienia": "Do przeniesienia",
}


@dataclass(frozen=True, slots=True)
class Pit38Field:
    key: str
    field_no: str | None
    label: str
    formula: str | None = None


def _field_numbers(year: int) -> tuple[str, ...]:
    if year >= PIT38_NEW_FIELDS_FROM_YEAR:
        return ("36", "37", "38", "39", "40")
    return ("34", "35", "36", "37", "38")


def pit38_fields_for_year(year: int) -> tuple[Pit38Field, ...]:
    przychod, koszty_biezace, koszty_lat_ubieglych, dochod, koszty_do_przeniesienia = (
        _field_numbers(year)
    )
    return (
        Pit38Field("przychod", przychod, "Przychód"),
        Pit38Field(
            "koszty_biezace",
            koszty_biezace,
            "Koszty poniesione w roku podatkowym",
        ),
        Pit38Field(
            "koszty_lat_ubieglych",
            koszty_lat_ubieglych,
            "Koszty z lat ubiegłych, niepotrącone w poprzednim roku",
        ),
        Pit38Field(
            "dochod",
            dochod,
            "Dochód",
            f"{przychod} − ({koszty_biezace} + {koszty_lat_ubieglych})",
        ),
        Pit38Field(
            "koszty_do_przeniesienia",
            koszty_do_przeniesienia,
            "Koszty niepotrącone w roku",
            f"({koszty_biezace} + {koszty_lat_ubieglych}) − {przychod}",
        ),
        Pit38Field(
            "podatek_19",
            None,
            "Podatek 19%",
            "poza częścią E — orientacyjnie",
        ),
    )


def pit38_field_range(year: int) -> str:
    numbers = _field_numbers(year)
    return f"{numbers[0]}–{numbers[-1]}"


def round_pit_amount(value: float) -> int:
    """Zaokrąglij kwotę do pełnych złotych według zasad dla zeznań PIT."""
    return int(Decimal(str(value)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def pit38_short_header(key: str) -> str:
    return _SHORT_LABELS.get(key, key)
