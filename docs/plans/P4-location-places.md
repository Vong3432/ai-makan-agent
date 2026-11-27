# P4 — Geocoding, timezone, Places + caches

**Goal:** turn free-text location into coordinates + timezone, and find nearby places cheaply.
**Specs:** [Recommendation Pipeline](../specs/04-recommendation-pipeline.md), [Cost, Safety & Privacy](../specs/08-cost-safety-privacy.md)

## Tasks

- [ ] **P4-T1** `location/geocode.py`: normalise query text → check `geocode_cache` → call provider (decision D2) on miss → store.
- [ ] **P4-T2** `location/timezone.py`: lat/lng → IANA timezone (decision D3).
- [ ] **P4-T3** `location/places.py`: Places API (New) Nearby/Text Search with **field mask** limited to id, name, location, types, rating, open-now, price level.
- [ ] **P4-T4** Cache key = geohash (precision ~6) + cuisine/type; TTL 7 days; read-through in `places_cache`.
- [ ] **P4-T5** Distance calc (haversine) and radius filtering.
- [ ] **P4-T6** Radius resolution: profile default, overridden by request phrases ("walking distance" ≈ 1 km, "can drive" ≈ 10 km).
- [ ] **P4-T7** Unit tests with `respx` mocks; assert field mask header is always sent; assert cache hit skips HTTP.
- [ ] **P4-T8** Log every billable API call (for cost tracking).

## Done when

- Second identical lookup makes zero external calls.
- Tests confirm field mask and radius behaviour.
