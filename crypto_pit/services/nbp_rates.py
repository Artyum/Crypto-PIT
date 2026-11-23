from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import requests

from crypto_pit.domain.money import DecimalError, currency_code, parse_decimal
from crypto_pit.services.http_json import RetryExhausted, read_json, request_response

NBP_URL = "https://api.nbp.pl/api/exchangerates/rates/A/{currency}/{start}/{end}/"
MAX_LOOKBACK_DAYS = 10
MAX_ATTEMPTS = 3
REQUEST_TIMEOUT_S = 10
RETRY_PAUSE_S = 0.3
_RETRY_STATUS = frozenset({500, 502, 503, 504})


class RateFetchError(Exception):
    pass


@dataclass(frozen=True)
class NbpRate:
    code: str
    currency_name: str
    mid: Decimal
    effective_date: date
    table_no: str


def fetch_pln_rate(currency: str, before_date: date) -> NbpRate:
    try:
        code = currency_code(currency)
    except DecimalError as exc:
        raise RateFetchError("Brak kodu waluty") from exc
    if code == "PLN":
        return NbpRate(
            code="PLN",
            currency_name="złoty polski",
            mid=Decimal(1),
            effective_date=before_date,
            table_no="—",
        )

    start = before_date - timedelta(days=MAX_LOOKBACK_DAYS - 1)
    url = NBP_URL.format(
        currency=code, start=start.isoformat(), end=before_date.isoformat()
    )
    try:
        response = request_response(
            url,
            params={"format": "json"},
            headers={"Accept": "application/json"},
            timeout=REQUEST_TIMEOUT_S,
            attempts=MAX_ATTEMPTS,
            pause_s=RETRY_PAUSE_S,
            retry_if=_is_transient,
        )
    except RetryExhausted as exc:
        raise RateFetchError(f"NBP chwilowo niedostępne ({exc})") from exc
    except requests.RequestException as exc:
        raise RateFetchError(f"Błąd połączenia z NBP: {exc}") from exc
    if response.status_code == 404:
        raise RateFetchError(
            f"Brak tabeli NBP dla {code} w dniu {before_date.isoformat()}"
        )
    if response.status_code != 200:
        raise RateFetchError(
            f"NBP zwróciło status {response.status_code} dla {code} "
            f"({before_date.isoformat()})"
        )
    try:
        payload = read_json(response)
    except ValueError as exc:
        raise RateFetchError(f"Niepoprawna odpowiedź NBP: {exc}") from exc
    return _rate_from_payload(code, before_date, payload)


def _is_transient(response: requests.Response) -> bool:
    if response.status_code in _RETRY_STATUS:
        return True
    if response.status_code != 404:
        return False
    content_type = str(response.headers.get("Content-Type", "")).lower()
    return "html" in content_type


def _rate_from_payload(code: str, before_date: date, payload: object) -> NbpRate:
    if not isinstance(payload, dict):
        raise RateFetchError("Niepoprawna odpowiedź NBP: brak kursów")
    try:
        rates = payload["rates"]
        currency_name = str(payload.get("currency") or code)
    except (KeyError, TypeError) as exc:
        raise RateFetchError(f"Niepoprawna odpowiedź NBP: {exc}") from exc
    if not isinstance(rates, list) or not rates:
        raise RateFetchError("Niepoprawna odpowiedź NBP: brak kursów")

    chosen_day: date | None = None
    chosen_mid = Decimal(0)
    chosen_no = ""
    for item in rates:
        if not isinstance(item, dict):
            raise RateFetchError("Niepoprawna odpowiedź NBP: brak kursów")
        try:
            table_day = date.fromisoformat(str(item["effectiveDate"]))
            mid = parse_decimal(str(item["mid"]))
            table_no = str(item.get("no") or "—")
        except (KeyError, TypeError, ValueError, DecimalError) as exc:
            raise RateFetchError(f"Niepoprawna odpowiedź NBP: {exc}") from exc
        if table_day > before_date:
            continue
        if chosen_day is None or table_day > chosen_day:
            chosen_day = table_day
            chosen_mid = mid
            chosen_no = table_no
    if chosen_day is None:
        raise RateFetchError(
            f"Brak tabeli NBP dla {code} w dniu {before_date.isoformat()}"
        )
    if chosen_mid <= 0:
        raise RateFetchError(f"NBP zwróciło niepoprawny kurs: {chosen_mid}")
    return NbpRate(
        code=code,
        currency_name=currency_name,
        mid=chosen_mid,
        effective_date=chosen_day,
        table_no=chosen_no,
    )
