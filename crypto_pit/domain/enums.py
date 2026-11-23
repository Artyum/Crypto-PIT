from __future__ import annotations

from enum import StrEnum


class TxType(StrEnum):
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
        raise ValueError("brak typu transakcji")
    key = str(raw).strip().lower()
    try:
        return TYPE_ALIASES[key]
    except KeyError as exc:
        raise ValueError(f"nieznany typ transakcji: {raw}") from exc
