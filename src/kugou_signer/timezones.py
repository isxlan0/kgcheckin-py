from __future__ import annotations

from datetime import timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


FALLBACK_TIMEZONES: dict[str, tzinfo] = {
    "Asia/Shanghai": timezone(timedelta(hours=8), name="CST"),
    "Asia/Hong_Kong": timezone(timedelta(hours=8), name="HKT"),
    "UTC": timezone.utc,
}


def resolve_timezone(name: str) -> tzinfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        if name in FALLBACK_TIMEZONES:
            return FALLBACK_TIMEZONES[name]
        raise
