from __future__ import annotations

import sqlite3
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from crypto_pit.datetime_fmt import parse_naive
from crypto_pit.domain.enums import TxType
from crypto_pit.domain.models import Holding, Transaction
from crypto_pit.infrastructure.database import (
    Database,
    _row_bool,
    _row_decimal,
    _row_str,
)


def _num(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise TypeError(type(value))
    return Decimal(str(value)) if isinstance(value, float) else Decimal(value)


def _tx(**overrides: object) -> Transaction:
    data: dict[str, object] = {
        "date": parse_naive("2024-06-01 12:00", "%Y-%m-%d %H:%M"),
        "type": TxType.BUY,
        "asset": "btc",
        "amount": Decimal(1),
        "value_pln": Decimal(100),
        "fee_pln": Decimal(1),
        "note": "linia\ndruga",
        "currency": "",
    }
    data.update(overrides)
    for key in (
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
    ):
        if key in data:
            data[key] = _num(data[key])
    return Transaction(**data)  # type: ignore[arg-type]


def test_database_crud_filters_and_migration(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE t (value REAL, name TEXT, flag INTEGER)")
    conn.execute("INSERT INTO t VALUES (NULL, NULL, NULL)")
    row = conn.execute("SELECT * FROM t").fetchone()
    assert row is not None
    assert _row_decimal(row, "missing") == 0
    assert _row_decimal(row, "value") == 0
    assert _row_str(row, "missing", "domyślne") == "domyślne"
    assert _row_str(row, "name") == ""
    assert _row_bool(row, "missing") is False
    assert _row_bool(row, "flag") is False

    db = Database(tmp_path / "app.db")
    try:
        assert db.get_transaction(1) is None
        assert db.get_holding(1) is None
        tx = _tx(
            confirmed=True,
            currency="USD",
            value=25,
            curr_to_pln=4,
            nbp_date=date(2026, 8, 26),
            nbp_table="165/A/NBP/2026",
        )
        tx_id = db.insert_transaction(tx)
        tx.id = tx_id
        tx.note = "zmiana"
        db.update_transaction(tx)
        stored = db.get_transaction(tx_id)
        assert stored is not None
        assert stored.nbp_date == date(2026, 8, 26)
        assert stored.nbp_table == "165/A/NBP/2026"
        assert db.list_transactions(year=2024, tx_type=TxType.BUY)
        assert db.list_transactions(year=1999) == []
        with pytest.raises(ValueError):
            db.update_transaction(_tx())
        db.delete_transaction(tx_id)
        assert db.list_transactions() == []

        holding = Holding(coin_id="bitcoin", symbol="BTC", amount=2, location="A")
        holding_id = db.insert_holding(holding)
        holding.id = holding_id
        holding.amount = 3
        db.update_holding(holding)
        assert db.get_holding(holding_id) is not None
        with pytest.raises(ValueError):
            db.update_holding(Holding("x", "X", 1, "B"))
        with pytest.raises(ValueError):
            db._clear_table("users")
        real_conn = db._conn

        class _IdLess:
            def __init__(self, cursor: sqlite3.Cursor) -> None:
                self._cursor = cursor
                self.lastrowid = None

            def __getattr__(self, name: str) -> object:
                return getattr(self._cursor, name)

        class _Conn:
            def __init__(self, mode: str) -> None:
                self.mode = mode

            def execute(self, sql: str, params: object = ()) -> sqlite3.Cursor:
                if self.mode == "sequence" and "sqlite_sequence" in sql:
                    raise sqlite3.OperationalError("brak sqlite_sequence")
                if self.mode == "update" and str(sql).lstrip().startswith(
                    "UPDATE holdings"
                ):
                    raise sqlite3.OperationalError("zapis")
                cursor = real_conn.execute(sql, params)
                if self.mode == "noid" and "INSERT INTO" in str(sql):
                    return _IdLess(cursor)
                return cursor

            def __getattr__(self, name: str) -> object:
                return getattr(real_conn, name)

        db._conn = _Conn("sequence")  # type: ignore[assignment]
        db._clear_table("transactions")
        db._conn = _Conn("update")  # type: ignore[assignment]
        with pytest.raises(sqlite3.OperationalError):
            db.update_holding(holding)
        db._conn = real_conn
        db.delete_holding(holding_id)
        db._conn = _Conn("noid")  # type: ignore[assignment]
        with pytest.raises(RuntimeError):
            db.insert_transaction(_tx())
        with pytest.raises(RuntimeError):
            db.insert_holding(Holding("eth", "ETH", 1, "B"))
        db._conn = real_conn

        duplicate = Holding(coin_id="bitcoin", symbol="BTC", amount=1, location="A")
        before = len(db.list_holdings())
        with pytest.raises(sqlite3.IntegrityError):
            db.replace_all_data([], [duplicate, duplicate])
        assert len(db.list_holdings()) == before
        n_tx, n_h = db.replace_all_data([_tx()], [duplicate])
        assert (n_tx, n_h) == (1, 1)
    finally:
        db.close()

    legacy = tmp_path / "legacy-no-confirmed.db"
    raw = sqlite3.connect(legacy)
    raw.executescript(
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
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE holdings (
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
    )
    raw.execute(
        """
        INSERT INTO transactions (
            date, type, asset, amount, value_pln, fee_pln, exchange, note,
            source, created_at, updated_at
        ) VALUES (
            '2023-05-01T00:00', 'sell', 'ETH', 1, 10, 1, '', '',
            'import', '2023-05-01T00:00:00', '2023-05-01T00:00:00'
        )
        """
    )
    raw.commit()
    raw.close()
    migrated = Database(legacy)
    try:
        rows = migrated.list_transactions()
        assert rows[0].confirmed is False
        assert rows[0].type == TxType.SELL
    finally:
        migrated.close()

    plain = tmp_path / "add-confirmed.db"
    raw = sqlite3.connect(plain)
    raw.executescript(
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
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    raw.execute(
        """
        INSERT INTO transactions (
            date, type, asset, amount, value_pln, fee_pln, exchange, note,
            currency, value, curr_to_pln, coin_amount, price, price_pln,
            fee_coin, fee, final_coin, created_at, updated_at
        ) VALUES (
            '2022-01-01T00:00', 'other', 'X', 1, 1, 0, '', '',
            'PLN', 1, 1, 1, 1, 1, 0, 0, 1,
            '2022-01-01T00:00:00', '2022-01-01T00:00:00'
        )
        """
    )
    raw.commit()
    raw.close()
    added = Database(plain)
    try:
        migrated_tx = added.list_transactions()[0]
        assert migrated_tx.confirmed is False
        assert migrated_tx.nbp_date is None
        assert migrated_tx.nbp_table == ""
    finally:
        added.close()
