from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from crypto_pit.domain.enums import TxType


@dataclass
class Transaction:
    date: datetime
    type: TxType
    asset: str
    amount: float
    value_pln: float
    fee_pln: float
    exchange: str = ""
    note: str = ""
    currency: str = "PLN"
    value: float = 0.0
    curr_to_pln: float = 1.0
    coin_amount: float = 0.0
    price: float = 0.0
    price_pln: float = 0.0
    fee_coin: float = 0.0
    fee: float = 0.0
    final_coin: float = 0.0
    confirmed: bool = False
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def year(self) -> int:
        return self.date.year

    def pit_revenue(self) -> float:
        if self.type == TxType.SELL:
            return abs(self.value_pln)
        return 0.0

    def pit_cost(self) -> float:
        if self.type == TxType.BUY:
            return abs(self.value_pln)
        if self.type == TxType.SELL:
            return abs(self.fee_pln)
        return 0.0


@dataclass
class YearSettlement:
    year: int
    revenue: float
    costs_current: float
    costs_prior: float
    costs_total: float
    income: float
    carried_forward: float
    tax_19: float
    tx_count: int
    buy_count: int
    sell_count: int
    other_count: int

    def pit_fields(self) -> dict[str, float]:
        return {
            "przychod": self.revenue,
            "koszty_biezace": self.costs_current,
            "koszty_lat_ubieglych": self.costs_prior,
            "dochod": self.income,
            "koszty_do_przeniesienia": self.carried_forward,
            "podatek_19": self.tax_19,
        }


@dataclass
class Holding:
    coin_id: str
    symbol: str
    amount: float
    location: str
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None
