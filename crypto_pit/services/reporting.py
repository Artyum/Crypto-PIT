from __future__ import annotations

import csv
from pathlib import Path

from crypto_pit.domain.models import Transaction, YearSettlement
from crypto_pit.domain.pit38 import pit38_short_header
from crypto_pit.services.calculator import line_impact


def export_report(
    path: Path | str,
    transactions: list[Transaction],
    settlements: list[YearSettlement],
) -> None:
    path = Path(path)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["=== TRANSAKCJE ==="])
        w.writerow(
            [
                "ID",
                "Data",
                "Typ",
                "Walor",
                "Ilość",
                "Waluta",
                "Kurs",
                "Cena",
                "Wartość PLN",
                "Prowizja PLN",
                "Prowizja (walor)",
                "Przychód PIT",
                "Koszt PIT",
                "Uwagi",
            ]
        )
        for tx in sorted(transactions, key=lambda t: (t.date, t.id or 0)):
            impact = line_impact(tx)
            w.writerow(
                [
                    impact["id"],
                    impact["date"],
                    impact["type"],
                    impact["asset"],
                    f"{impact['amount']:.8f}".replace(".", ","),
                    tx.currency or "PLN",
                    f"{tx.curr_to_pln:.6f}".replace(".", ","),
                    f"{tx.price:.6f}".replace(".", ","),
                    f"{impact['value_pln']:.2f}".replace(".", ","),
                    f"{impact['fee_pln']:.2f}".replace(".", ","),
                    f"{tx.fee_coin:.8f}".replace(".", ","),
                    f"{impact['przychod']:.2f}".replace(".", ","),
                    f"{impact['koszt']:.2f}".replace(".", ","),
                    str(impact["note"]).replace("\n", " | "),
                ]
            )

        w.writerow([])
        w.writerow(["=== ROZLICZENIE LAT (PIT-38) ==="])
        w.writerow(
            [
                "Rok",
                pit38_short_header("przychod"),
                pit38_short_header("koszty_biezace"),
                pit38_short_header("koszty_lat_ubieglych"),
                "Razem",
                pit38_short_header("dochod"),
                pit38_short_header("koszty_do_przeniesienia"),
                "Podatek 19%",
                "Liczba transakcji",
            ]
        )
        for s in settlements:
            w.writerow(
                [
                    s.year,
                    f"{s.revenue:.2f}".replace(".", ","),
                    f"{s.costs_current:.2f}".replace(".", ","),
                    f"{s.costs_prior:.2f}".replace(".", ","),
                    f"{s.costs_total:.2f}".replace(".", ","),
                    f"{s.income:.2f}".replace(".", ","),
                    f"{s.carried_forward:.2f}".replace(".", ","),
                    f"{s.tax_19:.2f}".replace(".", ","),
                    s.tx_count,
                ]
            )
