# Data Model

## Data model (draft, Postgres)

All per-user tables have `user_id uuid references auth.users` and RLS policy `user_id = auth.uid()`.

```sql
profiles (
  user_id            uuid primary key,
  onboarded          boolean default false,
  allergies          text[],
  dietary_rules      text[],
  budget_per_meal    numeric,
  currency           text,
  spice_tolerance    smallint,      -- 0..4
  skipped_meals      text[],
  dine_preference    text,          -- dine_in | delivery | either
  health_goals       text[],
  default_radius_km  numeric,
  slot_windows       jsonb,         -- overrides of defaults
  timezone           text,
  updated_at         timestamptz
)

recommendation_batches (
  id          uuid primary key,
  user_id     uuid,
  created_at  timestamptz,
  meal_slot   text,
  location    text,
  lat         double precision,
  lng         double precision
)

recommendations (
  id          uuid primary key,
  batch_id    uuid references recommendation_batches,
  user_id     uuid,
  position    smallint,            -- 1..3
  dish        text,
  place_id    text null,           -- Google place id
  place_name  text null,
  tags        text[],
  is_explore  boolean
)

feedback_events (
  id                 uuid primary key,
  user_id            uuid,
  created_at         timestamptz,
  raw_message        text,
  recommendation_id  uuid null,    -- resolved server-side, may be null
  dish               text,
  place_id           text null,
  meal_slot          text null,
  tags               text[],
  score              smallint      -- -2..2
)

usage_counters (                   -- rate limiting; disabled during testing
  user_id  uuid,
  day      date,
  calls    int,
  primary key (user_id, day)
)

-- Shared, no personal data, no RLS by user
places_cache (
  cache_key   text primary key,    -- geohash + cuisine/type
  payload     jsonb,
  fetched_at  timestamptz          -- TTL ~7 days
)

geocode_cache (
  query_norm  text primary key,
  lat         double precision,
  lng         double precision,
  timezone    text,
  fetched_at  timestamptz
)
```

