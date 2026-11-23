from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest
from crypto_pit.datetime_fmt import parse_naive
from crypto_pit.domain.enums import TxType
from crypto_pit.domain.models import Transaction
from crypto_pit.infrastructure.database import (
    Database,
)
from crypto_pit.services.calculator import settle_years
from crypto_pit.services.dca import query_dca
from crypto_pit.services.reporting import export_report


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


def test_query_dca_remaining_messages() -> None:
    buy = _tx()
    assert query_dca([buy], "zle", "2024-06-01").message == "Nieprawidłowa data."
    assert query_dca([], "2024-01-01", "2024-01-02").message == "Brak zakupów."


def test_export_report(tmp_path: Path) -> None:
    path = tmp_path / "raport.csv"
    sell = _tx(type=TxType.SELL, value_pln=200, fee_pln=2, id=3)
    years = settle_years([sell])
    export_report(path, [sell], years)
    text = path.read_text(encoding="utf-8-sig")
    assert "TRANSAKCJE" in text
    assert "PIT-38" in text
    assert "linia | druga" in text


def test_cli_and_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from crypto_pit.__main__ import main
    from crypto_pit.cli import run_cli

    db_path = tmp_path / "cli.db"
    db = Database(db_path)
    db.insert_transaction(_tx(type=TxType.SELL, value_pln=80, fee_pln=1))
    db.close()
    run_cli(db_path)
    printed = capsys.readouterr().out
    assert "ROK 2024" in printed
    assert "Podatek 19%" in printed

    monkeypatch.setattr(sys, "argv", ["crypto-pit", "--cli", "--db", str(db_path)])
    main()
    assert "ROK 2024" in capsys.readouterr().out

    called: list[Path | None] = []
    monkeypatch.setattr(
        "crypto_pit.gui.app.run_app", lambda path=None: called.append(path)
    )
    monkeypatch.setattr(sys, "argv", ["crypto-pit", "--db", str(db_path)])
    main()
    assert called == [db_path]
