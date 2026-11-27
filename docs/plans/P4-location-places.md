# P4 — Geocoding, timezone, Places + caches

**Goal:** turn free-text location into coordinates + timezone, and find nearby places cheaply.
**Specs:** [Recommendation Pipeline](../specs/04-recommendation-pipeline.md), [Cost, Safety & Privacy](../specs/08-cost-safety-privacy.md)

## Tasks

- [x] **P4-T1** `location/geocode.py`: normalise query text → check `geocode_cache` → call provider (decision D2) on miss → store.
- [x] **P4-T2** `location/timezone.py`: lat/lng → IANA timezone (decision D3).
- [x] **P4-T3** `location/places.py`: Places API (New) Nearby/Text Search with **field mask** limited to id, name, location, types, rating, open-now, price level.
- [x] **P4-T4** Cache key = geohash (precision ~6) + cuisine/type; TTL 7 days; read-through in `places_cache`.
- [x] **P4-T5** Distance calc (haversine) and radius filtering.
- [x] **P4-T6** Radius resolution: profile default, overridden by request phrases ("walking distance" ≈ 1 km, "can drive" ≈ 10 km).
- [x] **P4-T7** Unit tests with `respx` mocks; assert field mask header is always sent; assert cache hit skips HTTP.
- [x] **P4-T8** Log every billable API call (for cost tracking).

## Done when

- Second identical lookup makes zero external calls.
- Tests confirm field mask and radius behaviour.

## Implementation notes

- Modules: `location/geo.py` (geohash, haversine, bbox — pure), `radius.py` (pure), `timezone.py`, `google.py` (HTTP client; one Text Search method that refuses to run without a field mask and logs every call on the `makan.billing` logger), `geocode.py`, `places.py`. `deps.location_deps()` wires them to `CacheRepo` (service role); `override_location()` for tests.
- Geocode: query normalised (lowercase, NFKC, punctuation stripped, leading "near/around/at/in/by" dropped) → `geocode_cache` → Text Search with mask `places.location`, `pageSize: 1`. Not-found results are not cached. Timezone is computed with `timezonefinder` and stored with the entry.
- Places: Text Search `"{cuisine} food"` with a **`locationRestriction` rectangle** (Nearby Search needs fixed place types; free-text cuisines like "nasi lemak" don't map to those). Results are filtered by haversine distance from the user's exact point and sorted nearest first.
- Cache key `v2:{geohash6}:{cuisine}:{radius bucket}`; buckets 1/2/3/5/10/20/50 km. The search is centred on the geohash cell (radius = bucket + half the cell diagonal), so everyone in the cell shares an entry and the user's circle is always covered. TTL 7 days.
- Opening hours: the field mask also requests `places.regularOpeningHours.periods`, stored as `weekly_hours` (minute-of-week ranges, Sunday = 0; no close = 24/7). `open_at(place, local_time)` works out whether a place is open at request time, so it stays correct for cached places. The point-in-time `open_now` from a search is dropped on cache hits. Cache key version is `v2` (v1 entries had no hours). Holiday/special hours are not reflected.
- Radius: an explicit distance in the request ("within 2 km", "800m") wins, then walking phrases → 1 km, driving phrases → 10 km, then the profile default, else 3 km. Clamped to 0.2–50 km (Places max).
- `PLACES_REGION_CODE` (default `MY`) biases results to a country.
- Live-checked: "Bangsar" geocode + "nasi lemak" within 2 km → 11 places; repeat lookups made zero external calls (cache hits in ~15 ms).
