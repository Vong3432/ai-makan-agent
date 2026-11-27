# P9 — `delete_my_data` & rate-limit switch

**Goal:** privacy controls and a ready-but-off rate limiter.
**Specs:** [MCP Tools](../specs/03-tools.md), [Cost, Safety & Privacy](../specs/08-cost-safety-privacy.md)

## Tasks

- [ ] **P9-T1** Tool `delete_my_data()`: deletes profile, batches, recommendations, feedback, usage rows for the user; caches untouched.
- [ ] **P9-T2** Require confirmation: first call returns a warning + token; second call with `confirm=true` deletes. (Prevents a host LLM deleting on an ambiguous message.)
- [ ] **P9-T3** Rate limiter middleware on LLM-backed tools: increments `usage_counters`; enforced only if `RATE_LIMIT_ENABLED=true`; limit from config (default 30/day).
- [ ] **P9-T4** Friendly "limit reached" response.
- [ ] **P9-T5** Tests: deletion removes all user rows and nothing else; limiter off = no blocking, on = blocks at N+1.

## Done when

- Both behaviours tested; rate limit is **off** by default.
