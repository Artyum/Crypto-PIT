from __future__ import annotations

import csv
from pathlib import Path

from crypto_pit.domain.models import Transaction, YearSettlement
from crypto_pit.domain.pit38 import pit38_short_header
from crypto_pit.services.calculator import line_impact
from crypto_pit.services.csv_text import format_decimal


def export_report(
    path: Path | str,
    transactions: list[Transaction],
    settlements: list[YearSettlement],
) -> None:
    path = Path(path)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(["=== TRANSAKCJE ==="])
        writer.writerow(
            [
                "ID",
                "Data",
                "Typ",
                "Walor",
                "Ilość",
                "Waluta",
                "Kurs",
                "Data kursu NBP",
                "Cena",
                "Wartość PLN",
                "Prowizja PLN",
                "Prowizja (walor)",
                "Przychód PIT",
                "Koszt PIT",
                "Uwagi",
            ]
        )
        for tx in sorted(transactions, key=lambda item: (item.date, item.id or 0)):
            impact = line_impact(tx)
            writer.writerow(
                [
                    impact["id"],
                    impact["date"],
                    impact["type"],
                    impact["asset"],
                    format_decimal(tx.amount, 8),
                    tx.currency or "PLN",
                    format_decimal(tx.curr_to_pln, 6),
                    tx.nbp_date.isoformat() if tx.nbp_date else "",
                    format_decimal(tx.price, 6),
                    format_decimal(tx.value_pln, 2),
                    format_decimal(tx.fee_pln, 2),
                    format_decimal(tx.fee_coin, 8),
                    format_decimal(tx.pit_revenue(), 2),
                    format_decimal(tx.pit_cost(), 2),
                    str(impact["note"]).replace("\n", " | "),
                ]
            )

        writer.writerow([])
        writer.writerow(["=== ROZLICZENIE LAT (PIT-38) ==="])
        writer.writerow(
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
        for settlement in settlements:
            writer.writerow(
                [
                    settlement.year,
                    format_decimal(settlement.revenue, 2),
                    format_decimal(settlement.costs_current, 2),
                    format_decimal(settlement.costs_prior, 2),
                    format_decimal(settlement.costs_total, 2),
                    format_decimal(settlement.income, 2),
                    format_decimal(settlement.carried_forward, 2),
                    format_decimal(settlement.tax_19, 2),
                    settlement.tx_count,
                ]
            )
