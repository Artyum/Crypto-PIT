from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
import requests
from crypto_pit.gui.formatters import (
    fmt_money,
    fmt_rate,
)
from crypto_pit.services.crypto_rates import (
    CoinInfo,
    CryptoPrice,
    CryptoRateFetchError,
    CryptoRatesService,
    _as_decimal,
    _get_json,
)
from crypto_pit.services.nbp_rates import NbpRate, RateFetchError, fetch_pln_rate


class _Response:
    def __init__(
        self,
        status_code: int,
        payload: object | None = None,
        broken: bool = False,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self._broken = broken
        self.text = text
        self.headers = headers or {}

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
    assert pln.mid == Decimal(1)

    calls = {"n": 0}
    monkeypatch.setattr("crypto_pit.services.nbp_rates.RETRY_PAUSE_S", 0)

    def fake_get(
        url: str,
        params: dict | None = None,
        timeout: int = 0,
        headers: dict[str, str] | None = None,
    ) -> _Response:
        calls["n"] += 1
        if "simple/price" in url:
            if params and params.get("ids") == "broken":
                return _Response(200, ["nie-slownik"])
            if params and params.get("ids") == "missing,partial":
                return _Response(200, {"partial": {"usd": "x", "pln": 1}})
            return _Response(200, {"bitcoin": {"usd": 2, "pln": "8.5"}})
        if calls["n"] <= 3:
            raise requests.ConnectionError("offline")
        if calls["n"] <= 6:
            return _Response(500)
        if calls["n"] == 7:
            return _Response(200, {"rates": []})
        if calls["n"] == 8:
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

    monkeypatch.setattr("crypto_pit.services.http_json.requests.get", fake_get)
    with pytest.raises(RateFetchError, match="połączenia"):
        fetch_pln_rate("USD", day)
    with pytest.raises(RateFetchError, match="niedostępne"):
        fetch_pln_rate("USD", day)
    with pytest.raises(RateFetchError, match="Niepoprawna"):
        fetch_pln_rate("USD", day)
    with pytest.raises(RateFetchError, match="niepoprawny kurs"):
        fetch_pln_rate("USD", day)
    rate = fetch_pln_rate("USD", day)
    assert rate.mid == Decimal("4.2")
    assert rate.table_no == "—"
    assert rate.currency_name == "dolar"

    monkeypatch.setattr(
        "crypto_pit.services.nbp_rates.MAX_LOOKBACK_DAYS",
        1,
    )
    calls["n"] = 100

    def only_404(
        url: str,
        params: dict | None = None,
        timeout: int = 0,
        headers: dict[str, str] | None = None,
    ) -> _Response:
        return _Response(404)

    monkeypatch.setattr("crypto_pit.services.http_json.requests.get", only_404)
    with pytest.raises(RateFetchError, match="Brak tabeli"):
        fetch_pln_rate("EUR", day)

    def offline(url: str, params: dict | None = None, timeout: int = 0) -> _Response:
        raise requests.ConnectionError("offline")

    monkeypatch.setattr("crypto_pit.services.http_json.requests.get", offline)
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

    monkeypatch.setattr("crypto_pit.services.http_json.requests.get", status_get)
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

    monkeypatch.setattr("crypto_pit.services.http_json.requests.get", fake_get)
    prices = service.fetch_prices(["bitcoin"])
    assert prices["bitcoin"].ok
    cached = service.fetch_prices(["bitcoin"])
    assert cached["bitcoin"].pln == Decimal("8.5")
    refreshed = service.fetch_prices(["bitcoin"], force_refresh=True)
    assert refreshed["bitcoin"].usd == Decimal(2)

    failed = service.fetch_prices(["broken"])
    assert failed["broken"].error
    partial = service.fetch_prices(["missing", "partial"])
    assert partial["missing"].error == "Nieznany coin / brak w API"
    assert partial["partial"].error == "Brak kursu USD lub PLN"

    def boom(url: str, params: dict | None = None, timeout: int = 0) -> _Response:
        raise requests.ConnectionError("down")

    monkeypatch.setattr("crypto_pit.services.http_json.requests.get", boom)
    errored = service.fetch_prices(["solana"], force_refresh=True)
    assert "CoinGecko" in str(errored["solana"].error)
    assert _as_decimal(None) is None
    assert _as_decimal("1.5") == Decimal("1.5")
    assert _as_decimal(object()) is None
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

    monkeypatch.setattr("crypto_pit.services.http_json.requests.get", search_get)
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
    assert fmt_rate(Decimal("0.00123000")) == "0.00123"


def test_nbp_picks_newest_table_on_or_before_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    def fake_get(
        url: str,
        params: dict | None = None,
        timeout: int = 0,
        headers: dict[str, str] | None = None,
    ) -> _Response:
        seen.append(url)
        return _Response(
            200,
            {
                "currency": "dolar amerykański",
                "rates": [
                    {
                        "mid": 3.6839,
                        "effectiveDate": "2026-08-21",
                        "no": "162/A/NBP/2026",
                    },
                    {
                        "mid": 3.6852,
                        "effectiveDate": "2026-08-26",
                        "no": "165/A/NBP/2026",
                    },
                    {
                        "mid": 3.7151,
                        "effectiveDate": "2026-08-27",
                        "no": "166/A/NBP/2026",
                    },
                ],
            },
        )

    monkeypatch.setattr("crypto_pit.services.http_json.requests.get", fake_get)
    rate = fetch_pln_rate("usd", date(2026, 8, 26))
    assert rate.effective_date == date(2026, 8, 26)
    assert rate.mid == Decimal("3.6852")
    assert rate.table_no == "165/A/NBP/2026"
    assert seen == [
        "https://api.nbp.pl/api/exchangerates/rates/A/USD/2026-08-17/2026-08-26/"
    ]


def test_nbp_retries_gateway_404(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}
    monkeypatch.setattr("crypto_pit.services.nbp_rates.RETRY_PAUSE_S", 0)

    def fake_get(
        url: str,
        params: dict | None = None,
        timeout: int = 0,
        headers: dict[str, str] | None = None,
    ) -> _Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return _Response(404, headers={"Content-Type": "text/html"})
        return _Response(
            200,
            {
                "currency": "dolar",
                "rates": [
                    {
                        "mid": "3.6852",
                        "effectiveDate": "2026-08-26",
                        "no": "165/A/NBP/2026",
                    }
                ],
            },
        )

    monkeypatch.setattr("crypto_pit.services.http_json.requests.get", fake_get)
    rate = fetch_pln_rate("USD", date(2026, 8, 26))
    assert calls["n"] == 3
    assert rate.effective_date == date(2026, 8, 26)
    assert rate.mid == Decimal("3.6852")
