-- Local dev only: the fixed user used when AUTH_MODE=dev (matches DEV_USER_ID).
insert into auth.users (instance_id, id, aud, role, email, created_at, updated_at)
values (
  '00000000-0000-0000-0000-000000000000',
  '00000000-0000-0000-0000-000000000001',
  'authenticated', 'authenticated', 'dev@makan.local', now(), now()
)
on conflict (id) do nothing;
