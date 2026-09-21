from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from crypto_pit.domain.enums import TxType

_PRICE_DECIMALS = 6
_COIN_DECIMALS = 8


def _rprice(v: float) -> float:
    return round(v, _PRICE_DECIMALS)


def _rcoin(v: float) -> float:
    return round(v, _COIN_DECIMALS)


def _pack(
    *,
    value: float,
    fee: float,
    fee_coin: float,
    coin_amount: float,
    final_coin: float,
    price: float,
) -> dict[str, float]:
    return {
        "value": value,
        "fee": fee,
        "fee_coin": fee_coin,
        "coin_amount": coin_amount,
        "final_coin": final_coin,
        "price": price,
    }


@dataclass(frozen=True)
class CalcProfile:
    id: str
    input_fields: tuple[str, ...]
    compute: Callable[..., dict[str, float]]
    value_label: str | None = None
    value_hint: str | None = None


def _fee_final_coin(*, value: float, fee: float, final_coin: float) -> dict[str, float]:
    """Buy Binance/OKX/Kraken/Coinbase: price = (value - fee) / final_coin."""
    net = value - fee
    if net <= 0 or final_coin <= 0:
        raise ValueError("Wartość po prowizji i finalna ilość muszą być > 0")
    price = _rprice(net / final_coin)
    fee_coin = _rcoin(fee / price) if price else 0.0
    return _pack(
        value=value,
        fee=fee,
        fee_coin=fee_coin,
        coin_amount=_rcoin(final_coin + fee_coin),
        final_coin=final_coin,
        price=price,
    )


def _coin_amount_fee_coin(
    *, value: float, coin_amount: float, fee_coin: float
) -> dict[str, float]:
    """Buy Zonda: price = value / coin_amount."""
    if coin_amount <= 0 or fee_coin < 0:
        raise ValueError("Nieprawidłowa ilość waloru lub prowizja")
    price = _rprice(value / coin_amount)
    final_coin = _rcoin(coin_amount - fee_coin)
    if final_coin <= 0:
        raise ValueError("Finalna ilość waloru musi być większa od zera")
    return _pack(
        value=value,
        fee=fee_coin * price,
        fee_coin=fee_coin,
        coin_amount=coin_amount,
        final_coin=final_coin,
        price=price,
    )


def _fee_coin_final_coin(
    *, value: float, fee_coin: float, final_coin: float
) -> dict[str, float]:
    """Buy Kanga: coin_amount = final_coin + fee_coin; price = value / coin_amount."""
    if fee_coin < 0 or final_coin <= 0:
        raise ValueError("Nieprawidłowa prowizja lub finalna ilość")
    coin_amount = _rcoin(final_coin + fee_coin)
    price = _rprice(value / coin_amount)
    return _pack(
        value=value,
        fee=fee_coin * price,
        fee_coin=fee_coin,
        coin_amount=coin_amount,
        final_coin=final_coin,
        price=price,
    )


def _coin_amount_fee(
    *, value: float, coin_amount: float, fee: float
) -> dict[str, float]:
    """Sell: price = value / coin_amount."""
    if coin_amount <= 0 or fee < 0:
        raise ValueError("Nieprawidłowa ilość waloru lub prowizja")
    price = _rprice(value / coin_amount)
    fee_coin = _rcoin(fee / price) if price else 0.0
    final_coin = _rcoin(coin_amount - fee_coin)
    if final_coin <= 0:
        raise ValueError("Finalna ilość waloru musi być większa od zera")
    return _pack(
        value=value,
        fee=fee,
        fee_coin=fee_coin,
        coin_amount=coin_amount,
        final_coin=final_coin,
        price=price,
    )


PROFILES: Final[dict[str, CalcProfile]] = {
    "fee_final_coin": CalcProfile(
        "fee_final_coin", ("final_coin", "fee"), _fee_final_coin
    ),
    "coin_amount_fee_coin": CalcProfile(
        "coin_amount_fee_coin", ("coin_amount", "fee_coin"), _coin_amount_fee_coin
    ),
    "fee_coin_final_coin": CalcProfile(
        "fee_coin_final_coin", ("final_coin", "fee_coin"), _fee_coin_final_coin
    ),
    "coin_amount_fee": CalcProfile(
        "coin_amount_fee",
        ("coin_amount", "fee"),
        _coin_amount_fee,
        "Wartość sprzedaży brutto",
        "Kwota uzyskana ze sprzedaży przed potrąceniem prowizji.",
    ),
}

EXCHANGES: Final[tuple[str, ...]] = (
    "Binance",
    "Coinbase",
    "Kanga",
    "Kraken",
    "OKX",
    "Zonda",
)

_BINANCE_LIKE = ("binance", "okx", "kraken", "coinbase")
_REGISTRY: Final[dict[tuple[str, TxType], str]] = {
    **{(ex, TxType.BUY): "fee_final_coin" for ex in _BINANCE_LIKE},
    **{(ex, TxType.SELL): "coin_amount_fee" for ex in (*_BINANCE_LIKE, "zonda")},
    ("zonda", TxType.BUY): "coin_amount_fee_coin",
    ("kanga", TxType.BUY): "fee_coin_final_coin",
}


def normalize_exchange(name: str) -> str:
    return name.strip().lower()


def get_profile(exchange: str, tx_type: TxType) -> CalcProfile:
    profile_id = _REGISTRY.get((normalize_exchange(exchange), tx_type))
    if profile_id is None:
        raise KeyError(
            f"Brak profilu kalkulacji dla giełdy {exchange!r} i typu {tx_type.value}"
        )
    return PROFILES[profile_id]


def has_profile(exchange: str, tx_type: TxType) -> bool:
    return (normalize_exchange(exchange), tx_type) in _REGISTRY
