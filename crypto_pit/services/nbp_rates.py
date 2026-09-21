from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import requests

NBP_URL = "https://api.nbp.pl/api/exchangerates/rates/A/{currency}/{day}/"
MAX_LOOKBACK_DAYS = 10
REQUEST_TIMEOUT_S = 10


class RateFetchError(Exception):
    pass


@dataclass(frozen=True)
class NbpRate:
    code: str
    currency_name: str
    mid: float
    effective_date: date
    table_no: str
    requested_before: date


def fetch_pln_rate(currency: str, before_date: date) -> NbpRate:
    code = (currency or "").strip().upper()
    if not code:
        raise RateFetchError("Brak kodu waluty")
    if code == "PLN":
        return NbpRate(
            code="PLN",
            currency_name="złoty polski",
            mid=1.0,
            effective_date=before_date,
            table_no="—",
            requested_before=before_date,
        )

    day = before_date
    last_error = ""
    for _ in range(MAX_LOOKBACK_DAYS):
        url = NBP_URL.format(currency=code, day=day.isoformat())
        try:
            resp = requests.get(
                url, params={"format": "json"}, timeout=REQUEST_TIMEOUT_S
            )
        except requests.RequestException as exc:
            raise RateFetchError(f"Błąd połączenia z NBP: {exc}") from exc

        if resp.status_code == 404:
            last_error = f"Brak tabeli NBP dla {code} w dniu {day.isoformat()}"
            day = day - timedelta(days=1)
            continue
        if resp.status_code != 200:
            raise RateFetchError(
                f"NBP zwróciło status {resp.status_code} dla {code} ({day.isoformat()})"
            )
        try:
            payload = resp.json()
            rate = payload["rates"][0]
            mid = float(rate["mid"])
            table_day = date.fromisoformat(rate["effectiveDate"])
            table_no = str(rate.get("no") or "—")
            currency_name = str(payload.get("currency") or code)
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise RateFetchError(f"Niepoprawna odpowiedź NBP: {exc}") from exc
        if mid <= 0:
            raise RateFetchError(f"NBP zwróciło niepoprawny kurs: {mid}")
        return NbpRate(
            code=code,
            currency_name=currency_name,
            mid=mid,
            effective_date=table_day,
            table_no=table_no,
            requested_before=before_date,
        )

    raise RateFetchError(
        last_error
        or f"Nie znaleziono kursu {code}/PLN w ostatnich {MAX_LOOKBACK_DAYS} dniach"
    )
