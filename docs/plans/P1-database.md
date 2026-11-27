# P1 — Supabase schema, RLS, repositories

**Goal:** all tables from the data model exist with RLS, and the app reads/writes them through a thin repository layer.
**Specs:** [Data Model](../specs/07-data-model.md), [Cost, Safety & Privacy](../specs/08-cost-safety-privacy.md)

## Tasks

- [ ] **P1-T1** ~~`supabase init` in repo; local stack via `supabase start`; `make db-up`/`make db-reset`~~ ✅ done. **Remaining:** create the Supabase cloud project (needed by P2/P10).
- [x] **P1-T2** Migration `0001_core.sql`: `profiles`, `recommendation_batches`, `recommendations`, `feedback_events`, `usage_counters`.
- [x] **P1-T3** Migration `0002_caches.sql`: `places_cache`, `geocode_cache`.
- [x] **P1-T4** Migration `0003_rls.sql`: enable RLS on all per-user tables; policy `user_id = auth.uid()` for select/insert/update/delete. Caches: no user access, service role only.
- [x] **P1-T5** Indexes: `feedback_events(user_id, created_at)`, `recommendations(user_id, batch_id)`, `recommendation_batches(user_id, created_at)`.
- [x] **P1-T6** `db/client.py`: factory for (a) user-scoped client using the caller's JWT, (b) service-role client for caches. Dev-auth mode uses service role + explicit `user_id` filter.
- [x] **P1-T7** Repositories: `ProfileRepo`, `BatchRepo`, `FeedbackRepo`, `UsageRepo`, `CacheRepo` — typed with pydantic models.
- [x] **P1-T7b** Migration `0004_usage_fn.sql`: atomic `increment_usage()` RPC (security invoker, RLS applies). Seed `supabase/seed.sql` with the dev-mode user.
- [x] **P1-T8** Integration tests (run in the `app` container) against local Supabase: CRUD per repo + an RLS test proving user A cannot read user B's rows.

## Done when

- `supabase db reset` applies cleanly.
- RLS cross-user test passes.
