# P3 — LLM provider interface & prompts

**Goal:** a swappable LLM layer that returns validated structured output for each agent job.
**Specs:** [Architecture](../specs/02-architecture.md), [Recommendation Pipeline](../specs/04-recommendation-pipeline.md), [Preference Model](../specs/05-preference-model.md)

## Tasks

- [x] **P3-T1** `llm/base.py`: `LLMProvider` protocol with `structured(prompt, schema: type[BaseModel]) -> BaseModel`.
- [x] **P3-T2** First implementation for the chosen provider (decision D1); model name from config.
- [x] **P3-T3** `FakeLLM` for tests: returns canned responses keyed by job.
- [x] **P3-T4** Prompt + schema: **extract profile changes** from free text (allergies, dietary rules, budget, habits, radius, slot windows).
- [x] **P3-T5** Prompt + schema: **propose candidate dishes** (slot, local context, request, profile summary) → list of dishes with tags + search cuisine.
- [x] **P3-T6** Prompt + schema: **allergen check** — dish × declared allergens → `likely_contains: list[str]`. Conservative: when unsure, flag.
- [x] **P3-T7** Prompt + schema: **resolve + extract feedback** — message + recent batches → matched item (or none), dish, place, tags, score −2..2.
- [x] **P3-T8** Prompt + schema: **write reasons** — one line per option.
- [x] **P3-T9** Retry once on schema-validation failure; surface a clear error otherwise.
- [x] **P3-T10** Eval set runnable with the real model: `make eval` — 22 cases, all passing (2026-11-27, ~1 min). Grow toward 10–20 cases per job over time.

## Done when

- All prompts have schemas, unit tests (with `FakeLLM`), and pass the eval set with the real model.

## Implementation notes

- Model: `claude-haiku-5-5` via `messages.parse(output_format=<pydantic model>)`, `effort: low`, system prompt marked `cache_control` (short prompts may fall below the minimum cacheable size; harmless).
- Allergen and dietary checks are **one** job (`check_safety`) to halve calls.
- Free text is wrapped in `<user_message>` tags; every system prompt says tagged text is data, not instructions.
- Refusal / truncation / invalid output → one retry → `LLMError`. Haiku has no server-side refusal fallback.
- `make eval` is excluded from `make test` (pytest marker `eval`).
- **Schema limits:** structured outputs allow max 24 optional and 16 union-typed params per request, and compile each new schema (~20s first use, cached 24h). All LLM output models extend `LLMOut`, which publishes every field as required; a unit test enforces the limits. Client timeout 60s.
- **Safety-check risk evals (added after P7/P8 live runs):** dishes that really contain peanut (must always flag), false-alarm rate on peanut-free dishes (≤ 2/8), consistency of borderline verdicts over 3 runs, and "≥ 3 of 8 proposals survive" for a peanut-allergic, halal user. Findings: the original check flagged *all* dishes in a list of only peanut-free dishes (verdicts depended on the other dishes in the list) and rejected halal-compatible dishes because "some stalls may use lard".
- Fixes: `DishCheck.evidence` comes before the verdicts and must name the ingredient behind each flag; flags need a common ingredient (cross-contact / shared equipment / frying oil alone don't count; the vendor note covers those); dietary rules judged on the dish's own ingredients, not stall certification; the proposer is told to apply the same standard; `check_safety` runs at effort `medium` (`JOB_EFFORT` in `anthropic_provider.py`) because Haiku 5.5 rejects non-default `temperature`.
- Results over 3 runs: true positives pass 3/3; false alarms 2/8 each run (was 8/8); proposal survivors 6, 7, 4 of 8 (was 2); consistency passes 1/3: one genuinely ambiguous dish (nasi goreng kampung, beef rendang) flips per run. Open item.
