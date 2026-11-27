import json
import logging
from datetime import timedelta

import httpx
import pytest
import respx

from makan.db.models import GeocodeEntry
from makan.location import radius as R
from makan.location.geo import (
    LatLng,
    bbox_around,
    geohash_bounds,
    geohash_center,
    geohash_encode,
    haversine_km,
)
from makan.location.geocode import Geocoder, normalise_query
from makan.location.google import TEXT_SEARCH_URL, GooglePlacesHTTP, PlacesAPIError
from makan.location.places import (
    CACHE_TTL,
    PLACES_FIELD_MASK,
    Place,
    PlacesFinder,
    cache_key,
    radius_bucket,
)
from makan.location.timezone import timezone_at

KLCC = LatLng(3.1579, 101.7123)
BANGSAR = LatLng(3.1309, 101.6713)


class MemCache:
    def __init__(self) -> None:
        self.geo: dict[str, GeocodeEntry] = {}
        self.places: dict[str, object] = {}
        self.max_ages: list[timedelta] = []

    async def get_geocode(self, q):
        return self.geo.get(q)

    async def put_geocode(self, entry):
        self.geo[entry.query_norm] = entry

    async def get_places(self, key, max_age):
        self.max_ages.append(max_age)
        return self.places.get(key)

    async def put_places(self, key, payload):
        self.places[key] = json.loads(json.dumps(payload))  # as jsonb would round-trip


def raw_place(pid: str, at: LatLng, **extra) -> dict:
    return {
        "id": pid,
        "displayName": {"text": f"Place {pid}", "languageCode": "en"},
        "location": {"latitude": at.lat, "longitude": at.lng},
        "types": ["restaurant"],
        **extra,
    }


@pytest.fixture
def http():
    return GooglePlacesHTTP("test-key", client=httpx.AsyncClient(), region_code="MY")


# ---------- geo ----------


def test_geohash_known_value():
    assert geohash_encode(57.64911, 10.40744, 11) == "u4pruydqqvj"


def test_geohash_center_roundtrip():
    gh = geohash_encode(KLCC.lat, KLCC.lng, 6)
    c = geohash_center(gh)
    assert geohash_encode(c.lat, c.lng, 6) == gh
    b = geohash_bounds(gh)
    assert b.low.lat <= KLCC.lat <= b.high.lat and b.low.lng <= KLCC.lng <= b.high.lng


def test_haversine():
    assert haversine_km(KLCC, KLCC) == 0
    assert haversine_km(KLCC, BANGSAR) == pytest.approx(5.46, abs=0.1)
    # 1 degree of latitude ~ 111.2 km
    assert haversine_km(LatLng(0, 0), LatLng(1, 0)) == pytest.approx(111.2, abs=0.2)


def test_bbox_contains_circle():
    b = bbox_around(KLCC, 5)
    for bearing_pt in [LatLng(b.low.lat, KLCC.lng), LatLng(KLCC.lat, b.high.lng)]:
        assert haversine_km(KLCC, bearing_pt) == pytest.approx(5, rel=0.01)


# ---------- radius (P4-T6) ----------


@pytest.mark.parametrize(
    ("default", "request_text", "expected"),
    [
        (None, None, R.DEFAULT_RADIUS_KM),
        (5, None, 5),
        (5, "something soupy", 5),
        (5, "within walking distance please", R.WALKING_KM),
        (5, "I can drive", R.DRIVING_KM),
        (1, "happy to drive", R.DRIVING_KM),
        (5, "walkable, max 2 km", 2),
        (5, "within 800m", 0.8),
        (5, "within 500 km", R.MAX_RADIUS_KM),
        (500, None, R.MAX_RADIUS_KM),
        (0, None, R.DEFAULT_RADIUS_KM),
    ],
)
def test_resolve_radius(default, request_text, expected):
    assert R.resolve_radius(default, request_text) == pytest.approx(expected)


def test_radius_ignores_unrelated_numbers():
    assert R.radius_from_request("2 people, something spicy") is None


# ---------- timezone (P4-T2) ----------


def test_timezone_offline():
    assert timezone_at(KLCC.lat, KLCC.lng) == "Asia/Kuala_Lumpur"
    assert timezone_at(1.2834, 103.8607) == "Asia/Singapore"


# ---------- geocode (P4-T1) ----------


def test_normalise_query():
    assert normalise_query("  Near   KLCC!! ") == "klcc"
    assert normalise_query("Bangsar, KL") == "bangsar, kl"
    assert normalise_query("ＢＡＮＧＳＡＲ") == "bangsar"


@respx.mock
async def test_geocode_miss_then_hit(http):
    route = respx.post(TEXT_SEARCH_URL).respond(
        200, json={"places": [{"location": {"latitude": KLCC.lat, "longitude": KLCC.lng}}]}
    )
    cache = MemCache()
    g = Geocoder(cache, http)

    first = await g.geocode("Near KLCC")
    assert first and not first.cached
    assert first.timezone == "Asia/Kuala_Lumpur"
    req = route.calls.last.request
    assert req.headers["X-Goog-FieldMask"] == "places.location"
    assert req.headers["X-Goog-Api-Key"] == "test-key"
    body = json.loads(req.content)
    assert body == {"textQuery": "klcc", "pageSize": 1, "regionCode": "MY"}

    second = await g.geocode("klcc")
    assert second and second.cached and (second.lat, second.lng) == (first.lat, first.lng)
    assert route.call_count == 1  # cache hit made no HTTP call


@respx.mock
async def test_geocode_not_found_is_not_cached(http):
    route = respx.post(TEXT_SEARCH_URL).respond(200, json={})
    cache = MemCache()
    assert await Geocoder(cache, http).geocode("nowhere-ville") is None
    assert cache.geo == {} and route.call_count == 1


async def test_geocode_empty_rejected(http):
    with pytest.raises(ValueError):
        await Geocoder(MemCache(), http).geocode("  !! ")


@respx.mock
async def test_http_error_raises(http):
    respx.post(TEXT_SEARCH_URL).respond(403, json={"error": {"status": "PERMISSION_DENIED"}})
    with pytest.raises(PlacesAPIError, match="403"):
        await Geocoder(MemCache(), http).geocode("klcc")


def test_missing_key_rejected():
    with pytest.raises(PlacesAPIError, match="GOOGLE_API_KEY"):
        GooglePlacesHTTP("")


# ---------- places + cache (P4-T3/T4/T5) ----------


def test_cache_key_shape():
    k = cache_key(KLCC, "Nasi Lemak", 1.5)
    assert k == f"v1:{geohash_encode(KLCC.lat, KLCC.lng, 6)}:nasi_lemak:2"
    # same cell, same cuisine, same bucket -> same key
    nearby = LatLng(KLCC.lat + 0.0005, KLCC.lng)
    if geohash_encode(nearby.lat, nearby.lng, 6) == geohash_encode(KLCC.lat, KLCC.lng, 6):
        assert cache_key(nearby, "nasi lemak", 2) == k
    assert cache_key(KLCC, "nasi lemak", 3) != k


def test_radius_bucket():
    assert [radius_bucket(r) for r in (0.5, 1, 1.01, 10, 49, 80)] == [1, 1, 2, 10, 50, 50]


@respx.mock
async def test_places_fetch_filter_and_cache(http):
    near = LatLng(KLCC.lat + 0.005, KLCC.lng)  # ~0.56 km
    route = respx.post(TEXT_SEARCH_URL).respond(
        200,
        json={
            "places": [
                raw_place("far", BANGSAR, rating=4.6, priceLevel="PRICE_LEVEL_MODERATE"),  # ~5.5 km
                raw_place("near", near, rating=4.2, currentOpeningHours={"openNow": True}),
                {"id": "broken"},  # no location: dropped
            ]
        },
    )
    cache = MemCache()
    finder = PlacesFinder(cache, http)

    got = await finder.find(KLCC, "Malay", radius_km=2)
    assert [p.place_id for p in got] == ["near"]
    assert got[0].distance_km == pytest.approx(0.556, abs=0.01)
    assert got[0].open_now is True

    req = route.calls.last.request
    assert req.headers["X-Goog-FieldMask"] == PLACES_FIELD_MASK
    body = json.loads(req.content)
    assert body["textQuery"] == "Malay food"
    rect = body["locationRestriction"]["rectangle"]
    assert rect["low"]["latitude"] < KLCC.lat < rect["high"]["latitude"]
    assert rect["low"]["longitude"] < KLCC.lng < rect["high"]["longitude"]

    # Second identical lookup: zero HTTP calls; open_now unknown from cache.
    again = await finder.find(KLCC, "malay", radius_km=2)
    assert route.call_count == 1
    assert [p.place_id for p in again] == ["near"] and again[0].open_now is None
    assert cache.max_ages == [CACHE_TTL, CACHE_TTL]

    # Bigger radius -> different bucket -> new search; wider filter keeps both.
    wider = await finder.find(KLCC, "malay", radius_km=10)
    assert route.call_count == 2
    assert [p.place_id for p in wider] == ["near", "far"]
    assert wider[1].price_level == 2 and wider[1].rating == 4.6


@respx.mock
async def test_field_mask_always_sent(http):
    route = respx.post(TEXT_SEARCH_URL).respond(200, json={})
    cache = MemCache()
    await Geocoder(cache, http).geocode("bangsar")
    await PlacesFinder(cache, http).find(BANGSAR, "chinese", 3)
    assert route.call_count == 2
    for call in route.calls:
        mask = call.request.headers.get("X-Goog-FieldMask")
        assert mask and "*" not in mask


async def test_text_search_requires_mask(http):
    with pytest.raises(ValueError):
        await http.text_search(purpose="x", text_query="y", field_mask="")


@respx.mock
async def test_billable_calls_logged(http, caplog):
    respx.post(TEXT_SEARCH_URL).respond(200, json={})
    caplog.set_level(logging.INFO, logger="makan.billing")
    await PlacesFinder(MemCache(), http).find(KLCC, "indian", 1)
    records = [r for r in caplog.records if r.name == "makan.billing"]
    assert len(records) == 1
    assert "api=places.searchText" in records[0].getMessage()
    assert "purpose=places" in records[0].getMessage()
    assert "test-key" not in records[0].getMessage()


def test_place_model_defaults():
    p = Place(place_id="x", name="X", lat=0, lng=0)
    assert p.open_now is None and p.types == []
