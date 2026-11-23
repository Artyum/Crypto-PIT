from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from crypto_pit.datetime_fmt import parse_naive
from crypto_pit.domain.enums import normalize_tx_type
from crypto_pit.domain.models import Holding, Transaction
from crypto_pit.domain.money import DecimalError, parse_decimal
from crypto_pit.infrastructure.database import DEFAULT_HOLDING_LOCATION
from crypto_pit.services.csv_text import format_decimal

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
    "Data kursu NBP",
    "Tabela NBP",
]

HOLDINGS_COLUMNS = ["Coin ID", "Symbol", "Ilość", "Lokalizacja"]

TX_CSV = "transactions.csv"
HOLDINGS_CSV = "holdings.csv"
MAX_BACKUP_BYTES = 32 * 1024 * 1024
MAX_ENTRY_BYTES = 32 * 1024 * 1024
MAX_ROWS = 200_000


@dataclass
class BackupData:
    transactions: list[Transaction]
    holdings: list[Holding]


def _fmt_num(value: Decimal, decimals: int | None = None) -> str:
    return format_decimal(value, decimals)


def _parse_date(raw: object) -> datetime | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.lower() == "nan":
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return parse_naive(text, fmt)
        except ValueError:
            continue
    return None


def _parse_iso_date(raw: str) -> date | None:
    if not raw:
        return None
    parsed = _parse_date(raw)
    if parsed is None:
        raise ValueError(f"niepoprawna data kursu NBP: {raw}")
    return parsed.date()


def _cell(row: dict[str, str], key: str) -> str:
    value = row.get(key)
    return str(value).strip() if value is not None else ""


def _has_cell(row: dict[str, str], key: str) -> bool:
    return key in row and bool(_cell(row, key))


def _required_decimal(row: dict[str, str], key: str) -> Decimal:
    if not _has_cell(row, key):
        raise ValueError(f"brak wartości: {key}")
    return _non_negative(row, key, parse_decimal(_cell(row, key)))


def _optional_decimal(row: dict[str, str], key: str, default: Decimal) -> Decimal:
    if not _has_cell(row, key):
        return default
    return _non_negative(row, key, parse_decimal(_cell(row, key)))


def _positive_decimal(row: dict[str, str], key: str, default: Decimal) -> Decimal:
    number = _optional_decimal(row, key, default)
    if number <= 0:
        raise ValueError(f"wartość musi być większa od zera: {key}")
    return number


def _non_negative(row: dict[str, str], key: str, number: Decimal) -> Decimal:
    if number < 0:
        raise ValueError(f"ujemna wartość ({key}): {_cell(row, key)}")
    return number


def _norm_row(raw: dict[str | None, str | None]) -> dict[str, str]:
    return {(key or "").strip(): (value or "") for key, value in raw.items()}


def _raise_row_errors(label: str, errors: list[str]) -> None:
    if not errors:
        return
    preview = "; ".join(errors[:5])
    more = f" (+{len(errors) - 5} kolejnych)" if len(errors) > 5 else ""
    raise ValueError(f"Błędy w {label}: {preview}{more}")


def _require_columns(cols: list[str], required: tuple[str, ...], label: str) -> None:
    missing = [column for column in required if column not in cols]
    if missing:
        raise ValueError(
            f"Brak wymaganych kolumn ({label}): {', '.join(missing)}. "
            f"Znaleziono: {cols}"
        )


def _write_csv(columns: list[str], rows: list[dict[str, str]]) -> str:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=columns, delimiter=";")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def _read_csv(text: str) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    if not reader.fieldnames:
        raise ValueError("Plik CSV nie zawiera nagłówka.")
    columns = [column.strip() for column in reader.fieldnames if column]
    rows = [_norm_row(raw) for raw in reader]
    rows = [row for row in rows if any(value.strip() for value in row.values())]
    if len(rows) > MAX_ROWS:
        raise ValueError(f"Plik CSV przekracza limit {MAX_ROWS} wierszy.")
    return columns, rows


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
            "Data kursu NBP": tx.nbp_date.isoformat() if tx.nbp_date else "",
            "Tabela NBP": tx.nbp_table,
        }
        for tx in sorted(transactions, key=lambda item: (item.date, item.id or 0))
    ]
    return _write_csv(TX_COLUMNS, rows)


def _holdings_csv(holdings: list[Holding]) -> str:
    rows = [
        {
            "Coin ID": holding.coin_id,
            "Symbol": holding.symbol,
            "Ilość": _fmt_num(holding.amount),
            "Lokalizacja": holding.location,
        }
        for holding in sorted(
            holdings,
            key=lambda item: (item.symbol.lower(), item.location.lower(), item.id or 0),
        )
    ]
    return _write_csv(HOLDINGS_COLUMNS, rows)


def _parse_transactions(text: str) -> list[Transaction]:
    columns, rows = _read_csv(text)
    _require_columns(columns, ("Data", "Typ", "Wartość PLN"), "transakcje")
    results: list[Transaction] = []
    errors: list[str] = []
    for index, row in enumerate(rows, start=2):
        try:
            moment = _parse_date(_cell(row, "Data"))
            if moment is None:
                raise ValueError("niepoprawna data")
            amount = _optional_decimal(row, "Ilość", Decimal(0))
            value_pln = _required_decimal(row, "Wartość PLN")
            currency = _cell(row, "Waluta") or "PLN"
            value_default = value_pln if currency.upper() == "PLN" else None
            if value_default is None and not _has_cell(row, "Wartość (waluta)"):
                raise ValueError("brak wartości w walucie")
            value = (
                _optional_decimal(row, "Wartość (waluta)", value_default)
                if value_default is not None
                else _required_decimal(row, "Wartość (waluta)")
            )
            results.append(
                Transaction(
                    date=moment,
                    type=normalize_tx_type(_cell(row, "Typ")),
                    asset=_cell(row, "Walor"),
                    amount=amount,
                    value_pln=value_pln,
                    fee_pln=_optional_decimal(row, "Prowizja PLN", Decimal(0)),
                    exchange=_cell(row, "Giełda"),
                    note=_cell(row, "Uwagi").replace(" | ", "\n"),
                    currency=currency,
                    value=value,
                    curr_to_pln=_positive_decimal(row, "Kurs", Decimal(1)),
                    coin_amount=_optional_decimal(row, "Ilość (walor)", amount),
                    price=_optional_decimal(row, "Cena", Decimal(0)),
                    price_pln=_optional_decimal(row, "Cena PLN", Decimal(0)),
                    fee_coin=_optional_decimal(row, "Prowizja (walor)", Decimal(0)),
                    fee=_optional_decimal(row, "Prowizja (waluta)", Decimal(0)),
                    final_coin=_optional_decimal(row, "Ilość końcowa", amount),
                    confirmed=_cell(row, "Zatwierdzone").lower()
                    in ("1", "true", "tak", "yes", "x"),
                    nbp_date=_parse_iso_date(_cell(row, "Data kursu NBP")),
                    nbp_table=_cell(row, "Tabela NBP"),
                )
            )
        except (ValueError, TypeError, KeyError, DecimalError) as exc:
            errors.append(f"wiersz {index}: {exc}")
    _raise_row_errors("transakcje", errors)
    return results


def _parse_holdings(text: str) -> list[Holding]:
    columns, rows = _read_csv(text)
    _require_columns(columns, ("Coin ID", "Symbol", "Ilość"), "portfel")
    results: list[Holding] = []
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows, start=2):
        try:
            coin_id = _cell(row, "Coin ID")
            symbol = _cell(row, "Symbol")
            location = _cell(row, "Lokalizacja") or DEFAULT_HOLDING_LOCATION
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
                    amount=_required_decimal(row, "Ilość"),
                    location=location,
                )
            )
        except (ValueError, TypeError, KeyError, DecimalError) as exc:
            errors.append(f"wiersz {index}: {exc}")
    _raise_row_errors("portfel", errors)
    return results


def export_backup(
    path: Path | str,
    transactions: list[Transaction],
    holdings: list[Holding],
) -> None:
    path = Path(path)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(TX_CSV, _transactions_csv(transactions))
        archive.writestr(HOLDINGS_CSV, _holdings_csv(holdings))


def _zip_entry(names: list[str], filename: str) -> str | None:
    wanted = filename.lower()
    exact = [name for name in names if name.replace("\\", "/").lower() == wanted]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise ValueError(f"W archiwum jest więcej niż jeden plik {filename}.")
    nested = [
        name
        for name in names
        if name.replace("\\", "/").rstrip("/").lower().endswith("/" + wanted)
        and not name.endswith("/")
    ]
    if len(nested) == 1:
        return nested[0]
    if len(nested) > 1:
        raise ValueError(f"W archiwum jest więcej niż jeden plik {filename}.")
    return None


def _zip_text(archive: zipfile.ZipFile, name: str) -> str:
    info = archive.getinfo(name)
    if info.file_size > MAX_ENTRY_BYTES:
        raise ValueError(f"Plik {Path(name).name} przekracza limit rozmiaru.")
    try:
        payload = archive.read(name)
    except zipfile.BadZipFile as exc:
        raise ValueError("Backup musi być plikiem ZIP (transakcje + portfel).") from exc
    if len(payload) > MAX_ENTRY_BYTES:
        raise ValueError(f"Plik {Path(name).name} przekracza limit rozmiaru.")
    try:
        return payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Plik {Path(name).name} nie jest zapisany w UTF-8.") from exc


def parse_backup(path: Path | str) -> BackupData:
    path = Path(path)
    if path.stat().st_size > MAX_BACKUP_BYTES:
        raise ValueError("Backup przekracza limit rozmiaru.")
    if not zipfile.is_zipfile(path):
        raise ValueError("Backup musi być plikiem ZIP (transakcje + portfel).")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = archive.namelist()
            tx_name = _zip_entry(names, TX_CSV)
            holdings_name = _zip_entry(names, HOLDINGS_CSV)
            if tx_name is None or holdings_name is None:
                raise ValueError(f"Archiwum musi zawierać {TX_CSV} i {HOLDINGS_CSV}.")
            return BackupData(
                transactions=_parse_transactions(_zip_text(archive, tx_name)),
                holdings=_parse_holdings(_zip_text(archive, holdings_name)),
            )
    except zipfile.BadZipFile as exc:
        raise ValueError("Backup musi być plikiem ZIP (transakcje + portfel).") from exc
