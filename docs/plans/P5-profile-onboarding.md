# P5 — Profile tools & onboarding gate

**Goal:** users can set and view their profile through chat, and no recommendation happens before onboarding is complete.
**Specs:** [MCP Tools](../specs/03-tools.md), [Onboarding & Profile](../specs/06-onboarding-and-profile.md)

## Tasks

- [ ] **P5-T1** `domain/profile.py`: Profile model, hard vs soft fields, `is_onboarded()` (allergies answered — "none" counts — dietary rules, 3 loves, 3 dislikes, budget, radius).
- [ ] **P5-T2** `domain/slots.py`: default slot windows, user overrides, `infer_slot(local_time)` incl. supper wrapping past midnight.
- [ ] **P5-T3** Tool `update_profile(message)`: LLM extract (P3-T4) → merge → save → response echoes allergy/diet changes for confirmation.
- [ ] **P5-T4** Loves/dislikes from onboarding are seeded as feedback events (+2 / −2) so the preference model uses them.
- [ ] **P5-T5** Tool `get_profile()`: profile + top 5 likes / top 5 dislikes from the preference model.
- [ ] **P5-T6** Onboarding gate helper used by `recommend_meal`: returns the question set listing only missing items.
- [ ] **P5-T7** Tests: slot inference edge cases (00:30 → supper), onboarding completeness, allergy removal requires explicit statement.

## Done when

- A new user can onboard entirely via `update_profile` and see it in `get_profile`.
