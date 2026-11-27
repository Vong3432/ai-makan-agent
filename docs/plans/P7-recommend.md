# P7 — `recommend_meal` pipeline

**Goal:** the core tool, end-to-end.
**Specs:** [MCP Tools](../specs/03-tools.md), [Recommendation Pipeline](../specs/04-recommendation-pipeline.md)

## Tasks

- [ ] **P7-T1** Tool signature `recommend_meal(location, meal_slot=None, request=None)`; validate `location` non-empty.
- [ ] **P7-T2** Onboarding gate (P5-T6) → early return with questions.
- [ ] **P7-T3** Resolve context: geocode → timezone (save to profile) → slot → radius.
- [ ] **P7-T4** Candidate dishes via LLM (P3-T5).
- [ ] **P7-T5** Hard filters: allergen check (P3-T6) + dietary rules (P6-T6).
- [ ] **P7-T6** Places lookup per surviving cuisine (P4), cache-first; attach best place per dish within radius.
- [ ] **P7-T7** Score + variety + select three (P6).
- [ ] **P7-T8** Fallback: no places → dish-only options + "widen radius?" message. Never relax hard constraints.
- [ ] **P7-T9** Reasons (P3-T8) + allergen notes ("confirm with vendor") where relevant.
- [ ] **P7-T10** Persist batch + 3 recommendations.
- [ ] **P7-T11** Response shape: compact JSON + short human-readable summary for the host to present.
- [ ] **P7-T12** Integration test with `FakeLLM` + mocked Places: happy path, fallback path, allergen-excluded path, repetition path.

## Done when

- Manual test from MCP Inspector returns 3 sensible options for a real location.
