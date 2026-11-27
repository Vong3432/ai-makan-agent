# P6 — Preference scoring (pure logic)

**Goal:** deterministic, fully unit-tested scoring and variety rules with no I/O.
**Specs:** [Preference Model](../specs/05-preference-model.md), [Recommendation Pipeline](../specs/04-recommendation-pipeline.md)

## Tasks

- [ ] **P6-T1** `domain/preferences.py`: `tag_scores(events, now)` with 60-day half-life `0.5 ** (age_days / 60)`.
- [ ] **P6-T2** `preference_score(candidate_tags, tag_scores)`.
- [ ] **P6-T3** `domain/ranking.py`: habit fit (budget vs price level, spice tolerance, health goals, dine-in/delivery).
- [ ] **P6-T4** Repetition rules: dish within 3 days, place within 2 days → excluded unless explicitly requested.
- [ ] **P6-T5** Novelty: identify "never tried" candidates; `select_three()` = top 2 by score + best explore pick.
- [ ] **P6-T6** Hard-filter function contract: takes allergen-check results + dietary rules, returns survivors (never reads scores).
- [ ] **P6-T7** Unit tests incl. property test: a candidate flagged for an allergen is **never** returned regardless of score.

## Done when

- 100% branch coverage on `domain/preferences.py` and `domain/ranking.py`.
