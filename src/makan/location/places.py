"""Nearby places for a cuisine, read-through cached (P4-T3, T4, T5).

Cache design
- Key: `v1:{geohash6}:{cuisine}:{radius bucket}`. The search is centred on the geohash
  cell, not the user's exact point, so everyone in the same ~1.2 x 0.6 km cell shares it.
  The radius bucket keeps a 1 km search from being reused for a 10 km request.
- The search area is the cell centre + bucket radius + half the cell diagonal, so it
  covers the user's circle wherever they are in the cell. Results are then filtered by
  haversine distance from the user's actual point.
- TTL 7 days. Opening state is stored as the place's weekly hours (`weekly_hours`) so it
  can be worked out at request time with `open_at`; the point-in-time `open_now` from a
  fresh search is dropped on cache hits because it goes stale.
"""

import re
from datetime import datetime, timedelta
from typing import Any, Protocol
from urllib.parse import urlencode

from pydantic import BaseModel

from makan.location.geo import (
    LatLng,
    bbox_around,
    geohash_bounds,
    geohash_center,
    geohash_encode,
    haversine_km,
)
from makan.location.google import GooglePlacesHTTP

PLACES_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.location",
        "places.types",
        "places.rating",
        "places.currentOpeningHours.openNow",
        "places.regularOpeningHours.periods",
        "places.priceLevel",
    ]
)
CACHE_TTL = timedelta(days=7)
GEOHASH_PRECISION = 6
RADIUS_BUCKETS_KM = (1, 2, 3, 5, 10, 20, 50)
CACHE_VERSION = "v2"  # v2: weekly_hours added

_PRICE_LEVELS = {
    "PRICE_LEVEL_FREE": 0,
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}


class PlacesCache(Protocol):
    async def get_places(self, key: str, max_age: timedelta) -> Any | None: ...
    async def put_places(self, key: str, payload: Any) -> None: ...


class Place(BaseModel):
    place_id: str
    name: str
    lat: float
    lng: float
    types: list[str] = []
    rating: float | None = None
    open_now: bool | None = None  # from a fresh search only; prefer open_at()
    # Weekly opening periods as [open, close] minutes from Sunday 00:00 in the place's
    # local time; close None = open around the clock. None = hours unknown.
    weekly_hours: list[tuple[int, int | None]] | None = None
    price_level: int | None = None  # 0 (free) .. 4 (very expensive)
    distance_km: float | None = None  # from the user's point; set by `find`


def maps_url(place_id: str, name: str) -> str:
    """Google Maps link that opens this exact place (official Maps URLs format, free,
    no API call; works for cached places too)."""
    return "https://www.google.com/maps/search/?" + urlencode(
        {"api": "1", "query": name, "query_place_id": place_id}
    )


def normalise_cuisine(cuisine: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", cuisine.lower()).strip("_")


def radius_bucket(radius_km: float) -> int:
    return next((b for b in RADIUS_BUCKETS_KM if radius_km <= b), RADIUS_BUCKETS_KM[-1])


def cache_key(point: LatLng, cuisine: str, radius_km: float) -> str:
    gh = geohash_encode(point.lat, point.lng, GEOHASH_PRECISION)
    return f"{CACHE_VERSION}:{gh}:{normalise_cuisine(cuisine)}:{radius_bucket(radius_km)}"


def parse_place(raw: dict[str, Any]) -> Place | None:
    loc = raw.get("location") or {}
    if not raw.get("id") or "latitude" not in loc or "longitude" not in loc:
        return None
    return Place(
        place_id=raw["id"],
        name=(raw.get("displayName") or {}).get("text") or raw["id"],
        lat=float(loc["latitude"]),
        lng=float(loc["longitude"]),
        types=raw.get("types") or [],
        rating=raw.get("rating"),
        open_now=(raw.get("currentOpeningHours") or {}).get("openNow"),
        weekly_hours=_parse_periods((raw.get("regularOpeningHours") or {}).get("periods")),
        price_level=_PRICE_LEVELS.get(raw.get("priceLevel", "")),
    )


WEEK_MINUTES = 7 * 24 * 60


def _minute_of_week(point: dict[str, Any]) -> int:
    return int(point["day"]) * 1440 + int(point.get("hour", 0)) * 60 + int(point.get("minute", 0))


def _parse_periods(periods: Any) -> list[tuple[int, int | None]] | None:
    """Google `regularOpeningHours.periods` (day 0 = Sunday) -> minute-of-week ranges."""
    if not periods:
        return None
    out: list[tuple[int, int | None]] = []
    try:
        for p in periods:
            close = p.get("close")
            out.append((_minute_of_week(p["open"]), _minute_of_week(close) if close else None))
    except (KeyError, TypeError, ValueError):
        return None
    return out


def open_at(place: Place, local: datetime) -> bool | None:
    """Is the place open at `local` (wall-clock time where the place is)?
    Uses weekly hours when known, else a fresh `open_now`, else None (unknown)."""
    if place.weekly_hours is None:
        return place.open_now
    now = ((local.weekday() + 1) % 7) * 1440 + local.hour * 60 + local.minute  # Sunday = 0
    for start, end in place.weekly_hours:
        if end is None:
            return True
        length = (end - start) % WEEK_MINUTES
        if (now - start) % WEEK_MINUTES < length:
            return True
    return False


def within_radius(places: list[Place], origin: LatLng, radius_km: float) -> list[Place]:
    """Annotate distance from `origin`, keep those within radius, nearest first."""
    out = []
    for p in places:
        d = haversine_km(origin, LatLng(p.lat, p.lng))
        if d <= radius_km:
            out.append(p.model_copy(update={"distance_km": round(d, 3)}))
    return sorted(out, key=lambda p: p.distance_km or 0.0)


class PlacesFinder:
    def __init__(self, cache: PlacesCache, http: GooglePlacesHTTP) -> None:
        self.cache = cache
        self.http = http

    async def find(self, origin: LatLng, cuisine: str, radius_km: float) -> list[Place]:
        """Places serving `cuisine` within `radius_km` of `origin`, nearest first."""
        cuisine = cuisine.strip()
        if not cuisine:
            raise ValueError("cuisine is empty")
        key = cache_key(origin, cuisine, radius_km)

        cached = await self.cache.get_places(key, CACHE_TTL)
        if cached is not None:
            # open_now is a snapshot from fetch time; weekly_hours stays valid.
            places = [Place.model_validate({**p, "open_now": None}) for p in cached]
        else:
            places = await self._fetch(key, cuisine, radius_km)
            await self.cache.put_places(
                key, [p.model_dump(mode="json", exclude={"distance_km"}) for p in places]
            )
        return within_radius(places, origin, radius_km)

    async def _fetch(self, key: str, cuisine: str, radius_km: float) -> list[Place]:
        gh = key.split(":")[1]
        cell = geohash_bounds(gh)
        center = geohash_center(gh)
        half_diag = haversine_km(cell.low, cell.high) / 2
        area = bbox_around(center, radius_bucket(radius_km) + half_diag)
        raw = await self.http.text_search(
            purpose="places",
            text_query=f"{cuisine} food",
            field_mask=PLACES_FIELD_MASK,
            restrict_to=area,
        )
        return [p for r in raw if (p := parse_place(r)) is not None]
