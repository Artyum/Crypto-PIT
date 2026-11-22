from __future__ import annotations

import sqlite3
import sys
import zipfile
from datetime import date, datetime
from pathlib import Path

import pytest
import requests

from crypto_pit.datetime_fmt import fmt_datetime, parse_datetime, parse_naive
from crypto_pit.domain.calc import ValidationError, _to_result, resolve_trade
from crypto_pit.domain.enums import TxType, normalize_tx_type
from crypto_pit.domain.exchange_profiles import (
    _coin_amount_fee,
    _coin_amount_fee_coin,
    _fee_coin_final_coin,
    _fee_final_coin,
    get_profile,
    has_profile,
)
from crypto_pit.domain.models import Holding, Transaction, YearSettlement
from crypto_pit.domain.pit38 import pit38_short_header
from crypto_pit.gui.formatters import (
    fmt_money,
    fmt_money_compact,
    fmt_qty,
    fmt_rate,
    parse_float,
)
from crypto_pit.infrastructure.database import (
    Database,
    _row_bool,
    _row_float,
    _row_str,
)
from crypto_pit.services.backup import (
    _clean_amount,
    _fmt_num,
    _parse_date,
    _parse_holdings,
    _parse_transactions,
    _read_csv,
    export_backup,
    parse_backup,
)
from crypto_pit.services.calculator import line_impact, settle_years
from crypto_pit.services.crypto_rates import (
    CoinInfo,
    CryptoPrice,
    CryptoRateFetchError,
    CryptoRatesService,
    _as_float,
    _get_json,
)
from crypto_pit.services.dca import query_dca
from crypto_pit.services.nbp_rates import NbpRate, RateFetchError, fetch_pln_rate
from crypto_pit.services.reporting import export_report


def _tx(**overrides: object) -> Transaction:
    data: dict[str, object] = {
        "date": parse_naive("2024-06-01 12:00", "%Y-%m-%d %H:%M"),
        "type": TxType.BUY,
        "asset": "btc",
        "amount": 1.0,
        "value_pln": 100.0,
        "fee_pln": 1.0,
        "note": "linia\ndruga",
        "currency": "",
    }
    data.update(overrides)
    return Transaction(**data)  # type: ignore[arg-type]


def test_datetime_roundtrip_and_other_cost() -> None:
    parsed = parse_datetime(" 2024-01-02T03:04:05 ")
    assert fmt_datetime(parsed) == "2024-01-02 03:04"
    other = _tx(type=TxType.OTHER)
    assert other.pit_cost() == 0.0
    assert normalize_tx_type(None) == TxType.OTHER
    assert normalize_tx_type("  ") == TxType.OTHER
    assert normalize_tx_type("nieznany") == TxType.OTHER
    settlement = YearSettlement(
        year=2024,
        revenue=1,
        costs_current=2,
        costs_prior=3,
        costs_total=5,
        income=0,
        carried_forward=4,
        tax_19=0,
        tx_count=1,
        buy_count=1,
        sell_count=0,
        other_count=0,
    )
    assert settlement.pit_fields()["przychod"] == 1
    assert pit38_short_header("nieznane") == "nieznane"


def test_calc_validation_and_profiles() -> None:
    base = {
        "value": 10.0,
        "fee": 1.0,
        "fee_coin": 0.1,
        "coin_amount": 2.0,
        "final_coin": 1.0,
        "price": 4.0,
    }
    with pytest.raises(ValidationError):
        _to_result({**base, "value": 0}, 1)
    with pytest.raises(ValidationError):
        _to_result({**base, "fee": -1}, 1)
    with pytest.raises(ValidationError):
        _to_result({**base, "coin_amount": 0}, 1)
    with pytest.raises(ValidationError):
        _to_result(base, 0)
    with pytest.raises(ValidationError):
        _to_result({**base, "price": 0}, 1)
    with pytest.raises(ValidationError):
        _to_result({**base, "fee_coin": -1}, 1)
    with pytest.raises(ValidationError):
        _to_result({**base, "final_coin": 0}, 1)

    with pytest.raises(ValidationError):
        resolve_trade(exchange="nieznana", tx_type=TxType.BUY, curr_to_pln=1, value=1)
    assert (
        resolve_trade(exchange="Binance", tx_type=TxType.BUY, curr_to_pln=1, value=None)
        is None
    )
    assert (
        resolve_trade(
            exchange="Binance",
            tx_type=TxType.BUY,
            curr_to_pln=1,
            value=10,
            fee=10,
            final_coin=1,
        )
        is None
    )
    with pytest.raises(ValueError):
        _fee_final_coin(value=10, fee=10, final_coin=1)
    with pytest.raises(ValueError):
        _coin_amount_fee_coin(value=10, coin_amount=0, fee_coin=0)
    with pytest.raises(ValueError):
        _coin_amount_fee_coin(value=10, coin_amount=1, fee_coin=2)
    with pytest.raises(ValueError):
        _fee_coin_final_coin(value=10, fee_coin=-1, final_coin=1)
    with pytest.raises(ValueError):
        _coin_amount_fee(value=10, coin_amount=0, fee=0)
    with pytest.raises(ValueError):
        _coin_amount_fee(value=10, coin_amount=0.0000001, fee=10)
    with pytest.raises(KeyError):
        get_profile("Kanga", TxType.SELL)
    assert has_profile("Zonda", TxType.BUY)
    assert not has_profile("Kanga", TxType.OTHER)


def test_settle_empty_profit_and_line_impact() -> None:
    assert settle_years([]) == []
    buy = _tx(value_pln=100, fee_pln=0)
    sell = _tx(type=TxType.SELL, value_pln=500, fee_pln=10)
    other = _tx(
        type=TxType.OTHER,
        value_pln=5,
        date=parse_naive("2026-01-01 00:00", "%Y-%m-%d %H:%M"),
    )
    years = {row.year: row for row in settle_years([buy, sell, other])}
    assert years[2024].income > 0
    assert years[2024].carried_forward == 0
    assert years[2025].tx_count == 0
    assert years[2026].other_count == 1
    impact = line_impact(_tx(id=None))
    assert impact["id"] == 0
    assert impact["asset"] == "BTC"
    assert "linia" in str(impact["note"])


def test_formatters() -> None:
    assert fmt_money(None) == "—"
    assert fmt_money(1234.5) == "1 234,50"
    assert fmt_money_compact(1.2) == "1,20"
    assert fmt_qty(0.0) == "0"
    assert fmt_qty(1.5) == "1.5"
    assert parse_float(" 1 234,5 ") == 1234.5
    assert parse_float(" \u00a0 ") == 0.0


def test_backup_numbers_dates_and_errors(tmp_path: Path) -> None:
    assert _fmt_num(-0.4, 0) == "0"
    assert _clean_amount(None) == 0.0
    assert _clean_amount(" nan ") == 0.0
    assert _clean_amount("none") == 0.0
    assert _clean_amount("  ") == 0.0
    assert _clean_amount("abc") == 0.0
    assert _clean_amount("−1 200,5") == pytest.approx(-1200.5)
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
    assert parsed[0].price == pytest.approx(50)
    assert parsed[0].fee_coin == pytest.approx(4 / 50)
    assert parsed[0].exchange == "Binance"

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
        [Holding(coin_id="bitcoin", symbol="btc", amount=1.5, location="Ledger")],
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
    with pytest.raises(ValueError, match="holdings.csv"):
        parse_backup(incomplete)


def test_database_crud_filters_and_migration(tmp_path: Path) -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE t (value REAL, name TEXT, flag INTEGER)")
    conn.execute("INSERT INTO t VALUES (NULL, NULL, NULL)")
    row = conn.execute("SELECT * FROM t").fetchone()
    assert row is not None
    assert _row_float(row, "missing") == 0.0
    assert _row_float(row, "value") == 0.0
    assert _row_str(row, "missing", "domyślne") == "domyślne"
    assert _row_str(row, "name") == ""
    assert _row_bool(row, "missing") is False
    assert _row_bool(row, "flag") is False

    db = Database(tmp_path / "app.db")
    try:
        assert db.get_transaction(1) is None
        assert db.get_holding(1) is None
        tx = _tx(confirmed=True, currency="USD", value=25, curr_to_pln=4)
        tx_id = db.insert_transaction(tx)
        tx.id = tx_id
        tx.note = "zmiana"
        db.update_transaction(tx)
        assert db.get_transaction(tx_id) is not None
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
        assert added.list_transactions()[0].confirmed is False
    finally:
        added.close()


class _Response:
    def __init__(
        self, status_code: int, payload: object | None = None, broken: bool = False
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self._broken = broken

    def json(self) -> object:
        if self._broken:
            raise ValueError("zły json")
        return self._payload


def test_nbp_and_crypto_rates(monkeypatch: pytest.MonkeyPatch) -> None:
    day = date(2024, 1, 10)
    with pytest.raises(RateFetchError, match="kodu"):
        fetch_pln_rate("  ", day)
    pln = fetch_pln_rate("pln", day)
    assert isinstance(pln, NbpRate)
    assert pln.mid == 1.0

    calls = {"n": 0}

    def fake_get(url: str, params: dict | None = None, timeout: int = 0) -> _Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.ConnectionError("offline")
        if "simple/price" in url:
            if params and params.get("ids") == "broken":
                return _Response(200, ["nie-slownik"])
            if params and params.get("ids") == "missing,partial":
                return _Response(200, {"partial": {"usd": "x", "pln": 1}})
            return _Response(200, {"bitcoin": {"usd": 2, "pln": "8.5"}})
        if calls["n"] == 2:
            return _Response(404)
        if calls["n"] == 3:
            return _Response(500)
        if calls["n"] == 4:
            return _Response(200, {"rates": []})
        if calls["n"] == 5:
            return _Response(
                200, {"rates": [{"mid": 0, "effectiveDate": "2024-01-09"}]}
            )
        return _Response(
            200,
            {
                "currency": "dolar",
                "rates": [{"mid": "4.2", "effectiveDate": "2024-01-09", "no": ""}],
            },
        )

    monkeypatch.setattr("crypto_pit.services.nbp_rates.requests.get", fake_get)
    with pytest.raises(RateFetchError, match="połączenia"):
        fetch_pln_rate("USD", day)
    with pytest.raises(RateFetchError, match="status 500"):
        fetch_pln_rate("USD", day)
    with pytest.raises(RateFetchError, match="Niepoprawna"):
        fetch_pln_rate("USD", day)
    with pytest.raises(RateFetchError, match="niepoprawny kurs"):
        fetch_pln_rate("USD", day)
    rate = fetch_pln_rate("USD", day)
    assert rate.mid == pytest.approx(4.2)
    assert rate.table_no == "—"
    assert rate.currency_name == "dolar"

    monkeypatch.setattr(
        "crypto_pit.services.nbp_rates.MAX_LOOKBACK_DAYS",
        1,
    )
    calls["n"] = 100

    def only_404(url: str, params: dict | None = None, timeout: int = 0) -> _Response:
        return _Response(404)

    monkeypatch.setattr("crypto_pit.services.nbp_rates.requests.get", only_404)
    with pytest.raises(RateFetchError, match="Brak tabeli"):
        fetch_pln_rate("EUR", day)

    def offline(url: str, params: dict | None = None, timeout: int = 0) -> _Response:
        raise requests.ConnectionError("offline")

    monkeypatch.setattr("crypto_pit.services.crypto_rates.requests.get", offline)
    with pytest.raises(CryptoRateFetchError, match="połączenia"):
        _get_json("https://api.coingecko.com/api/v3/search", {"query": "btc"})

    def status_get(url: str, params: dict | None = None, timeout: int = 0) -> _Response:
        if params and params.get("query") == "limit":
            return _Response(429)
        if params and params.get("query") == "status":
            return _Response(503)
        if params and params.get("query") == "broken":
            return _Response(200, broken=True)
        if params and params.get("query") == "shape":
            return _Response(200, {"coins": "zle"})
        return _Response(
            200,
            {
                "coins": [
                    "zle",
                    {"id": "", "symbol": "x", "name": "x"},
                    {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
                    {"id": "bitcoin", "symbol": "btc", "name": "duplikat"},
                    {"id": "ethereum", "symbol": "eth", "name": "Ethereum"},
                ]
            },
        )

    monkeypatch.setattr("crypto_pit.services.crypto_rates.requests.get", status_get)
    with pytest.raises(CryptoRateFetchError, match="429"):
        _get_json("u", {"query": "limit"})
    with pytest.raises(CryptoRateFetchError, match="503"):
        _get_json("u", {"query": "status"})
    with pytest.raises(CryptoRateFetchError, match="Niepoprawna odpowiedź"):
        _get_json("u", {"query": "broken"})

    service = CryptoRatesService()
    assert service.search_coins("  ") == []
    with pytest.raises(CryptoRateFetchError):
        service.search_coins("shape")
    found = service.search_coins("btc", limit=1)
    assert found == [CoinInfo("bitcoin", "btc", "Bitcoin")]
    assert found[0].label().startswith("BTC")
    assert service.get_cached_price("bitcoin") is None
    assert service.fetch_prices([" ", ""]) == {}

    monkeypatch.setattr("crypto_pit.services.crypto_rates.requests.get", fake_get)
    prices = service.fetch_prices(["bitcoin"])
    assert prices["bitcoin"].ok
    cached = service.fetch_prices(["bitcoin"])
    assert cached["bitcoin"].pln == pytest.approx(8.5)
    refreshed = service.fetch_prices(["bitcoin"], force_refresh=True)
    assert refreshed["bitcoin"].usd == pytest.approx(2)

    failed = service.fetch_prices(["broken"])
    assert failed["broken"].error
    partial = service.fetch_prices(["missing", "partial"])
    assert partial["missing"].error == "Nieznany coin / brak w API"
    assert partial["partial"].error == "Brak kursu USD lub PLN"

    def boom(url: str, params: dict | None = None, timeout: int = 0) -> _Response:
        raise requests.ConnectionError("down")

    monkeypatch.setattr("crypto_pit.services.crypto_rates.requests.get", boom)
    errored = service.fetch_prices(["solana"], force_refresh=True)
    assert "CoinGecko" in str(errored["solana"].error)
    assert _as_float(None) is None
    assert _as_float("1.5") == 1.5
    assert _as_float(object()) is None
    assert CryptoPrice("x", None, 1).ok is False


def test_resolve_crypto_symbols(monkeypatch: pytest.MonkeyPatch) -> None:
    def search_get(url: str, params: dict | None = None, timeout: int = 0) -> _Response:
        query = str((params or {}).get("query") or "").upper()
        if query == "ETH":
            return _Response(
                200,
                {
                    "coins": [
                        {"id": "ethereum", "symbol": "eth", "name": "Ethereum"},
                    ]
                },
            )
        if query == "FOO":
            return _Response(
                200,
                {"coins": [{"id": "foo-token", "symbol": "zzz", "name": "Foo"}]},
            )
        if query == "FAIL":
            return _Response(503)
        return _Response(200, {"coins": []})

    monkeypatch.setattr("crypto_pit.services.crypto_rates.requests.get", search_get)
    service = CryptoRatesService()
    service.remember_symbol("btc", "bitcoin")
    mapping = service.resolve_symbols(["BTC", "eth", "foo", "zzz", "fail", "  "])
    assert mapping["BTC"] == "bitcoin"
    assert mapping["ETH"] == "ethereum"
    assert mapping["FOO"] == "foo-token"
    assert "ZZZ" not in mapping
    assert "FAIL" not in mapping
    assert service.get_cached_price_for_symbol("btc") is None
    assert fmt_rate(None) == "—"
    assert fmt_rate(1500) == fmt_money(1500)
    assert fmt_rate(0.00123000) == "0.00123"


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
