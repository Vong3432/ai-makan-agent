# P7 — `recommend_meal` pipeline

**Goal:** the core tool, end-to-end.
**Specs:** [MCP Tools](../specs/03-tools.md), [Recommendation Pipeline](../specs/04-recommendation-pipeline.md)

## Tasks

- [x] **P7-T1** Tool signature `recommend_meal(location, meal_slot=None, request=None)`; validate `location` non-empty.
- [x] **P7-T2** Onboarding gate (P5-T6) → early return with questions.
- [x] **P7-T3** Resolve context: geocode → timezone (save to profile) → slot → radius.
- [x] **P7-T4** Candidate dishes via LLM (P3-T5).
- [x] **P7-T5** Hard filters: allergen check (P3-T6) + dietary rules (P6-T6).
- [x] **P7-T6** Places lookup per surviving cuisine (P4), cache-first; attach best place per dish within radius.
- [x] **P7-T7** Score + variety + select three (P6).
- [x] **P7-T8** Fallback: no places → dish-only options + "widen radius?" message. Never relax hard constraints.
- [x] **P7-T9** Reasons (P3-T8) + allergen notes ("confirm with vendor") where relevant.
- [x] **P7-T10** Persist batch + 3 recommendations.
- [x] **P7-T11** Response shape: compact JSON + short human-readable summary for the host to present.
- [x] **P7-T12** Integration test with `FakeLLM` + mocked Places: happy path, fallback path, allergen-excluded path, repetition path.
- [x] **P7-T13** Each recommended place includes a copyable Google Maps link (`place.maps_url`), also printed in `message`.

## Done when

- Manual test from MCP Inspector returns 3 sensible options for a real location.

## Implementation notes

- Logic in `tools/recommend.py` (testable with in-memory fakes); `server.py` wires repos, `deps.location_deps()` and the LLM. Statuses: `ok`, `needs_onboarding`, `location_not_found`, `no_safe_options`, `no_options` (everything repeated). Invalid `location`/`meal_slot` raise `ValueError` (tool error).
- **One path for normal and fallback results:** every safe dish becomes a candidate with each of its top 3 places *and* as a dish-only candidate with a −1.0 penalty; `select_three` keeps the best version of each dish. All three dish-only → `no_places_found` + `suggested_radius_km` (×2, at least +2 km).
- **Cost cap:** Places is queried for at most 5 distinct `places_query` values, chosen by a dish-only pre-score. Typical call: 3 LLM calls (propose, safety, reasons) + ≤5 Places searches (fewer when cached).
- **Safety:** with dietary rules set, a dish missing from the safety-check results is excluded (mirrors P6's rule for allergies). The check is skipped when there are no allergies or rules. With allergies, every option carries the "confirm with the vendor" note.
- **Places:** rated below 3.5 skipped (unrated kept); ordered by rating minus 0.15 per km. `open_now == False` excludes a place only when the slot is the current one; for a later slot `open_now` is not reported.
- **Budget:** `domain/budget.py` maps budget + currency to Google's price level (MYR, SGD, IDR, THB, USD, EUR, GBP, AUD; others → no budget penalty).
- **Explicit requests:** a dish named in `request` bypasses the repeat rule, is removed from the LLM's avoid list, and gets +3.0 so it wins.
- `write_reasons` failure falls back to a template reason; it never fails the recommendation.
- Live-checked (Claude Haiku 5.5 + Places + local Supabase): onboarding then two `recommend_meal` calls for Bangsar, 7–10 s each on a cold cache; peanut/halal exclusions applied; "walking distance" → 1 km; "soupy" → soups.
- Each place carries `maps_url`, a Google Maps link in the official Maps URLs format (`/maps/search/?api=1&query=<name>&query_place_id=<id>`). It's built locally: no extra API field or cost, and it works for cached places. The text `message` prints it under each option.
