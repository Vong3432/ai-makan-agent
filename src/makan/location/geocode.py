"""Free-text location -> coordinates + timezone, cached by normalised query (P4-T1).

Geocoding uses Places Text Search (decision D2) with a minimal field mask.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from makan.db.models import GeocodeEntry
from makan.location.google import GooglePlacesHTTP
from makan.location.timezone import timezone_at

GEOCODE_FIELD_MASK = "places.location"

_PUNCT = re.compile(r"[^\w\s,-]", re.UNICODE)
_SPACE = re.compile(r"\s+")
_FILLER = re.compile(r"^(near|around|at|in|by)\s+", re.I)


class GeocodeCache(Protocol):
    async def get_geocode(self, query_norm: str) -> GeocodeEntry | None: ...
    async def put_geocode(self, entry: GeocodeEntry) -> None: ...


@dataclass(frozen=True)
class GeoPoint:
    query_norm: str
    lat: float
    lng: float
    timezone: str | None
    cached: bool


def normalise_query(text: str) -> str:
    """Cache key for a location, e.g. '  Near KLCC!! ' -> 'klcc'."""
    t = unicodedata.normalize("NFKC", text).lower()
    t = _PUNCT.sub(" ", t)
    t = _SPACE.sub(" ", t).strip(" ,-")
    t = _FILLER.sub("", t)
    return t


class Geocoder:
    def __init__(self, cache: GeocodeCache, http: GooglePlacesHTTP) -> None:
        self.cache = cache
        self.http = http

    async def geocode(self, query: str) -> GeoPoint | None:
        """None if the location can't be found. Raises ValueError on empty input."""
        q = normalise_query(query)
        if not q:
            raise ValueError("location is empty")

        if (hit := await self.cache.get_geocode(q)) is not None:
            tz = hit.timezone or timezone_at(hit.lat, hit.lng)
            return GeoPoint(q, hit.lat, hit.lng, tz, cached=True)

        places = await self.http.text_search(
            purpose="geocode", text_query=q, field_mask=GEOCODE_FIELD_MASK, page_size=1
        )
        loc = places[0].get("location") if places else None
        if not loc or "latitude" not in loc or "longitude" not in loc:
            return None
        lat, lng = float(loc["latitude"]), float(loc["longitude"])
        tz = timezone_at(lat, lng)
        await self.cache.put_geocode(GeocodeEntry(query_norm=q, lat=lat, lng=lng, timezone=tz))
        return GeoPoint(q, lat, lng, tz, cached=False)
