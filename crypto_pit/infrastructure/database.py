from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from crypto_pit.config import DEFAULT_DB_PATH
from crypto_pit.datetime_fmt import local_now
from crypto_pit.domain.enums import TxType
from crypto_pit.domain.models import Holding, Transaction
from crypto_pit.domain.money import (
    decimal_from_legacy_real,
    decimal_to_text,
    parse_decimal,
)

SCHEMA_VERSION = 1
DEFAULT_HOLDING_LOCATION = "Nieokreślone"

_TX_NUMERIC = (
    "amount",
    "value_pln",
    "fee_pln",
    "value",
    "curr_to_pln",
    "coin_amount",
    "price",
    "price_pln",
    "fee_coin",
    "fee",
    "final_coin",
)

_LEGACY_TX_COLUMNS = frozenset(
    {
        "source",
        "import_hash",
        "classification_override",
        "raw_json",
        "calc_variant",
    }
)

_TRANSACTIONS_STATEMENTS = (
    """
    CREATE TABLE transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        type TEXT NOT NULL,
        asset TEXT NOT NULL DEFAULT '',
        amount TEXT NOT NULL DEFAULT '0',
        value_pln TEXT NOT NULL DEFAULT '0',
        fee_pln TEXT NOT NULL DEFAULT '0',
        exchange TEXT NOT NULL DEFAULT '',
        note TEXT NOT NULL DEFAULT '',
        currency TEXT NOT NULL DEFAULT 'PLN',
        value TEXT NOT NULL DEFAULT '0',
        curr_to_pln TEXT NOT NULL DEFAULT '1',
        coin_amount TEXT NOT NULL DEFAULT '0',
        price TEXT NOT NULL DEFAULT '0',
        price_pln TEXT NOT NULL DEFAULT '0',
        fee_coin TEXT NOT NULL DEFAULT '0',
        fee TEXT NOT NULL DEFAULT '0',
        final_coin TEXT NOT NULL DEFAULT '0',
        confirmed INTEGER NOT NULL DEFAULT 0,
        nbp_date TEXT,
        nbp_table TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX idx_transactions_date ON transactions(date)",
    "CREATE INDEX idx_transactions_type ON transactions(type)",
)

_HOLDINGS_STATEMENT = """
CREATE TABLE holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coin_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    amount TEXT NOT NULL DEFAULT '0',
    location TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(coin_id, location)
)
"""


def _now() -> str:
    return local_now().isoformat(timespec="seconds")


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _table_columns(conn: sqlite3.Connection, table: str) -> dict[str, str]:
    return {
        str(row[1]): str(row[2] or "")
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _stored_decimal(value: object, default: Decimal = Decimal(0)) -> Decimal:
    if value is None:
        return default
    if isinstance(value, float):
        return decimal_from_legacy_real(value)
    return parse_decimal(value)


def _row_decimal(row: sqlite3.Row, key: str, default: Decimal = Decimal(0)) -> Decimal:
    try:
        value = row[key]
    except (IndexError, KeyError):
        return default
    return _stored_decimal(value, default)


def _row_str(row: sqlite3.Row, key: str, default: str = "") -> str:
    try:
        value = row[key]
    except (IndexError, KeyError):
        return default
    if value is None:
        return default
    return str(value)


def _row_date(row: sqlite3.Row, key: str) -> date | None:
    raw = _row_str(row, key)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _row_bool(row: sqlite3.Row, key: str, default: bool = False) -> bool:
    try:
        value = row[key]
    except (IndexError, KeyError):
        return default
    if value is None:
        return default
    return bool(value)


def _row_to_holding(row: sqlite3.Row) -> Holding:
    return Holding(
        id=row["id"],
        coin_id=row["coin_id"],
        symbol=row["symbol"] or "",
        amount=_row_decimal(row, "amount"),
        location=row["location"] or "",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _tx_fields(tx: Transaction) -> tuple[object, ...]:
    return (
        tx.date.isoformat(timespec="minutes"),
        tx.type.value,
        tx.asset,
        decimal_to_text(tx.amount),
        decimal_to_text(tx.value_pln),
        decimal_to_text(tx.fee_pln),
        tx.exchange,
        tx.note,
        tx.currency,
        decimal_to_text(tx.value),
        decimal_to_text(tx.curr_to_pln),
        decimal_to_text(tx.coin_amount),
        decimal_to_text(tx.price),
        decimal_to_text(tx.price_pln),
        decimal_to_text(tx.fee_coin),
        decimal_to_text(tx.fee),
        decimal_to_text(tx.final_coin),
        1 if tx.confirmed else 0,
        tx.nbp_date.isoformat() if tx.nbp_date else None,
        tx.nbp_table or None,
    )


def _tx_insert_params(tx: Transaction, now: str) -> tuple[object, ...]:
    return (*_tx_fields(tx), now, now)


def _row_to_tx(row: sqlite3.Row) -> Transaction:
    return Transaction(
        id=row["id"],
        date=_parse_dt(row["date"]),
        type=TxType(row["type"]),
        asset=row["asset"] or "",
        amount=_row_decimal(row, "amount"),
        value_pln=_row_decimal(row, "value_pln"),
        fee_pln=_row_decimal(row, "fee_pln"),
        exchange=row["exchange"] or "",
        note=row["note"] or "",
        currency=_row_str(row, "currency", "PLN") or "PLN",
        value=_row_decimal(row, "value"),
        curr_to_pln=_row_decimal(row, "curr_to_pln", Decimal(1)),
        coin_amount=_row_decimal(row, "coin_amount"),
        price=_row_decimal(row, "price"),
        price_pln=_row_decimal(row, "price_pln"),
        fee_coin=_row_decimal(row, "fee_coin"),
        fee=_row_decimal(row, "fee"),
        final_coin=_row_decimal(row, "final_coin"),
        confirmed=_row_bool(row, "confirmed"),
        nbp_date=_row_date(row, "nbp_date"),
        nbp_table=_row_str(row, "nbp_table"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class Database:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, timeout=5, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.isolation_level = None
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA busy_timeout = 5000")
        with suppress(sqlite3.Error):
            self._conn.execute("PRAGMA journal_mode = WAL")
        self._migrate()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        else:
            self._conn.execute("COMMIT")

    def _mutate(self, operation: Callable[[], None]) -> None:
        with self._lock, self._transaction():
            operation()

    def _migrate(self) -> None:
        version = int(self._conn.execute("PRAGMA user_version").fetchone()[0])
        if version == SCHEMA_VERSION:
            return
        if version > SCHEMA_VERSION:
            raise RuntimeError(f"Baza ma nowszą wersję schematu: {version}")
        if version != 0:
            raise RuntimeError(f"Nieobsługiwana wersja schematu: {version}")
        if not _table_exists(self._conn, "transactions"):
            self._create_schema()
            self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            return
        backup_path = self._write_backup()
        with self._transaction():
            self._migrate_transactions()
            self._migrate_holdings()
            self._conn.execute("DROP TABLE IF EXISTS filed_declarations")
            self._conn.execute("DROP TABLE IF EXISTS import_batches")
            self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        check = self._conn.execute("PRAGMA integrity_check").fetchone()
        if check is None or str(check[0]) != "ok":
            raise RuntimeError(
                f"Baza nie przeszła kontroli integralności: {backup_path}"
            )
        backup_path.unlink(missing_ok=True)

    def _create_schema(self) -> None:
        for statement in _TRANSACTIONS_STATEMENTS:
            self._conn.execute(statement)
        self._conn.execute(_HOLDINGS_STATEMENT)

    def _write_backup(self) -> Path:
        backup_path = self.path.with_name(self.path.name + ".premigration")
        if backup_path.exists():
            backup_path.unlink()
        backup = sqlite3.connect(backup_path)
        try:
            self._conn.backup(backup)
        finally:
            backup.close()
        return backup_path

    def _migrate_transactions(self) -> None:
        columns = _table_columns(self._conn, "transactions")
        if not self._transactions_need_rebuild(columns):
            return
        rows = self._conn.execute("SELECT * FROM transactions").fetchall()
        self._conn.execute("DROP INDEX IF EXISTS idx_transactions_import_hash")
        self._conn.execute("DROP INDEX IF EXISTS idx_transactions_date")
        self._conn.execute("DROP INDEX IF EXISTS idx_transactions_type")
        self._conn.execute("ALTER TABLE transactions RENAME TO transactions_legacy")
        for statement in _TRANSACTIONS_STATEMENTS:
            self._conn.execute(statement)
        for row in rows:
            self._conn.execute(
                """
                INSERT INTO transactions (
                    date, type, asset, amount, value_pln, fee_pln, exchange, note,
                    currency, value, curr_to_pln, coin_amount, price, price_pln,
                    fee_coin, fee, final_coin, confirmed, nbp_date, nbp_table,
                    created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                self._legacy_tx_params(row, columns),
            )
        self._conn.execute("DROP TABLE transactions_legacy")

    def _transactions_need_rebuild(self, columns: dict[str, str]) -> bool:
        if columns.keys() & _LEGACY_TX_COLUMNS:
            return True
        required = {
            "confirmed",
            "nbp_date",
            "nbp_table",
            "currency",
            "value",
            "curr_to_pln",
            "coin_amount",
            "price",
            "price_pln",
            "fee_coin",
            "fee",
            "final_coin",
        }
        if not required <= columns.keys():
            return True
        return any("TEXT" not in columns[name].upper() for name in _TX_NUMERIC)

    def _legacy_tx_params(
        self, row: sqlite3.Row, columns: dict[str, str]
    ) -> tuple[object, ...]:
        def text(name: str, default: str = "") -> str:
            if name not in columns or row[name] is None:
                return default
            return str(row[name])

        def number(name: str, default: str = "0") -> str:
            if name not in columns or row[name] is None:
                return default
            return decimal_to_text(_stored_decimal(row[name]))

        confirmed = 0
        if "confirmed" in columns and row["confirmed"] is not None:
            confirmed = 1 if row["confirmed"] else 0
        nbp_date = text("nbp_date") or None
        nbp_table = text("nbp_table") or None
        return (
            text("date"),
            text("type"),
            text("asset"),
            number("amount"),
            number("value_pln"),
            number("fee_pln"),
            text("exchange"),
            text("note"),
            text("currency", "PLN") or "PLN",
            number("value"),
            number("curr_to_pln", "1"),
            number("coin_amount"),
            number("price"),
            number("price_pln"),
            number("fee_coin"),
            number("fee"),
            number("final_coin"),
            confirmed,
            nbp_date,
            nbp_table,
            text("created_at"),
            text("updated_at"),
        )

    def _migrate_holdings(self) -> None:
        if not _table_exists(self._conn, "holdings"):
            self._conn.execute(_HOLDINGS_STATEMENT)
            return
        columns = _table_columns(self._conn, "holdings")
        needs_location = "location" not in columns
        needs_text = "TEXT" not in columns.get("amount", "").upper()
        if not needs_location and not needs_text:
            return
        rows = self._conn.execute("SELECT * FROM holdings").fetchall()
        self._conn.execute("ALTER TABLE holdings RENAME TO holdings_legacy")
        self._conn.execute(_HOLDINGS_STATEMENT)
        for row in rows:
            location = DEFAULT_HOLDING_LOCATION
            if "location" in columns and row["location"]:
                location = str(row["location"])
            self._conn.execute(
                """
                INSERT INTO holdings (
                    id, coin_id, symbol, amount, location, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["coin_id"],
                    row["symbol"],
                    decimal_to_text(_stored_decimal(row["amount"])),
                    location,
                    row["created_at"],
                    row["updated_at"],
                ),
            )
        self._conn.execute("DROP TABLE holdings_legacy")

    def list_transactions(
        self,
        year: int | None = None,
        tx_type: TxType | None = None,
    ) -> list[Transaction]:
        clauses: list[str] = []
        params: list[object] = []
        if year is not None:
            clauses.append("substr(date, 1, 4) = ?")
            params.append(str(year))
        if tx_type is not None:
            clauses.append("type = ?")
            params.append(tx_type.value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            cur = self._conn.execute(
                f"SELECT * FROM transactions {where} ORDER BY date ASC, id ASC",
                params,
            )
            return [_row_to_tx(row) for row in cur.fetchall()]

    def get_transaction(self, tx_id: int) -> Transaction | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM transactions WHERE id = ?", (tx_id,)
            ).fetchone()
        return _row_to_tx(row) if row else None

    def insert_transaction(self, tx: Transaction) -> int:
        now = _now()
        row_id: int | None = None

        def operation() -> None:
            nonlocal row_id
            cur = self._conn.execute(
                """
                INSERT INTO transactions (
                    date, type, asset, amount, value_pln, fee_pln, exchange, note,
                    currency, value, curr_to_pln, coin_amount, price, price_pln,
                    fee_coin, fee, final_coin, confirmed, nbp_date, nbp_table,
                    created_at, updated_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                _tx_insert_params(tx, now),
            )
            if cur.lastrowid is None:
                raise RuntimeError("INSERT nie zwrócił id transakcji")
            row_id = int(cur.lastrowid)

        self._mutate(operation)
        if row_id is None:
            raise RuntimeError("INSERT nie zwrócił id transakcji")
        return row_id

    def update_transaction(self, tx: Transaction) -> None:
        if tx.id is None:
            raise ValueError("Brak id transakcji")

        def operation() -> None:
            self._conn.execute(
                """
                UPDATE transactions SET
                    date = ?, type = ?, asset = ?, amount = ?, value_pln = ?,
                    fee_pln = ?, exchange = ?, note = ?,
                    currency = ?, value = ?, curr_to_pln = ?, coin_amount = ?,
                    price = ?, price_pln = ?, fee_coin = ?, fee = ?,
                    final_coin = ?, confirmed = ?, nbp_date = ?, nbp_table = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (*_tx_fields(tx), _now(), tx.id),
            )

        self._mutate(operation)

    def delete_transaction(self, tx_id: int) -> None:
        def operation() -> None:
            self._conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))

        self._mutate(operation)

    def list_holdings(self) -> list[Holding]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT * FROM holdings
                ORDER BY symbol COLLATE NOCASE ASC,
                         location COLLATE NOCASE ASC,
                         id ASC
                """
            )
            return [_row_to_holding(row) for row in cur.fetchall()]

    def get_holding(self, holding_id: int) -> Holding | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM holdings WHERE id = ?", (holding_id,)
            ).fetchone()
        return _row_to_holding(row) if row else None

    def insert_holding(self, holding: Holding) -> int:
        now = _now()
        row_id: int | None = None

        def operation() -> None:
            nonlocal row_id
            cur = self._conn.execute(
                """
                INSERT INTO holdings (
                    coin_id, symbol, amount, location, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    holding.coin_id,
                    holding.symbol,
                    decimal_to_text(holding.amount),
                    holding.location,
                    now,
                    now,
                ),
            )
            if cur.lastrowid is None:
                raise RuntimeError("INSERT nie zwrócił id holdings")
            row_id = int(cur.lastrowid)

        self._mutate(operation)
        if row_id is None:
            raise RuntimeError("INSERT nie zwrócił id holdings")
        return row_id

    def update_holding(self, holding: Holding) -> None:
        if holding.id is None:
            raise ValueError("Brak id holdings")

        def operation() -> None:
            self._conn.execute(
                """
                UPDATE holdings
                SET coin_id = ?, symbol = ?, amount = ?, location = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    holding.coin_id,
                    holding.symbol,
                    decimal_to_text(holding.amount),
                    holding.location,
                    _now(),
                    holding.id,
                ),
            )

        self._mutate(operation)

    def delete_holding(self, holding_id: int) -> None:
        def operation() -> None:
            self._conn.execute("DELETE FROM holdings WHERE id = ?", (holding_id,))

        self._mutate(operation)

    def _clear_table(self, name: str) -> None:
        if name not in {"transactions", "holdings"}:
            raise ValueError(f"Niedozwolona tabela: {name}")
        self._conn.execute(f"DELETE FROM {name}")
        with suppress(sqlite3.OperationalError):
            self._conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", (name,))

    def replace_all_data(
        self,
        transactions: list[Transaction],
        holdings: list[Holding],
    ) -> tuple[int, int]:
        now = _now()

        def operation() -> None:
            self._clear_table("transactions")
            for tx in transactions:
                self._conn.execute(
                    """
                    INSERT INTO transactions (
                        date, type, asset, amount, value_pln, fee_pln, exchange, note,
                        currency, value, curr_to_pln, coin_amount, price, price_pln,
                        fee_coin, fee, final_coin, confirmed, nbp_date, nbp_table,
                        created_at, updated_at
                    ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                    """,
                    _tx_insert_params(tx, now),
                )
            self._clear_table("holdings")
            for holding in holdings:
                self._conn.execute(
                    """
                    INSERT INTO holdings (
                        coin_id, symbol, amount, location, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        holding.coin_id,
                        holding.symbol,
                        decimal_to_text(holding.amount),
                        holding.location,
                        now,
                        now,
                    ),
                )

        self._mutate(operation)
        return len(transactions), len(holdings)
