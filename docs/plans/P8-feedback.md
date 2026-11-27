# P8 — `give_feedback`

**Goal:** free-text feedback updates preferences and influences the next recommendation.
**Specs:** [MCP Tools](../specs/03-tools.md), [Preference Model](../specs/05-preference-model.md)

## Tasks

- [x] **P8-T1** Tool `give_feedback(message)`.
- [x] **P8-T2** Load last N (e.g. 3) batches for context.
- [x] **P8-T3** LLM resolve + extract (P3-T7): matched item or free-standing; tags; score −2..2.
- [x] **P8-T4** Persist `feedback_events` (link `recommendation_id` when matched).
- [x] **P8-T5** Multiple items in one message ("first good, second too oily") → multiple events.
- [x] **P8-T6** Response confirms what was recorded ("Noted: fried rice at Ah Kow +1") so the user can correct a mis-match.
- [x] **P8-T7** Ensure feedback never edits allergies/dietary rules — route those to `update_profile` with a hint.
- [x] **P8-T8** Test: positive feedback on dish X raises its rank in the next `recommend_meal` (subject to repetition rules).

## Done when

- Loop test passes: recommend → feedback → recommend shows the learned preference.

## Implementation notes

- Logic in `tools/feedback.py`; `server.py` wires it. The last 3 batches are shown to the LLM with refs `b{batch}.{position}` (`b1` = newest).
- A matched item takes the shown dish, place and tags (so cuisine and `place:` preferences learn too) plus the LLM's tags; `recommendation_id` is linked. Unknown refs (hallucinated) fall back to free-standing events using the LLM's dish; items with no identifiable dish are skipped. The same item mentioned twice is recorded once. Scores are clamped to −2..2.
- Allergy / diet statements come back as `profile_hint`; the profile is never touched and the message asks the user to say it again so the host calls `update_profile`.
- Loop test (`test_loop_feedback_raises_rank_in_next_recommendation`): +2 on the 3rd-ranked dish → hidden for 3 days by the repeat rule → ranked 1st after.
- **P7 fix found while live-testing:** with a peanut allergy the safety check rejected 5–8 of 8 proposals, leaving 0–1 options. `recommend_meal` now runs one top-up round (new dishes, excluded ones added to the avoid list, only new ones re-checked) when fewer than 3 survive. The filter itself is never relaxed.
- Live-checked with Claude Haiku 5.5: two-item message → two linked events (+2, −1 "oily"), ~1.5–2 s per call; an allergy mention produced a hint and left allergies unchanged.
