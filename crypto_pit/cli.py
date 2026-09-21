from __future__ import annotations

from pathlib import Path

from crypto_pit.infrastructure.database import Database
from crypto_pit.services.calculator import settle_years


def run_cli(db_path: Path | None = None) -> None:
    db = Database(db_path)
    try:
        txs = db.list_transactions()
        for s in settle_years(txs):
            print(
                f"\n==== ROK {s.year} ====\n"
                f"  Przychód:                 {s.revenue:12.2f} PLN\n"
                f"  Koszty bieżące:           {s.costs_current:12.2f} PLN\n"
                f"  Koszty lat ubiegłych:     {s.costs_prior:12.2f} PLN\n"
                f"  Dochód:                   {s.income:12.2f} PLN\n"
                f"  Koszty do przeniesienia:  {s.carried_forward:12.2f} PLN\n"
                f"  Podatek 19%:              {s.tax_19:12.2f} PLN"
            )
    finally:
        db.close()
