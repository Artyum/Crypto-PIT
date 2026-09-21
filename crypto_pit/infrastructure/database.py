from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from crypto_pit.config import DEFAULT_DB_PATH
from crypto_pit.datetime_fmt import local_now
from crypto_pit.domain.enums import TxType
from crypto_pit.domain.models import Holding, Transaction

_TX_KEEP_COLUMNS = (
    "id",
    "date",
    "type",
    "asset",
    "amount",
    "value_pln",
    "fee_pln",
    "exchange",
    "note",
    "currency",
    "value",
    "curr_to_pln",
    "coin_amount",
    "price",
    "price_pln",
    "fee_coin",
    "fee",
    "final_coin",
    "confirmed",
    "created_at",
    "updated_at",
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

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    type TEXT NOT NULL,
    asset TEXT NOT NULL DEFAULT '',
    amount REAL NOT NULL DEFAULT 0,
    value_pln REAL NOT NULL DEFAULT 0,
    fee_pln REAL NOT NULL DEFAULT 0,
    exchange TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    currency TEXT NOT NULL DEFAULT 'PLN',
    value REAL NOT NULL DEFAULT 0,
    curr_to_pln REAL NOT NULL DEFAULT 1,
    coin_amount REAL NOT NULL DEFAULT 0,
    price REAL NOT NULL DEFAULT 0,
    price_pln REAL NOT NULL DEFAULT 0,
    fee_coin REAL NOT NULL DEFAULT 0,
    fee REAL NOT NULL DEFAULT 0,
    final_coin REAL NOT NULL DEFAULT 0,
    confirmed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type);

CREATE TABLE IF NOT EXISTS holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coin_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    amount REAL NOT NULL DEFAULT 0,
    location TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(coin_id, location)
);
"""

DEFAULT_HOLDING_LOCATION = "Nieokreślone"


def _now() -> str:
    return local_now().isoformat(timespec="seconds")


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _row_float(row: sqlite3.Row, key: str, default: float = 0.0) -> float:
    try:
        val = row[key]
    except (IndexError, KeyError):
        return default
    if val is None:
        return default
    return float(val)


def _row_str(row: sqlite3.Row, key: str, default: str = "") -> str:
    try:
        val = row[key]
    except (IndexError, KeyError):
        return default
    if val is None:
        return default
    return str(val)


def _row_bool(row: sqlite3.Row, key: str, default: bool = False) -> bool:
    try:
        val = row[key]
    except (IndexError, KeyError):
        return default
    if val is None:
        return default
    return bool(val)


def _row_to_holding(row: sqlite3.Row) -> Holding:
    return Holding(
        id=row["id"],
        coin_id=row["coin_id"],
        symbol=row["symbol"] or "",
        amount=float(row["amount"] or 0),
        location=row["location"] or "",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_tx(row: sqlite3.Row) -> Transaction:
    return Transaction(
        id=row["id"],
        date=_parse_dt(row["date"]),
        type=TxType(row["type"]),
        asset=row["asset"] or "",
        amount=float(row["amount"] or 0),
        value_pln=float(row["value_pln"] or 0),
        fee_pln=float(row["fee_pln"] or 0),
        exchange=row["exchange"] or "",
        note=row["note"] or "",
        currency=_row_str(row, "currency", "PLN") or "PLN",
        value=_row_float(row, "value"),
        curr_to_pln=_row_float(row, "curr_to_pln", 1.0),
        coin_amount=_row_float(row, "coin_amount"),
        price=_row_float(row, "price"),
        price_pln=_row_float(row, "price_pln"),
        fee_coin=_row_float(row, "fee_coin"),
        fee=_row_float(row, "fee"),
        final_coin=_row_float(row, "final_coin"),
        confirmed=_row_bool(row, "confirmed"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class Database:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._migrate()
        self._conn.execute("DROP TABLE IF EXISTS filed_declarations")
        self._conn.execute("DROP TABLE IF EXISTS import_batches")
        self._conn.commit()

    def _migrate(self) -> None:
        tx_cols = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(transactions)").fetchall()
        }
        if tx_cols:
            if tx_cols & _LEGACY_TX_COLUMNS:
                self._rebuild_transactions_table(tx_cols)
            elif "confirmed" not in tx_cols:
                self._conn.execute(
                    "ALTER TABLE transactions ADD COLUMN confirmed "
                    "INTEGER NOT NULL DEFAULT 0"
                )

        holding_cols = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(holdings)").fetchall()
        }
        if holding_cols and "location" not in holding_cols:
            self._rebuild_holdings_table()

    def _rebuild_transactions_table(self, existing_cols: set[str]) -> None:
        insert_cols: list[str] = []
        select_parts: list[str] = []
        for col in _TX_KEEP_COLUMNS:
            if col in existing_cols:
                insert_cols.append(col)
                select_parts.append(col)
            elif col == "confirmed":
                insert_cols.append(col)
                select_parts.append("0 AS confirmed")

        self._conn.execute("DROP INDEX IF EXISTS idx_transactions_import_hash")
        self._conn.execute("ALTER TABLE transactions RENAME TO transactions_legacy")
        self._conn.executescript(
            """
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                type TEXT NOT NULL,
                asset TEXT NOT NULL DEFAULT '',
                amount REAL NOT NULL DEFAULT 0,
                value_pln REAL NOT NULL DEFAULT 0,
                fee_pln REAL NOT NULL DEFAULT 0,
                exchange TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                currency TEXT NOT NULL DEFAULT 'PLN',
                value REAL NOT NULL DEFAULT 0,
                curr_to_pln REAL NOT NULL DEFAULT 1,
                coin_amount REAL NOT NULL DEFAULT 0,
                price REAL NOT NULL DEFAULT 0,
                price_pln REAL NOT NULL DEFAULT 0,
                fee_coin REAL NOT NULL DEFAULT 0,
                fee REAL NOT NULL DEFAULT 0,
                final_coin REAL NOT NULL DEFAULT 0,
                confirmed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
            CREATE INDEX IF NOT EXISTS idx_transactions_type ON transactions(type);
            """
        )
        self._conn.execute(
            f"INSERT INTO transactions ({', '.join(insert_cols)}) "
            f"SELECT {', '.join(select_parts)} FROM transactions_legacy"
        )
        self._conn.execute("DROP TABLE transactions_legacy")

    def _rebuild_holdings_table(self) -> None:
        self._conn.execute("ALTER TABLE holdings RENAME TO holdings_legacy")
        self._conn.execute(
            """
            CREATE TABLE holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0,
                location TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(coin_id, location)
            )
            """
        )
        self._conn.execute(
            """
            INSERT INTO holdings (
                id, coin_id, symbol, amount, location, created_at, updated_at
            )
            SELECT
                id, coin_id, symbol, amount, ?, created_at, updated_at
            FROM holdings_legacy
            """,
            (DEFAULT_HOLDING_LOCATION,),
        )
        self._conn.execute("DROP TABLE holdings_legacy")

    def close(self) -> None:
        self._conn.close()

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
        cur = self._conn.execute(
            f"SELECT * FROM transactions {where} ORDER BY date ASC, id ASC",
            params,
        )
        return [_row_to_tx(r) for r in cur.fetchall()]

    def get_transaction(self, tx_id: int) -> Transaction | None:
        cur = self._conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,))
        row = cur.fetchone()
        return _row_to_tx(row) if row else None

    def insert_transaction(self, tx: Transaction) -> int:
        now = _now()
        cur = self._conn.execute(
            """
            INSERT INTO transactions (
                date, type, asset, amount, value_pln, fee_pln, exchange, note,
                currency, value, curr_to_pln, coin_amount, price, price_pln,
                fee_coin, fee, final_coin, confirmed,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tx.date.isoformat(timespec="minutes"),
                tx.type.value,
                tx.asset,
                tx.amount,
                tx.value_pln,
                tx.fee_pln,
                tx.exchange,
                tx.note,
                tx.currency,
                tx.value,
                tx.curr_to_pln,
                tx.coin_amount,
                tx.price,
                tx.price_pln,
                tx.fee_coin,
                tx.fee,
                tx.final_coin,
                1 if tx.confirmed else 0,
                now,
                now,
            ),
        )
        self._conn.commit()
        if cur.lastrowid is None:
            raise RuntimeError("INSERT nie zwrócił id transakcji")
        return int(cur.lastrowid)

    def update_transaction(self, tx: Transaction) -> None:
        if tx.id is None:
            raise ValueError("Brak id transakcji")
        self._conn.execute(
            """
            UPDATE transactions SET
                date = ?, type = ?, asset = ?, amount = ?, value_pln = ?,
                fee_pln = ?, exchange = ?, note = ?,
                currency = ?, value = ?, curr_to_pln = ?, coin_amount = ?,
                price = ?, price_pln = ?, fee_coin = ?, fee = ?,
                final_coin = ?, confirmed = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                tx.date.isoformat(timespec="minutes"),
                tx.type.value,
                tx.asset,
                tx.amount,
                tx.value_pln,
                tx.fee_pln,
                tx.exchange,
                tx.note,
                tx.currency,
                tx.value,
                tx.curr_to_pln,
                tx.coin_amount,
                tx.price,
                tx.price_pln,
                tx.fee_coin,
                tx.fee,
                tx.final_coin,
                1 if tx.confirmed else 0,
                _now(),
                tx.id,
            ),
        )
        self._conn.commit()

    def delete_transaction(self, tx_id: int) -> None:
        self._conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        self._conn.commit()

    def list_holdings(self) -> list[Holding]:
        cur = self._conn.execute(
            """
            SELECT * FROM holdings
            ORDER BY symbol COLLATE NOCASE ASC,
                     location COLLATE NOCASE ASC,
                     id ASC
            """
        )
        return [_row_to_holding(r) for r in cur.fetchall()]

    def get_holding(self, holding_id: int) -> Holding | None:
        cur = self._conn.execute("SELECT * FROM holdings WHERE id = ?", (holding_id,))
        row = cur.fetchone()
        return _row_to_holding(row) if row else None

    def insert_holding(self, holding: Holding) -> int:
        now = _now()
        try:
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
                    holding.amount,
                    holding.location,
                    now,
                    now,
                ),
            )
            self._conn.commit()
        except sqlite3.Error:
            self._conn.rollback()
            raise
        if cur.lastrowid is None:
            raise RuntimeError("INSERT nie zwrócił id holdings")
        return int(cur.lastrowid)

    def update_holding(self, holding: Holding) -> None:
        if holding.id is None:
            raise ValueError("Brak id holdings")
        try:
            self._conn.execute(
                """
                UPDATE holdings
                SET coin_id = ?, symbol = ?, amount = ?, location = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    holding.coin_id,
                    holding.symbol,
                    holding.amount,
                    holding.location,
                    _now(),
                    holding.id,
                ),
            )
            self._conn.commit()
        except sqlite3.Error:
            self._conn.rollback()
            raise

    def delete_holding(self, holding_id: int) -> None:
        self._conn.execute("DELETE FROM holdings WHERE id = ?", (holding_id,))
        self._conn.commit()

    def _clear_table(self, name: str) -> None:
        if name not in {"transactions", "holdings"}:
            raise ValueError(f"Niedozwolona tabela: {name}")
        self._conn.execute(f"DELETE FROM {name}")
        try:
            self._conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", (name,))
        except sqlite3.OperationalError:
            pass

    def replace_all_data(
        self,
        transactions: list[Transaction],
        holdings: list[Holding],
    ) -> tuple[int, int]:
        now = _now()
        try:
            self._conn.execute("BEGIN")
            self._clear_table("transactions")
            for tx in transactions:
                self._conn.execute(
                    """
                    INSERT INTO transactions (
                        date, type, asset, amount, value_pln, fee_pln, exchange, note,
                        currency, value, curr_to_pln, coin_amount, price, price_pln,
                        fee_coin, fee, final_coin, confirmed,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tx.date.isoformat(timespec="minutes"),
                        tx.type.value,
                        tx.asset,
                        tx.amount,
                        tx.value_pln,
                        tx.fee_pln,
                        tx.exchange,
                        tx.note,
                        tx.currency,
                        tx.value,
                        tx.curr_to_pln,
                        tx.coin_amount,
                        tx.price,
                        tx.price_pln,
                        tx.fee_coin,
                        tx.fee,
                        tx.final_coin,
                        1 if tx.confirmed else 0,
                        now,
                        now,
                    ),
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
                        holding.amount,
                        holding.location,
                        now,
                        now,
                    ),
                )

            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        return len(transactions), len(holdings)
