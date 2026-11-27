-- Atomic per-user daily counter increment. Runs as the caller, so RLS applies.
create function public.increment_usage(p_user_id uuid, p_day date)
returns integer
language sql
security invoker
set search_path = ''
as $$
  insert into public.usage_counters as u (user_id, day, calls)
  values (p_user_id, p_day, 1)
  on conflict (user_id, day) do update set calls = u.calls + 1
  returning u.calls;
$$;
