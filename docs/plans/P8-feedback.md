# P8 — `give_feedback`

**Goal:** free-text feedback updates preferences and influences the next recommendation.
**Specs:** [MCP Tools](../specs/03-tools.md), [Preference Model](../specs/05-preference-model.md)

## Tasks

- [ ] **P8-T1** Tool `give_feedback(message)`.
- [ ] **P8-T2** Load last N (e.g. 3) batches for context.
- [ ] **P8-T3** LLM resolve + extract (P3-T7): matched item or free-standing; tags; score −2..2.
- [ ] **P8-T4** Persist `feedback_events` (link `recommendation_id` when matched).
- [ ] **P8-T5** Multiple items in one message ("first good, second too oily") → multiple events.
- [ ] **P8-T6** Response confirms what was recorded ("Noted: fried rice at Ah Kow +1") so the user can correct a mis-match.
- [ ] **P8-T7** Ensure feedback never edits allergies/dietary rules — route those to `update_profile` with a hint.
- [ ] **P8-T8** Test: positive feedback on dish X raises its rank in the next `recommend_meal` (subject to repetition rules).

## Done when

- Loop test passes: recommend → feedback → recommend shows the learned preference.
