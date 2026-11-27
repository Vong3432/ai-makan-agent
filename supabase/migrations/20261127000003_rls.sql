-- Row Level Security. Per-user tables: owner only. Caches: no policies => service role only.

alter table public.profiles               enable row level security;
alter table public.recommendation_batches enable row level security;
alter table public.recommendations        enable row level security;
alter table public.feedback_events        enable row level security;
alter table public.usage_counters         enable row level security;
alter table public.places_cache           enable row level security;
alter table public.geocode_cache          enable row level security;

do $$
declare
  t text;
begin
  foreach t in array array[
    'profiles', 'recommendation_batches', 'recommendations', 'feedback_events', 'usage_counters'
  ] loop
    execute format(
      'create policy %I on public.%I for all to authenticated
         using ((select auth.uid()) = user_id)
         with check ((select auth.uid()) = user_id)',
      t || '_owner', t
    );
  end loop;
end;
$$;

-- Anonymous clients get nothing anywhere.
revoke all on public.places_cache, public.geocode_cache from anon, authenticated;
