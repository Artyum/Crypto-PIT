from __future__ import annotations

from enum import Enum


class TxType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    OTHER = "other"

    @property
    def label_pl(self) -> str:
        return {
            TxType.BUY: "Kupno",
            TxType.SELL: "Sprzedaż",
            TxType.OTHER: "Inne",
        }[self]


TYPE_ALIASES: dict[str, TxType] = {
    "kupno": TxType.BUY,
    "buy": TxType.BUY,
    "sprzedaż": TxType.SELL,
    "sprzedaz": TxType.SELL,
    "sprzedaj": TxType.SELL,
    "sell": TxType.SELL,
    "inne": TxType.OTHER,
    "other": TxType.OTHER,
}


def normalize_tx_type(raw: str | None) -> TxType:
    if raw is None or not str(raw).strip():
        return TxType.OTHER
    return TYPE_ALIASES.get(str(raw).strip().lower(), TxType.OTHER)
