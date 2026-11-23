from __future__ import annotations

import time
from collections.abc import Callable

import requests

DEFAULT_TIMEOUT_S = 10


class RetryExhausted(Exception):
    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__(f"status {status}")


def request_response(
    url: str,
    *,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
    attempts: int = 1,
    pause_s: float = 0.0,
    retry_if: Callable[[requests.Response], bool] | None = None,
) -> requests.Response:
    last_error: requests.RequestException | None = None
    last_status = 0
    for attempt in range(attempts):
        try:
            if headers is None:
                response = requests.get(url, params=params, timeout=timeout)
            else:
                response = requests.get(
                    url, params=params, headers=headers, timeout=timeout
                )
        except requests.RequestException as exc:
            last_error = exc
            if attempt + 1 == attempts:
                raise
            time.sleep(pause_s)
            continue
        if retry_if is None or not retry_if(response):
            return response
        last_status = response.status_code
        if attempt + 1 < attempts:
            time.sleep(pause_s)
    if last_error is not None:
        raise last_error
    raise RetryExhausted(last_status)


def read_json(response: requests.Response) -> object:
    try:
        return response.json()
    except ValueError as exc:
        raise ValueError("niepoprawny JSON") from exc
