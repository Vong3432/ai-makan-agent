# P6 — Preference scoring (pure logic)

**Goal:** deterministic, fully unit-tested scoring and variety rules with no I/O.
**Specs:** [Preference Model](../specs/05-preference-model.md), [Recommendation Pipeline](../specs/04-recommendation-pipeline.md)

## Tasks

- [x] **P6-T1** `domain/preferences.py`: `tag_scores(events, now)` with 60-day half-life `0.5 ** (age_days / 60)`.
- [x] **P6-T2** `preference_score(candidate_tags, tag_scores)`.
- [x] **P6-T3** `domain/ranking.py`: habit fit (budget vs price level, spice tolerance, health goals, dine-in/delivery).
- [x] **P6-T4** Repetition rules: dish within 3 days, place within 2 days → excluded unless explicitly requested.
- [x] **P6-T5** Novelty: identify "never tried" candidates; `select_three()` = top 2 by score + best explore pick.
- [x] **P6-T6** Hard-filter function contract: takes allergen-check results + dietary rules, returns survivors (never reads scores).
- [x] **P6-T7** Unit tests incl. property test: a candidate flagged for an allergen is **never** returned regardless of score.

## Done when

- 100% branch coverage on `domain/preferences.py` and `domain/ranking.py`.

## Implementation notes

- "Tried" = the user has a feedback event for that dish (onboarding loves/dislikes count once seeded in P5-T4). Being shown a dish does not count as trying it.
- With allergies declared, a dish **missing** from the allergen-check results is excluded (unknown = unsafe).
- `select_three` reserves one slot for the best untried dish when any exist; only that pick is flagged `is_explore`.
- Tunable constants live at the top of `domain/ranking.py` (novelty +0.3, shown-within-7-days −0.5, per-level budget −1.0, spice −0.75, per health goal −0.75, dine-mode mismatch −0.5).
- Mapping a numeric budget (e.g. RM15) to Google's 0–4 price level is left to P7.
