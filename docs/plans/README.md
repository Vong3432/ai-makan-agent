# Implementation Plans

Each plan is a milestone with tracked tasks. Tick a box (`- [x]`) when a task is done. Task IDs (e.g. `P3-T2`) are stable — reference them in commits/PRs.

| Plan | Milestone | Depends on | Status |
|---|---|---|---|
| [P0](P0-scaffold.md) | Project scaffold & local dev loop | — | ✅ |
| [P1](P1-database.md) | Supabase schema, RLS, repositories | P0 | ✅ local (cloud project pending) |
| [P2](P2-auth.md) | OAuth 2.1 via Supabase Auth | P0, P1 | ☐ |
| [P3](P3-llm.md) | LLM provider interface & prompts | P0 | ☐ |
| [P4](P4-location-places.md) | Geocoding, timezone, Places + caches | P1 | ☐ |
| [P5](P5-profile-onboarding.md) | Profile tools & onboarding gate | P1, P3 | ☐ |
| [P6](P6-preference-model.md) | Preference scoring (pure logic) | P0 | ☐ |
| [P7](P7-recommend.md) | `recommend_meal` pipeline | P3, P4, P5, P6 | ☐ |
| [P8](P8-feedback.md) | `give_feedback` | P3, P6, P7 | ☐ |
| [P9](P9-privacy-limits.md) | `delete_my_data`, rate-limit switch | P1 | ☐ |
| [P10](P10-deploy.md) | Cloud Run deploy & host connection | all | ☐ |

## Suggested order

```
P0 ─┬─ P1 ─┬─ P2 ─────────────────────────┐
    │      ├─ P4 ──────┐                  │
    │      └─ P9       │                  │
    ├─ P3 ── P5 ───────┼─ P7 ── P8 ── P10 ┘
    └─ P6 ─────────────┘
```

P2 (auth) can run late: locally we use a **dev-auth mode** (fixed test user) so P3–P9 aren't blocked on OAuth.

## Dev environment (Docker)

- App runs via `docker compose` (dev target of a multi-stage Dockerfile, source mounted, hot reload). No host Python needed.
- Local Supabase runs via `supabase start` (Supabase CLI, Docker-based); the app container reaches it at `host.docker.internal`.
- Tests and lint run inside the app container (`make test`, `make lint`).
- The same Dockerfile's `prod` target is what Cloud Run deploys (P10).

## Target layout

```
ai_makan_agent/
├─ pyproject.toml            # uv-managed
├─ Dockerfile               # multi-stage: dev / prod
├─ compose.yaml             # local dev
├─ Makefile
├─ .env.example
├─ supabase/migrations/      # SQL migrations
├─ src/makan/
│  ├─ server.py              # FastMCP app, tool registration
│  ├─ config.py              # pydantic-settings
│  ├─ auth.py                # Supabase provider / dev-auth
│  ├─ db/                    # supabase client + repositories
│  ├─ llm/                   # provider interface, impls, prompts
│  ├─ location/              # geocode, timezone, places, caches
│  ├─ domain/                # profile, slots, preferences, ranking (pure)
│  └─ tools/                 # one module per MCP tool
└─ tests/
   ├─ unit/
   └─ integration/
```

## Decisions (resolved — see DECISIONS.md #23–26)

| # | Question | Blocks | Recommendation |
|---|---|---|---|
| D1 | Which LLM provider/model? | P3 | Claude Haiku 5.5 (cheap, fast, good structured output) |
| D2 | Geocoding source | P4 | Google Places Text Search (one API key, one bill) — geocoding API is an alternative |
| D3 | Timezone source | P4 | `timezonefinder` offline lib (free) instead of Google Time Zone API |
| D4 | Server DB access under RLS | P1 | Per-user queries use the user's JWT (RLS enforced); caches use service role |
