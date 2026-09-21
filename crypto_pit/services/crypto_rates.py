from __future__ import annotations

from dataclasses import dataclass

import requests

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
    usd: float | None
    pln: float | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.usd is not None and self.pln is not None


class CryptoRatesService:
    def __init__(self) -> None:
        self._prices: dict[str, CryptoPrice] = {}

    def get_cached_price(self, coin_id: str) -> CryptoPrice | None:
        return self._prices.get(coin_id)

    def search_coins(self, query: str, *, limit: int = 40) -> list[CoinInfo]:
        q = (query or "").strip()
        if not q:
            return []
        payload = _get_json(f"{COINGECKO_BASE}/search", {"query": q})
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
        unique = list(dict.fromkeys(c.strip() for c in coin_ids if c and c.strip()))
        if not unique:
            return {}

        to_fetch = [
            cid
            for cid in unique
            if force_refresh or cid not in self._prices or not self._prices[cid].ok
        ]
        if to_fetch:
            self._prices.update(self._fetch_prices(to_fetch))

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
            usd = _as_float(row.get("usd"))
            pln = _as_float(row.get("pln"))
            if usd is None or pln is None:
                result[cid] = CryptoPrice(
                    coin_id=cid, usd=usd, pln=pln, error="Brak kursu USD lub PLN"
                )
            else:
                result[cid] = CryptoPrice(coin_id=cid, usd=usd, pln=pln)
        return result


def _get_json(url: str, params: dict[str, str]) -> object:
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_S)
    except requests.RequestException as exc:
        raise CryptoRateFetchError(f"Błąd połączenia z CoinGecko: {exc}") from exc
    if resp.status_code == 429:
        raise CryptoRateFetchError("Limit zapytań CoinGecko (429) — spróbuj za chwilę")
    if resp.status_code != 200:
        raise CryptoRateFetchError(f"CoinGecko zwróciło status {resp.status_code}")
    try:
        return resp.json()
    except ValueError as exc:
        raise CryptoRateFetchError(f"Niepoprawna odpowiedź CoinGecko: {exc}") from exc


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
