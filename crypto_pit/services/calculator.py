from __future__ import annotations

from crypto_pit.config import TAX_RATE
from crypto_pit.datetime_fmt import fmt_datetime
from crypto_pit.domain.enums import TxType
from crypto_pit.domain.models import Transaction, YearSettlement
from crypto_pit.domain.pit38 import round_pit_amount


def settle_years(transactions: list[Transaction]) -> list[YearSettlement]:
    if not transactions:
        return []

    years_present = {t.year for t in transactions}
    year_min = min(years_present)
    year_max = max(years_present)
    all_years = list(range(year_min, year_max + 1))

    by_year: dict[int, list[Transaction]] = {y: [] for y in all_years}
    for t in transactions:
        by_year.setdefault(t.year, []).append(t)

    carried = 0
    results: list[YearSettlement] = []

    for year in all_years:
        txs = by_year.get(year, [])
        revenue = round_pit_amount(sum(t.pit_revenue() for t in txs))
        costs_current = round_pit_amount(sum(t.pit_cost() for t in txs))
        costs_prior = carried
        costs_total = costs_current + costs_prior

        if costs_total > revenue:
            income = 0
            next_carried = costs_total - revenue
        else:
            income = revenue - costs_total
            next_carried = 0

        tax = round_pit_amount(income * TAX_RATE)

        results.append(
            YearSettlement(
                year=year,
                revenue=revenue,
                costs_current=costs_current,
                costs_prior=costs_prior,
                costs_total=costs_total,
                income=income,
                carried_forward=next_carried,
                tax_19=tax,
                tx_count=len(txs),
                buy_count=sum(1 for t in txs if t.type == TxType.BUY),
                sell_count=sum(1 for t in txs if t.type == TxType.SELL),
                other_count=sum(1 for t in txs if t.type == TxType.OTHER),
            )
        )
        carried = next_carried

    return results


def line_impact(tx: Transaction) -> dict[str, float | str]:
    return {
        "id": tx.id or 0,
        "date": fmt_datetime(tx.date),
        "type": tx.type.label_pl,
        "asset": (tx.asset or "").upper(),
        "amount": tx.amount,
        "value_pln": tx.value_pln,
        "fee_pln": tx.fee_pln,
        "przychod": round(tx.pit_revenue(), 2),
        "koszt": round(tx.pit_cost(), 2),
        "note": tx.note,
    }
