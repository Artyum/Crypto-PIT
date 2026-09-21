from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from crypto_pit.datetime_fmt import parse_naive
from crypto_pit.domain.enums import normalize_tx_type
from crypto_pit.domain.models import Holding, Transaction

TX_COLUMNS = [
    "Data",
    "Typ",
    "Walor",
    "Ilość",
    "Wartość PLN",
    "Prowizja PLN",
    "Waluta",
    "Kurs",
    "Cena",
    "Cena PLN",
    "Prowizja (walor)",
    "Wartość (waluta)",
    "Ilość (walor)",
    "Prowizja (waluta)",
    "Ilość końcowa",
    "Giełda",
    "Uwagi",
    "Zatwierdzone",
]

HOLDINGS_COLUMNS = ["Coin ID", "Symbol", "Ilość", "Lokalizacja"]

TX_CSV = "transactions.csv"
HOLDINGS_CSV = "holdings.csv"

_WS_RE = re.compile(r"[\s\u00a0\u202f\u2007\u2009\u2008\u200a]+")


@dataclass
class BackupData:
    transactions: list[Transaction]
    holdings: list[Holding]


def _fmt_num(value: float, decimals: int = 8) -> str:
    text = f"{value:.{decimals}f}".rstrip("0").rstrip(".")
    if text in {"", "-"}:
        text = "0"
    return text.replace(".", ",")


def _clean_amount(val: object) -> float:
    if val is None:
        return 0.0
    s = str(val).strip()
    if not s or s.lower() in {"nan", "none"}:
        return 0.0
    s = _WS_RE.sub("", s)
    negative = s.startswith(("-", "−"))
    s = s.replace("-", "").replace("−", "").replace(",", ".")
    try:
        num = float(s)
    except ValueError:
        return 0.0
    return -num if negative else num


def _parse_date(raw: object) -> datetime | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.lower() == "nan":
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return parse_naive(s, fmt)
        except ValueError:
            continue
    return None


def _cell(row: dict[str, str], key: str) -> str:
    val = row.get(key)
    return str(val).strip() if val is not None else ""


def _opt_float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    raw = _cell(row, key)
    return _clean_amount(raw) if raw else default


def _norm_row(raw: dict[str | None, str | None]) -> dict[str, str]:
    return {(k or "").strip(): (v or "") for k, v in raw.items()}


def _raise_row_errors(label: str, errors: list[str]) -> None:
    if not errors:
        return
    preview = "; ".join(errors[:5])
    more = f" (+{len(errors) - 5} kolejnych)" if len(errors) > 5 else ""
    raise ValueError(f"Błędy w {label}: {preview}{more}")


def _require_columns(cols: list[str], required: tuple[str, ...], label: str) -> None:
    missing = [c for c in required if c not in cols]
    if missing:
        raise ValueError(
            f"Brak wymaganych kolumn ({label}): {', '.join(missing)}. "
            f"Znaleziono: {cols}"
        )


def _write_csv(columns: list[str], rows: list[dict[str, str]]) -> str:
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=columns, delimiter=";")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def _read_csv(text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if not reader.fieldnames:
        raise ValueError("Plik CSV nie zawiera nagłówka.")
    cols = [c.strip() for c in reader.fieldnames if c]
    rows = [_norm_row(raw) for raw in reader]
    rows = [r for r in rows if any(v.strip() for v in r.values())]
    return cols, rows


def _transactions_csv(transactions: list[Transaction]) -> str:
    rows = [
        {
            "Data": tx.date.isoformat(timespec="minutes"),
            "Typ": tx.type.label_pl,
            "Walor": (tx.asset or "").upper(),
            "Ilość": _fmt_num(tx.amount),
            "Wartość PLN": _fmt_num(tx.value_pln, 2),
            "Prowizja PLN": _fmt_num(tx.fee_pln, 2),
            "Waluta": tx.currency or "PLN",
            "Kurs": _fmt_num(tx.curr_to_pln, 6),
            "Cena": _fmt_num(tx.price, 6),
            "Cena PLN": _fmt_num(tx.price_pln),
            "Prowizja (walor)": _fmt_num(tx.fee_coin),
            "Wartość (waluta)": _fmt_num(tx.value),
            "Ilość (walor)": _fmt_num(tx.coin_amount),
            "Prowizja (waluta)": _fmt_num(tx.fee, 2),
            "Ilość końcowa": _fmt_num(tx.final_coin),
            "Giełda": tx.exchange,
            "Uwagi": tx.note.replace("\n", " | "),
            "Zatwierdzone": "1" if tx.confirmed else "0",
        }
        for tx in sorted(transactions, key=lambda t: (t.date, t.id or 0))
    ]
    return _write_csv(TX_COLUMNS, rows)


def _holdings_csv(holdings: list[Holding]) -> str:
    rows = [
        {
            "Coin ID": h.coin_id,
            "Symbol": h.symbol,
            "Ilość": _fmt_num(h.amount),
            "Lokalizacja": h.location,
        }
        for h in sorted(
            holdings,
            key=lambda x: (x.symbol.lower(), x.location.lower(), x.id or 0),
        )
    ]
    return _write_csv(HOLDINGS_COLUMNS, rows)


def _parse_transactions(text: str) -> list[Transaction]:
    cols, rows = _read_csv(text)
    _require_columns(cols, ("Data", "Typ", "Wartość PLN"), "transakcje")

    results: list[Transaction] = []
    errors: list[str] = []
    for i, row in enumerate(rows, start=2):
        try:
            dt = _parse_date(_cell(row, "Data"))
            if dt is None:
                raise ValueError("niepoprawna data")

            amount = abs(_opt_float(row, "Ilość"))
            value_pln = abs(_opt_float(row, "Wartość PLN"))
            fee_pln = abs(_opt_float(row, "Prowizja PLN"))
            price = _opt_float(row, "Cena")
            price_pln = _opt_float(row, "Cena PLN", default=price)
            fee_coin = _opt_float(row, "Prowizja (walor)")
            exchange = _cell(row, "Giełda")
            note = _cell(row, "Uwagi").replace(" | ", "\n")

            if price <= 0 and amount > 0 and value_pln > 0:
                price = value_pln / amount
                if price_pln <= 0:
                    price_pln = price
            if fee_coin <= 0 and fee_pln > 0 and price > 0:
                fee_coin = fee_pln / price
            if not exchange and note:
                exchange = note.splitlines()[0].strip()

            results.append(
                Transaction(
                    date=dt,
                    type=normalize_tx_type(_cell(row, "Typ")),
                    asset=_cell(row, "Walor"),
                    amount=amount,
                    value_pln=value_pln,
                    fee_pln=fee_pln,
                    exchange=exchange,
                    note=note,
                    currency=_cell(row, "Waluta") or "PLN",
                    value=_opt_float(row, "Wartość (waluta)", default=value_pln),
                    curr_to_pln=_opt_float(row, "Kurs", default=1.0) or 1.0,
                    coin_amount=_opt_float(row, "Ilość (walor)", default=amount),
                    price=price,
                    price_pln=price_pln,
                    fee_coin=fee_coin,
                    fee=_opt_float(row, "Prowizja (waluta)", default=fee_pln),
                    final_coin=_opt_float(row, "Ilość końcowa", default=amount),
                    confirmed=_cell(row, "Zatwierdzone").lower()
                    in ("1", "true", "tak", "yes", "x"),
                )
            )
        except (ValueError, TypeError, KeyError) as exc:
            errors.append(f"wiersz {i}: {exc}")

    _raise_row_errors("transakcje", errors)
    return results


def _parse_holdings(text: str) -> list[Holding]:
    cols, rows = _read_csv(text)
    _require_columns(cols, ("Coin ID", "Symbol", "Ilość"), "portfel")

    results: list[Holding] = []
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for i, row in enumerate(rows, start=2):
        try:
            coin_id = _cell(row, "Coin ID")
            symbol = _cell(row, "Symbol")
            location = _cell(row, "Lokalizacja") or "Nieokreślone"
            if not coin_id:
                raise ValueError("brak Coin ID")
            if not symbol:
                raise ValueError("brak Symbol")
            key = (coin_id, location)
            if key in seen:
                raise ValueError(f"duplikat pozycji ({coin_id}, {location})")
            seen.add(key)
            results.append(
                Holding(
                    coin_id=coin_id,
                    symbol=symbol,
                    amount=abs(_opt_float(row, "Ilość")),
                    location=location,
                )
            )
        except (ValueError, TypeError, KeyError) as exc:
            errors.append(f"wiersz {i}: {exc}")

    _raise_row_errors("portfel", errors)
    return results


def export_backup(
    path: Path | str,
    transactions: list[Transaction],
    holdings: list[Holding],
) -> None:
    path = Path(path)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(TX_CSV, _transactions_csv(transactions))
        zf.writestr(HOLDINGS_CSV, _holdings_csv(holdings))


def parse_backup(path: Path | str) -> BackupData:
    path = Path(path)
    if not zipfile.is_zipfile(path):
        raise ValueError("Backup musi być plikiem ZIP (transakcje + portfel).")

    with zipfile.ZipFile(path, "r") as zf:
        names = {n.lower(): n for n in zf.namelist()}
        tx_name = names.get(TX_CSV)
        h_name = names.get(HOLDINGS_CSV)
        if tx_name is None or h_name is None:
            raise ValueError(f"Archiwum musi zawierać {TX_CSV} i {HOLDINGS_CSV}.")
        return BackupData(
            transactions=_parse_transactions(zf.read(tx_name).decode("utf-8-sig")),
            holdings=_parse_holdings(zf.read(h_name).decode("utf-8-sig")),
        )
