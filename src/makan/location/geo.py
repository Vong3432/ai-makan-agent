"""Pure geo helpers: geohash, haversine distance, bounding boxes. No I/O."""

import math
from dataclasses import dataclass

EARTH_RADIUS_KM = 6371.0088
_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"


@dataclass(frozen=True)
class LatLng:
    lat: float
    lng: float


@dataclass(frozen=True)
class BBox:
    low: LatLng  # south-west
    high: LatLng  # north-east


def geohash_encode(lat: float, lng: float, precision: int = 6) -> str:
    lat_lo, lat_hi = -90.0, 90.0
    lng_lo, lng_hi = -180.0, 180.0
    out: list[str] = []
    bits, ch, even = 0, 0, True
    while len(out) < precision:
        if even:
            mid = (lng_lo + lng_hi) / 2
            if lng >= mid:
                ch, lng_lo = (ch << 1) | 1, mid
            else:
                ch, lng_hi = ch << 1, mid
        else:
            mid = (lat_lo + lat_hi) / 2
            if lat >= mid:
                ch, lat_lo = (ch << 1) | 1, mid
            else:
                ch, lat_hi = ch << 1, mid
        even = not even
        bits += 1
        if bits == 5:
            out.append(_BASE32[ch])
            bits, ch = 0, 0
    return "".join(out)


def geohash_bounds(gh: str) -> BBox:
    lat_lo, lat_hi = -90.0, 90.0
    lng_lo, lng_hi = -180.0, 180.0
    even = True
    for c in gh:
        val = _BASE32.index(c)
        for shift in range(4, -1, -1):
            bit = (val >> shift) & 1
            if even:
                mid = (lng_lo + lng_hi) / 2
                lng_lo, lng_hi = (mid, lng_hi) if bit else (lng_lo, mid)
            else:
                mid = (lat_lo + lat_hi) / 2
                lat_lo, lat_hi = (mid, lat_hi) if bit else (lat_lo, mid)
            even = not even
    return BBox(LatLng(lat_lo, lng_lo), LatLng(lat_hi, lng_hi))


def geohash_center(gh: str) -> LatLng:
    b = geohash_bounds(gh)
    return LatLng((b.low.lat + b.high.lat) / 2, (b.low.lng + b.high.lng) / 2)


def haversine_km(a: LatLng, b: LatLng) -> float:
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp = p2 - p1
    dl = math.radians(b.lng - a.lng)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(h)))


def bbox_around(center: LatLng, radius_km: float) -> BBox:
    """Smallest lat/lng rectangle containing the circle (clamped at the poles)."""
    dlat = math.degrees(radius_km / EARTH_RADIUS_KM)
    cos_lat = max(math.cos(math.radians(center.lat)), 1e-6)
    dlng = min(180.0, math.degrees(radius_km / (EARTH_RADIUS_KM * cos_lat)))
    return BBox(
        LatLng(max(-90.0, center.lat - dlat), center.lng - dlng),
        LatLng(min(90.0, center.lat + dlat), center.lng + dlng),
    )
