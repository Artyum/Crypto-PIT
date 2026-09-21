from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from crypto_pit.domain.models import Holding
from crypto_pit.infrastructure.database import DEFAULT_HOLDING_LOCATION, Database


def _seed_legacy_holdings_db(path: Path) -> None:
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
        CREATE TABLE holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            coin_id TEXT NOT NULL UNIQUE,
            symbol TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        """
        INSERT INTO holdings (coin_id, symbol, amount, created_at, updated_at)
        VALUES ('bitcoin', 'BTC', 1.5, '2024-01-15T10:00:00', '2024-01-15T10:00:00')
        """
    )
    conn.commit()
    conn.close()


def test_holdings_migration_adds_default_location(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_holdings.db"
    _seed_legacy_holdings_db(db_path)

    db = Database(db_path)
    try:
        cols = {
            row[1] for row in db._conn.execute("PRAGMA table_info(holdings)").fetchall()
        }
        assert "location" in cols

        holdings = db.list_holdings()
        assert len(holdings) == 1
        assert holdings[0].coin_id == "bitcoin"
        assert holdings[0].location == DEFAULT_HOLDING_LOCATION
        assert holdings[0].amount == 1.5
    finally:
        db.close()


def test_same_coin_different_locations_allowed(tmp_path: Path) -> None:
    db = Database(tmp_path / "holdings.db")
    try:
        db.insert_holding(
            Holding(coin_id="bitcoin", symbol="BTC", amount=1.0, location="Ledger")
        )
        db.insert_holding(
            Holding(coin_id="bitcoin", symbol="BTC", amount=0.5, location="Trezor")
        )
        holdings = db.list_holdings()
        assert len(holdings) == 2
        assert [h.location for h in holdings] == ["Ledger", "Trezor"]
    finally:
        db.close()


def test_same_coin_same_location_rejected(tmp_path: Path) -> None:
    db = Database(tmp_path / "holdings_dup.db")
    try:
        db.insert_holding(
            Holding(coin_id="bitcoin", symbol="BTC", amount=1.0, location="Ledger")
        )
        with pytest.raises(sqlite3.IntegrityError):
            db.insert_holding(
                Holding(coin_id="bitcoin", symbol="BTC", amount=2.0, location="Ledger")
            )
        holdings = db.list_holdings()
        assert len(holdings) == 1
        assert holdings[0].amount == 1.0
    finally:
        db.close()
