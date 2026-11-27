"""lat/lng -> IANA timezone, offline via `timezonefinder` (decision D3, P4-T2)."""

from functools import lru_cache

from timezonefinder import TimezoneFinder


@lru_cache(maxsize=1)
def _finder() -> TimezoneFinder:
    return TimezoneFinder()


def timezone_at(lat: float, lng: float) -> str | None:
    """IANA name (e.g. "Asia/Kuala_Lumpur"), or None if it can't be determined."""
    return _finder().timezone_at(lat=lat, lng=lng)
