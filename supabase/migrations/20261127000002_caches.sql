-- Shared caches. Contain no personal data. Server (service role) access only.

create table public.places_cache (
  cache_key   text primary key,          -- geohash + cuisine/type
  payload     jsonb not null,
  fetched_at  timestamptz not null default now()
);

create table public.geocode_cache (
  query_norm  text primary key,
  lat         double precision not null,
  lng         double precision not null,
  timezone    text,
  fetched_at  timestamptz not null default now()
);
