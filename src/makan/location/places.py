"""Nearby places for a cuisine, read-through cached (P4-T3, T4, T5).

Cache design
- Key: `v1:{geohash6}:{cuisine}:{radius bucket}`. The search is centred on the geohash
  cell, not the user's exact point, so everyone in the same ~1.2 x 0.6 km cell shares it.
  The radius bucket keeps a 1 km search from being reused for a 10 km request.
- The search area is the cell centre + bucket radius + half the cell diagonal, so it
  covers the user's circle wherever they are in the cell. Results are then filtered by
  haversine distance from the user's actual point.
- TTL 7 days. `open_now` is only meaningful when fresh, so cache hits return it as None.
"""

import re
from datetime import timedelta
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
        "places.priceLevel",
    ]
)
CACHE_TTL = timedelta(days=7)
GEOHASH_PRECISION = 6
RADIUS_BUCKETS_KM = (1, 2, 3, 5, 10, 20, 50)
CACHE_VERSION = "v1"

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
    open_now: bool | None = None
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
        price_level=_PRICE_LEVELS.get(raw.get("priceLevel", "")),
    )


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
