-- Core per-user tables. See docs/specs/07-data-model.md.
-- Every table cascades from auth.users so deleting a user removes all their data.

create table public.profiles (
  user_id            uuid primary key references auth.users (id) on delete cascade,
  onboarded          boolean not null default false,
  allergies          text[]  not null default '{}',
  allergies_answered boolean not null default false,  -- "none" is a valid answer
  dietary_rules      text[]  not null default '{}',
  dietary_answered   boolean not null default false,
  budget_per_meal    numeric,
  currency           text,
  spice_tolerance    smallint check (spice_tolerance between 0 and 4),
  skipped_meals      text[]  not null default '{}',
  dine_preference    text check (dine_preference in ('dine_in', 'delivery', 'either')),
  health_goals       text[]  not null default '{}',
  default_radius_km  numeric check (default_radius_km > 0),
  slot_windows       jsonb   not null default '{}'::jsonb,
  timezone           text,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now()
);

create table public.recommendation_batches (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users (id) on delete cascade,
  created_at  timestamptz not null default now(),
  meal_slot   text not null check (meal_slot in ('breakfast', 'lunch', 'tea', 'dinner', 'supper')),
  location    text not null,
  lat         double precision,
  lng         double precision
);

create table public.recommendations (
  id          uuid primary key default gen_random_uuid(),
  batch_id    uuid not null references public.recommendation_batches (id) on delete cascade,
  user_id     uuid not null references auth.users (id) on delete cascade,
  position    smallint not null check (position between 1 and 3),
  dish        text not null,
  place_id    text,
  place_name  text,
  tags        text[] not null default '{}',
  is_explore  boolean not null default false,
  unique (batch_id, position)
);

create table public.feedback_events (
  id                 uuid primary key default gen_random_uuid(),
  user_id            uuid not null references auth.users (id) on delete cascade,
  created_at         timestamptz not null default now(),
  raw_message        text not null,
  recommendation_id  uuid references public.recommendations (id) on delete set null,
  dish               text,
  place_id           text,
  meal_slot          text,
  tags               text[] not null default '{}',
  score              smallint not null check (score between -2 and 2)
);

-- Rate limiting; enforcement is off by default (RATE_LIMIT_ENABLED).
create table public.usage_counters (
  user_id  uuid not null references auth.users (id) on delete cascade,
  day      date not null,
  calls    integer not null default 0,
  primary key (user_id, day)
);

create index feedback_events_user_created_idx on public.feedback_events (user_id, created_at desc);
create index recommendation_batches_user_created_idx on public.recommendation_batches (user_id, created_at desc);
create index recommendations_user_batch_idx on public.recommendations (user_id, batch_id);

create function public.touch_updated_at() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create trigger profiles_touch_updated_at
before update on public.profiles
for each row execute function public.touch_updated_at();
