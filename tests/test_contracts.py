from __future__ import annotations

import sqlite3
import threading
import time
from decimal import Decimal
from pathlib import Path

import pytest
from crypto_pit.config import resolve_db_path
from crypto_pit.datetime_fmt import parse_naive
from crypto_pit.domain.calc import ValidationError, resolve_trade
from crypto_pit.domain.enums import TxType
from crypto_pit.domain.models import Holding, Transaction
from crypto_pit.domain.money import (
    DecimalError,
    currency_code,
    decimal_from_legacy_real,
    parse_decimal,
)
from crypto_pit.gui.tasks import UiTaskRunner
from crypto_pit.infrastructure.database import SCHEMA_VERSION, Database
from crypto_pit.services import backup as backup_mod
from crypto_pit.services.backup import export_backup, parse_backup


def _tx(**overrides: object) -> Transaction:
    data: dict[str, object] = {
        "date": parse_naive("2024-06-01 12:00", "%Y-%m-%d %H:%M"),
        "type": TxType.BUY,
        "asset": "BTC",
        "amount": Decimal(1),
        "value_pln": Decimal(100),
        "fee_pln": Decimal(1),
    }
    data.update(overrides)
    return Transaction(**data)  # type: ignore[arg-type]


class _TaskRoot:
    def after(self, milliseconds: int, callback: object) -> None:
        del milliseconds, callback


def test_decimal_parser_rejects_non_finite_and_invalid_text() -> None:
    with pytest.raises(DecimalError):
        parse_decimal("nan")
    with pytest.raises(DecimalError):
        parse_decimal("inf")
    with pytest.raises(DecimalError):
        parse_decimal(float("nan"))
    with pytest.raises(DecimalError):
        parse_decimal("abc")
    assert parse_decimal("−1 200,5") == Decimal("-1200.5")
    assert currency_code(" usd ") == "USD"
    with pytest.raises(DecimalError):
        currency_code("../USD")


def test_legacy_float_scientific_notation_migrates_without_rounding() -> None:
    assert decimal_from_legacy_real(1.739e-05) == Decimal("0.00001739")


def test_trade_rejects_non_finite_values_instead_of_hiding_them() -> None:
    with pytest.raises(ValidationError):
        resolve_trade(
            exchange="Binance",
            tx_type=TxType.BUY,
            curr_to_pln=1,
            value=Decimal("NaN"),
            fee=1,
            final_coin=1,
        )


def test_backup_rejects_damaged_numbers_and_unknown_type(tmp_path: Path) -> None:
    damaged = (
        "Data;Typ;Wartość PLN\n"
        "2024-01-02;Nieznany;10\n"
        "2024-01-03;Kupno;-5\n"
        "2024-01-04;Kupno;nan\n"
    )
    with pytest.raises(ValueError, match="nieznany typ"):
        backup_mod._parse_transactions(damaged)

    huge = tmp_path / "huge.zip"
    huge.write_bytes(b"PK" + b"x" * 100)
    original = backup_mod.MAX_BACKUP_BYTES
    backup_mod.MAX_BACKUP_BYTES = 10
    try:
        with pytest.raises(ValueError, match="limit rozmiaru"):
            parse_backup(huge)
    finally:
        backup_mod.MAX_BACKUP_BYTES = original


def test_backup_roundtrip_preserves_exact_decimals(tmp_path: Path) -> None:
    path = tmp_path / "exact.zip"
    tx = _tx(
        value=Decimal("10.125"),
        value_pln=Decimal("40.50"),
        curr_to_pln=Decimal("4.000001"),
        amount=Decimal("0.10000001"),
    )
    holding = Holding(
        coin_id="bitcoin", symbol="BTC", amount=Decimal("0.10000001"), location="A"
    )
    export_backup(path, [tx], [holding])
    loaded = parse_backup(path)
    assert loaded.transactions[0].value == Decimal("10.125")
    assert loaded.transactions[0].curr_to_pln == Decimal("4.000001")
    assert loaded.holdings[0].amount == Decimal("0.10000001")


def test_migration_is_versioned_and_not_repeated(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            asset TEXT NOT NULL,
            amount REAL NOT NULL,
            value_pln REAL NOT NULL,
            fee_pln REAL NOT NULL,
            exchange TEXT NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO transactions VALUES (
            1, '2024-01-01T00:00', 'buy', 'BTC', 1, 10, 0, '', '',
            '2024-01-01T00:00:00', '2024-01-01T00:00:00'
        )
        """
    )
    conn.execute("CREATE TABLE import_batches (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

    db = Database(path)
    try:
        version = db._conn.execute("PRAGMA user_version").fetchone()
        assert version is not None
        assert int(version[0]) == SCHEMA_VERSION
        assert not path.with_name(path.name + ".premigration").exists()
        tables = {
            row[0]
            for row in db._conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "import_batches" not in tables
        db._conn.execute("CREATE TABLE user_notes (id INTEGER PRIMARY KEY)")
    finally:
        db.close()

    reopened = Database(path)
    try:
        tables = {
            row[0]
            for row in reopened._conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "user_notes" in tables
    finally:
        reopened.close()


def test_locked_database_raises(tmp_path: Path) -> None:
    path = tmp_path / "busy.db"
    db = Database(path)
    other = sqlite3.connect(path, timeout=0)
    try:
        other.execute("BEGIN EXCLUSIVE")
        db._conn.execute("PRAGMA busy_timeout = 100")
        with pytest.raises(sqlite3.OperationalError):
            db.insert_transaction(_tx())
    finally:
        other.rollback()
        other.close()
        db.close()


def test_default_database_uses_existing_project_file_or_user_dir(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    legacy = project / "data"
    legacy.mkdir(parents=True)
    db_file = legacy / "crypto_pit.db"
    db_file.write_bytes(b"")
    assert (
        resolve_db_path(
            project_root=project,
            platform="win32",
            environ={"LOCALAPPDATA": str(tmp_path / "local")},
            home=tmp_path / "home",
        )
        == db_file
    )
    empty = tmp_path / "empty-project"
    empty.mkdir()
    resolved = resolve_db_path(
        project_root=empty,
        platform="win32",
        environ={"LOCALAPPDATA": str(tmp_path / "local")},
        home=tmp_path / "home",
    )
    assert resolved == tmp_path / "local" / "Crypto-PIT" / "crypto_pit.db"


def test_cancelled_background_task_does_not_update_ui() -> None:
    runner = UiTaskRunner(_TaskRoot())  # type: ignore[arg-type]
    called: list[object] = []
    started = threading.Event()
    release = threading.Event()

    def work() -> int:
        started.set()
        assert release.wait(2)
        return 1

    token = runner.submit(
        work,
        lambda value: called.append(value),
        lambda exc: called.append(exc),
    )
    assert started.wait(2)
    runner.cancel(token)
    release.set()
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        runner._poll()
        time.sleep(0.02)
    runner.close()
    assert called == []


def test_failed_migration_rolls_back_and_keeps_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            asset TEXT NOT NULL,
            amount REAL NOT NULL,
            value_pln REAL NOT NULL,
            fee_pln REAL NOT NULL,
            exchange TEXT NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO transactions VALUES (
            1, '2024-01-01T00:00', 'buy', 'BTC', 1, 10, 0, '', '',
            '2024-01-01T00:00:00', '2024-01-01T00:00:00'
        )
        """
    )
    conn.commit()
    conn.close()

    def fail(
        self: Database,
        row: sqlite3.Row,
        columns: dict[str, str],
    ) -> tuple[object, ...]:
        del self, row, columns
        raise RuntimeError("przerwana migracja")

    monkeypatch.setattr(Database, "_legacy_tx_params", fail)
    with pytest.raises(RuntimeError, match="przerwana migracja"):
        Database(path)

    assert path.with_name(path.name + ".premigration").exists()
    check = sqlite3.connect(path)
    try:
        version = check.execute("PRAGMA user_version").fetchone()
        count = check.execute("SELECT COUNT(*) FROM transactions").fetchone()
        names = {row[0] for row in check.execute("SELECT name FROM sqlite_master")}
    finally:
        check.close()
    assert version is not None and int(version[0]) == 0
    assert count is not None and int(count[0]) == 1
    assert "transactions" in names
    assert "transactions_legacy" not in names


def test_closed_runner_ignores_finished_background_work() -> None:
    runner = UiTaskRunner(_TaskRoot())  # type: ignore[arg-type]
    called: list[object] = []
    started = threading.Event()
    release = threading.Event()

    def work() -> int:
        started.set()
        assert release.wait(2)
        return 1

    runner.submit(
        work,
        lambda value: called.append(value),
        lambda exc: called.append(exc),
    )
    assert started.wait(2)
    runner.close()
    release.set()
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        runner._poll()
        time.sleep(0.02)
    assert called == []
