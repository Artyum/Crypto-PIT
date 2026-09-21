from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

DATETIME_FMT = "%Y-%m-%d %H:%M"
_LOCAL_TZ = ZoneInfo("Europe/Warsaw")


def local_now() -> datetime:

    return datetime.now(_LOCAL_TZ).replace(tzinfo=None)


def make_local_datetime(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    microsecond: int = 0,
) -> datetime:

    return datetime(
        year,
        month,
        day,
        hour,
        minute,
        second,
        microsecond,
        tzinfo=_LOCAL_TZ,
    ).replace(tzinfo=None)


def parse_naive(text: str, fmt: str) -> datetime:
    return datetime.strptime(text, fmt).replace(tzinfo=_LOCAL_TZ).replace(tzinfo=None)


def fmt_datetime(dt: datetime) -> str:
    return dt.strftime(DATETIME_FMT)


def parse_datetime(text: str) -> datetime:
    return datetime.fromisoformat(text.strip())
