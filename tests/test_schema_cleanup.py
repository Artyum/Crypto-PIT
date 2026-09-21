from __future__ import annotations

import sqlite3
from pathlib import Path

from crypto_pit.datetime_fmt import parse_naive
from crypto_pit.domain.enums import TxType
from crypto_pit.domain.models import Holding, Transaction
from crypto_pit.infrastructure.database import Database
from crypto_pit.services.backup import export_backup, parse_backup


def _seed_legacy_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
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
            import_hash TEXT,
            classification_override TEXT,
            raw_json TEXT,
            currency TEXT NOT NULL DEFAULT 'PLN',
            value REAL NOT NULL DEFAULT 0,
            curr_to_pln REAL NOT NULL DEFAULT 1,
            coin_amount REAL NOT NULL DEFAULT 0,
            price REAL NOT NULL DEFAULT 0,
            price_pln REAL NOT NULL DEFAULT 0,
            fee_coin REAL NOT NULL DEFAULT 0,
            fee REAL NOT NULL DEFAULT 0,
            final_coin REAL NOT NULL DEFAULT 0,
            calc_variant TEXT NOT NULL DEFAULT '',
            confirmed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX idx_transactions_import_hash
            ON transactions(import_hash) WHERE import_hash IS NOT NULL;
        CREATE TABLE import_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT
        );
        """
    )
    conn.execute(
        """
        INSERT INTO transactions (
            date, type, asset, amount, value_pln, fee_pln, exchange, note,
            source, import_hash, classification_override, raw_json,
            currency, value, curr_to_pln, coin_amount, price, price_pln,
            fee_coin, fee, final_coin, calc_variant, confirmed,
            created_at, updated_at
        ) VALUES (
            '2024-01-15T10:00', 'buy', 'BTC', 0.01, 1000.0, 5.0, 'Binance', 'note',
            'import', 'abc123', NULL, '{"x":1}',
            'PLN', 1000.0, 1.0, 0.01, 100000.0, 100000.0,
            0.0, 5.0, 0.01, 'import', 1,
            '2024-01-15T10:00:00', '2024-01-15T10:00:00'
        )
        """
    )
    conn.commit()
    conn.close()


def test_destructive_migration_drops_import_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    _seed_legacy_db(db_path)

    db = Database(db_path)
    try:
        cols = {
            row[1]
            for row in db._conn.execute("PRAGMA table_info(transactions)").fetchall()
        }
        assert "source" not in cols
        assert "import_hash" not in cols
        assert "classification_override" not in cols
        assert "raw_json" not in cols
        assert "calc_variant" not in cols
        assert "confirmed" in cols
        assert "exchange" in cols
        assert "note" in cols

        tables = {
            row[0]
            for row in db._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "import_batches" not in tables

        txs = db.list_transactions()
        assert len(txs) == 1
        assert txs[0].asset == "BTC"
        assert txs[0].value_pln == 1000.0
        assert txs[0].confirmed is True
        assert txs[0].exchange == "Binance"
        assert txs[0].note == "note"
    finally:
        db.close()


def test_backup_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "backup.zip"
    tx = Transaction(
        date=parse_naive("2024-03-01 12:00", "%Y-%m-%d %H:%M"),
        type=TxType.SELL,
        asset="ETH",
        amount=1.5,
        value_pln=15000.0,
        fee_pln=10.0,
        exchange="Zonda",
        note="ok",
        currency="PLN",
        value=15000.0,
        curr_to_pln=1.0,
        coin_amount=1.5,
        price=10000.0,
        price_pln=10000.0,
        fee_coin=0.0,
        fee=10.0,
        final_coin=1.5,
        confirmed=True,
    )
    holdings = [
        Holding(coin_id="bitcoin", symbol="BTC", amount=0.5, location="Binance"),
        Holding(coin_id="ethereum", symbol="ETH", amount=2.0, location="Ledger"),
    ]
    export_backup(path, [tx], holdings)

    data = parse_backup(path)
    assert len(data.transactions) == 1
    assert data.transactions[0].asset == "ETH"
    assert data.transactions[0].type == TxType.SELL
    assert data.transactions[0].confirmed is True
    assert len(data.holdings) == 2

    db = Database(tmp_path / "restore.db")
    try:
        db.insert_holding(
            Holding(coin_id="old", symbol="OLD", amount=1.0, location="X")
        )
        n_tx, n_h = db.replace_all_data(data.transactions, data.holdings)
        assert (n_tx, n_h) == (1, 2)
        assert len(db.list_transactions()) == 1
        assert all(h.coin_id != "old" for h in db.list_holdings())
    finally:
        db.close()
