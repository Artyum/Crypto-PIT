from __future__ import annotations

import zipfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from crypto_pit.datetime_fmt import parse_naive
from crypto_pit.domain.enums import TxType
from crypto_pit.domain.models import Holding, Transaction
from crypto_pit.services.backup import (
    _fmt_num,
    _parse_date,
    _parse_holdings,
    _parse_transactions,
    _read_csv,
    export_backup,
    parse_backup,
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


def test_backup_numbers_dates_and_errors(tmp_path: Path) -> None:
    assert _fmt_num(Decimal("-0.4"), 0) == "0"
    assert _parse_date(None) is None
    assert _parse_date("nan") is None
    assert _parse_date("2024-03-04T05:06:07") == datetime.fromisoformat(
        "2024-03-04T05:06:07"
    )
    assert _parse_date("04.03.2024 05:06") is not None
    assert _parse_date("04.03.2024") is not None
    assert _parse_date("nie-data") is None
    with pytest.raises(ValueError, match="nagłówka"):
        _read_csv("")

    bad_rows = "\n".join(["Data;Typ;Wartość PLN"] + ["zle;Kupno;1"] * 6)
    with pytest.raises(ValueError, match="kolejnych"):
        _parse_transactions(bad_rows)
    with pytest.raises(ValueError, match="kolumn"):
        _parse_transactions("Data;Typ\n2024-01-01;Kupno\n")

    minimal = (
        "Data;Typ;Wartość PLN;Ilość;Prowizja PLN;Uwagi\n"
        "2024-01-02;Kupno;100;2;4;Binance\n"
    )
    parsed = _parse_transactions(minimal)
    assert parsed[0].price == 0
    assert parsed[0].fee_coin == 0
    assert parsed[0].exchange == ""
    assert parsed[0].amount == Decimal(2)
    assert parsed[0].value_pln == Decimal(100)
    assert parsed[0].nbp_date is None
    assert parsed[0].nbp_table == ""

    with_nbp = (
        "Data;Typ;Wartość PLN;Data kursu NBP;Tabela NBP\n"
        "2026-08-27;Kupno;10;26.08.2026;165/A/NBP/2026\n"
    )
    nbp_tx = _parse_transactions(with_nbp)[0]
    assert nbp_tx.nbp_date == date(2026, 8, 26)
    assert nbp_tx.nbp_table == "165/A/NBP/2026"
    with pytest.raises(ValueError, match="data kursu NBP"):
        _parse_transactions(
            "Data;Typ;Wartość PLN;Data kursu NBP\n2026-08-27;Kupno;10;nie-data\n"
        )

    holdings_bad = "\n".join(
        ["Coin ID;Symbol;Ilość"]
        + [";;1", ";BTC;1"]
        + ["bitcoin;BTC;1"] * 2
        + ["bitcoin;;1", "eth;ETH;1", "x;X;1"]
    )
    with pytest.raises(ValueError, match="portfel"):
        _parse_holdings(holdings_bad)

    archive = tmp_path / "backup.zip"
    export_backup(
        archive,
        [_tx(id=2, confirmed=True, exchange="Zonda")],
        [
            Holding(
                coin_id="bitcoin",
                symbol="btc",
                amount=Decimal("1.5"),
                location="Ledger",
            )
        ],
    )
    loaded = parse_backup(archive)
    assert loaded.transactions[0].confirmed
    assert loaded.transactions[0].note == "linia\ndruga"
    assert loaded.holdings[0].symbol == "btc"

    plain = tmp_path / "not.zip"
    plain.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="ZIP"):
        parse_backup(plain)
    incomplete = tmp_path / "half.zip"
    with zipfile.ZipFile(incomplete, "w") as zf:
        zf.writestr("transactions.csv", minimal)
    with pytest.raises(ValueError, match=r"holdings\.csv"):
        parse_backup(incomplete)

    nested = tmp_path / "nested.zip"
    holdings_csv = "Coin ID;Symbol;Ilość;Lokalizacja\nbitcoin;BTC;1;Ledger\n"
    with zipfile.ZipFile(nested, "w") as zf:
        zf.writestr("kopia/transactions.csv", minimal)
        zf.writestr("kopia/holdings.csv", holdings_csv)
    nested_data = parse_backup(nested)
    assert nested_data.transactions[0].exchange == ""
    assert nested_data.holdings[0].location == "Ledger"

    broken = tmp_path / "broken.zip"
    broken.write_bytes(b"PK\x03\x04" + b"\x00" * 30)
    with pytest.raises(ValueError, match="ZIP"):
        parse_backup(broken)
