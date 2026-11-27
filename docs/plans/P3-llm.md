# P3 — LLM provider interface & prompts

**Goal:** a swappable LLM layer that returns validated structured output for each agent job.
**Specs:** [Architecture](../specs/02-architecture.md), [Recommendation Pipeline](../specs/04-recommendation-pipeline.md), [Preference Model](../specs/05-preference-model.md)

## Tasks

- [ ] **P3-T1** `llm/base.py`: `LLMProvider` protocol with `structured(prompt, schema: type[BaseModel]) -> BaseModel`.
- [ ] **P3-T2** First implementation for the chosen provider (decision D1); model name from config.
- [ ] **P3-T3** `FakeLLM` for tests: returns canned responses keyed by job.
- [ ] **P3-T4** Prompt + schema: **extract profile changes** from free text (allergies, dietary rules, budget, habits, radius, slot windows).
- [ ] **P3-T5** Prompt + schema: **propose candidate dishes** (slot, local context, request, profile summary) → list of dishes with tags + search cuisine.
- [ ] **P3-T6** Prompt + schema: **allergen check** — dish × declared allergens → `likely_contains: list[str]`. Conservative: when unsure, flag.
- [ ] **P3-T7** Prompt + schema: **resolve + extract feedback** — message + recent batches → matched item (or none), dish, place, tags, score −2..2.
- [ ] **P3-T8** Prompt + schema: **write reasons** — one line per option.
- [ ] **P3-T9** Retry once on schema-validation failure; surface a clear error otherwise.
- [ ] **P3-T10** Small eval set (10–20 cases per prompt) runnable with the real model: `make eval`.

## Done when

- All prompts have schemas, unit tests (with `FakeLLM`), and pass the eval set with the real model.
