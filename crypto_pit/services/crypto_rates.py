from __future__ import annotations

import threading
from dataclasses import dataclass
from decimal import Decimal

import requests

from crypto_pit.domain.money import DecimalError, parse_decimal
from crypto_pit.services.http_json import read_json, request_response

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
REQUEST_TIMEOUT_S = 20


class CryptoRateFetchError(Exception):
    pass


@dataclass(frozen=True)
class CoinInfo:
    id: str
    symbol: str
    name: str

    def label(self) -> str:
        return f"{self.symbol.upper()} — {self.name} ({self.id})"


@dataclass(frozen=True)
class CryptoPrice:
    coin_id: str
    usd: Decimal | None
    pln: Decimal | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.usd is not None and self.pln is not None


class CryptoRatesService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._prices: dict[str, CryptoPrice] = {}
        self._symbol_ids: dict[str, str] = {}

    def get_cached_price(self, coin_id: str) -> CryptoPrice | None:
        with self._lock:
            return self._prices.get(coin_id)

    def remember_symbol(self, symbol: str, coin_id: str) -> None:
        key = symbol.strip().upper()
        cid = coin_id.strip()
        if key and cid:
            with self._lock:
                self._symbol_ids[key] = cid

    def get_cached_price_for_symbol(self, symbol: str) -> CryptoPrice | None:
        with self._lock:
            cid = self._symbol_ids.get(symbol.strip().upper())
            if not cid:
                return None
            return self._prices.get(cid)

    def resolve_symbols(self, symbols: list[str]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for raw in symbols:
            key = raw.strip().upper()
            if not key:
                continue
            with self._lock:
                cached = self._symbol_ids.get(key)
            if cached:
                mapping[key] = cached
                continue
            try:
                found = self.search_coins(key, limit=10)
            except CryptoRateFetchError:
                continue
            chosen = next((coin for coin in found if coin.symbol.upper() == key), None)
            if chosen is None and found:
                chosen = found[0]
            if chosen is None:
                continue
            with self._lock:
                self._symbol_ids[key] = chosen.id
            mapping[key] = chosen.id
        return mapping

    def search_coins(self, query: str, *, limit: int = 40) -> list[CoinInfo]:
        text = (query or "").strip()
        if not text:
            return []
        payload = _get_json(f"{COINGECKO_BASE}/search", {"query": text})
        coins_raw = payload.get("coins") if isinstance(payload, dict) else None
        if not isinstance(coins_raw, list):
            raise CryptoRateFetchError("Niepoprawna odpowiedź CoinGecko (szukaj)")

        result: list[CoinInfo] = []
        seen: set[str] = set()
        for item in coins_raw:
            if not isinstance(item, dict):
                continue
            coin_id = str(item.get("id") or "").strip()
            symbol = str(item.get("symbol") or "").strip()
            name = str(item.get("name") or "").strip()
            if not coin_id or not symbol or coin_id in seen:
                continue
            seen.add(coin_id)
            result.append(CoinInfo(id=coin_id, symbol=symbol, name=name))
            if len(result) >= limit:
                break
        return result

    def fetch_prices(
        self,
        coin_ids: list[str],
        *,
        force_refresh: bool = False,
    ) -> dict[str, CryptoPrice]:
        unique = list(
            dict.fromkeys(item.strip() for item in coin_ids if item and item.strip())
        )
        if not unique:
            return {}
        with self._lock:
            to_fetch = [
                cid
                for cid in unique
                if force_refresh or cid not in self._prices or not self._prices[cid].ok
            ]
        if to_fetch:
            fetched = self._fetch_prices(to_fetch)
            with self._lock:
                self._prices.update(fetched)
        with self._lock:
            return {cid: self._prices[cid] for cid in unique if cid in self._prices}

    def _fetch_prices(self, coin_ids: list[str]) -> dict[str, CryptoPrice]:
        try:
            payload = _get_json(
                f"{COINGECKO_BASE}/simple/price",
                {"ids": ",".join(coin_ids), "vs_currencies": "usd,pln"},
            )
        except CryptoRateFetchError as exc:
            err = str(exc)
            return {
                cid: CryptoPrice(coin_id=cid, usd=None, pln=None, error=err)
                for cid in coin_ids
            }

        if not isinstance(payload, dict):
            err = "Niepoprawna odpowiedź CoinGecko (kursy)"
            return {
                cid: CryptoPrice(coin_id=cid, usd=None, pln=None, error=err)
                for cid in coin_ids
            }

        result: dict[str, CryptoPrice] = {}
        for cid in coin_ids:
            row = payload.get(cid)
            if not isinstance(row, dict):
                result[cid] = CryptoPrice(
                    coin_id=cid, usd=None, pln=None, error="Nieznany coin / brak w API"
                )
                continue
            usd = _as_decimal(row.get("usd"))
            pln = _as_decimal(row.get("pln"))
            if usd is None or pln is None:
                result[cid] = CryptoPrice(
                    coin_id=cid, usd=usd, pln=pln, error="Brak kursu USD lub PLN"
                )
            else:
                result[cid] = CryptoPrice(coin_id=cid, usd=usd, pln=pln)
        return result


def _get_json(url: str, params: dict[str, str]) -> object:
    try:
        response = request_response(url, params=params, timeout=REQUEST_TIMEOUT_S)
    except requests.RequestException as exc:
        raise CryptoRateFetchError(f"Błąd połączenia z CoinGecko: {exc}") from exc
    if response.status_code == 429:
        raise CryptoRateFetchError("Limit zapytań CoinGecko (429) — spróbuj za chwilę")
    if response.status_code != 200:
        raise CryptoRateFetchError(f"CoinGecko zwróciło status {response.status_code}")
    try:
        return read_json(response)
    except ValueError as exc:
        raise CryptoRateFetchError(f"Niepoprawna odpowiedź CoinGecko: {exc}") from exc


def _as_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return parse_decimal(str(value) if not isinstance(value, str) else value)
    except DecimalError:
        return None
