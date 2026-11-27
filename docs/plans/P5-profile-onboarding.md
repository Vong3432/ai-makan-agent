# P5 — Profile tools & onboarding gate

**Goal:** users can set and view their profile through chat, and no recommendation happens before onboarding is complete.
**Specs:** [MCP Tools](../specs/03-tools.md), [Onboarding & Profile](../specs/06-onboarding-and-profile.md)

## Tasks

- [x] **P5-T1** `domain/profile.py`: Profile model, hard vs soft fields, `is_onboarded()` (allergies answered — "none" counts — dietary rules, 3 loves, 3 dislikes, budget, radius).
- [x] **P5-T2** `domain/slots.py`: default slot windows, user overrides, `infer_slot(local_time)` incl. supper wrapping past midnight.
- [x] **P5-T3** Tool `update_profile(message)`: LLM extract (P3-T4) → merge → save → response echoes allergy/diet changes for confirmation.
- [x] **P5-T4** Loves/dislikes from onboarding are seeded as feedback events (+2 / −2) so the preference model uses them.
- [x] **P5-T5** Tool `get_profile()`: profile + top 5 likes / top 5 dislikes from the preference model.
- [x] **P5-T6** Onboarding gate helper used by `recommend_meal`: returns the question set listing only missing items.
- [x] **P5-T7** Tests: slot inference edge cases (00:30 → supper), onboarding completeness, allergy removal requires explicit statement.

## Done when

- A new user can onboard entirely via `update_profile` and see it in `get_profile`.

## Implementation notes

- Migration `0005_feedback_source.sql`: `feedback_events.source` = `feedback` | `profile`. Loves/dislikes stated via `update_profile` are stored as `profile` events (+2 / −2); onboarding counts **distinct** profile-sourced dishes (saying "I love laksa" 3× counts once).
- `allergies_answered` / `dietary_answered` flags make "none" a valid onboarding answer.
- "No allergies" never clears existing allergies; the response asks the user to remove them explicitly. Allergy/diet changes are echoed as `safety_changes` and the tool description tells the host to ask for confirmation.
- Slot inference: time inside a window → that slot; in a gap → next slot to start (e.g. 10:30 → lunch, 03:00 → breakfast). Malformed overrides are ignored.
- Tool logic lives in `tools/profile.py` (testable with in-memory fakes); `server.py` only wires dependencies (`deps.py`, which also allows an LLM override in tests).
- Live-checked against Claude Haiku 5.5 over MCP: 3-message onboarding, ~2–3 s per call.
