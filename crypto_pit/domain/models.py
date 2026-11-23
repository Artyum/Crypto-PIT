from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from crypto_pit.domain.enums import TxType
from crypto_pit.domain.money import currency_code, parse_decimal


def _non_negative(value: object, name: str) -> Decimal:
    number = parse_decimal(value)
    if number < 0:
        raise ValueError(f"{name} nie może być ujemne")
    return number


def _positive(value: object, name: str) -> Decimal:
    number = parse_decimal(value)
    if number <= 0:
        raise ValueError(f"{name} musi być większe od zera")
    return number


def _currency(value: str) -> str:
    if not value.strip():
        return "PLN"
    return currency_code(value)


@dataclass
class Transaction:
    date: datetime
    type: TxType
    asset: str
    amount: Decimal
    value_pln: Decimal
    fee_pln: Decimal
    exchange: str = ""
    note: str = ""
    currency: str = "PLN"
    value: Decimal = Decimal(0)
    curr_to_pln: Decimal = Decimal(1)
    coin_amount: Decimal = Decimal(0)
    price: Decimal = Decimal(0)
    price_pln: Decimal = Decimal(0)
    fee_coin: Decimal = Decimal(0)
    fee: Decimal = Decimal(0)
    final_coin: Decimal = Decimal(0)
    confirmed: bool = False
    nbp_date: date | None = None
    nbp_table: str = ""
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        self.amount = _non_negative(self.amount, "Ilość")
        self.value_pln = _non_negative(self.value_pln, "Wartość PLN")
        self.fee_pln = _non_negative(self.fee_pln, "Prowizja PLN")
        self.value = _non_negative(self.value, "Wartość")
        self.curr_to_pln = _positive(self.curr_to_pln, "Kurs")
        self.coin_amount = _non_negative(self.coin_amount, "Ilość waloru")
        self.price = _non_negative(self.price, "Cena")
        self.price_pln = _non_negative(self.price_pln, "Cena PLN")
        self.fee_coin = _non_negative(self.fee_coin, "Prowizja w walorze")
        self.fee = _non_negative(self.fee, "Prowizja")
        self.final_coin = _non_negative(self.final_coin, "Finalna ilość")
        self.currency = _currency(self.currency)
        self.asset = self.asset.strip()
        self.exchange = self.exchange.strip()
        self.note = self.note
        self.nbp_table = self.nbp_table.strip()

    @property
    def year(self) -> int:
        return self.date.year

    def pit_revenue(self) -> Decimal:
        if self.type == TxType.SELL:
            return self.value_pln
        return Decimal(0)

    def pit_cost(self) -> Decimal:
        if self.type == TxType.BUY:
            return self.value_pln
        if self.type == TxType.SELL:
            return self.fee_pln
        return Decimal(0)


@dataclass
class YearSettlement:
    year: int
    revenue: int
    costs_current: int
    costs_prior: int
    costs_total: int
    income: int
    carried_forward: int
    tax_19: int
    tx_count: int
    buy_count: int
    sell_count: int
    other_count: int

    def pit_fields(self) -> dict[str, int]:
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
    amount: Decimal
    location: str
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        self.coin_id = self.coin_id.strip()
        self.symbol = self.symbol.strip()
        self.location = self.location.strip()
        self.amount = _non_negative(self.amount, "Ilość")
        if not self.coin_id:
            raise ValueError("brak Coin ID")
        if not self.symbol:
            raise ValueError("brak symbolu")
        if not self.location:
            raise ValueError("brak lokalizacji")
