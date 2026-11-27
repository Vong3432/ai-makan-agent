"""Supabase client factories.

- `user_client`: per-user tables. Uses the caller's JWT so Postgres RLS is enforced.
  In dev-auth mode there is no JWT, so it falls back to the service role; repositories
  always filter by user_id explicitly, so behaviour is the same.
- `service_client`: shared caches (no personal data), service role only.
"""

from supabase import AsyncClient, AsyncClientOptions, acreate_client

from makan.auth import CurrentUser
from makan.config import get_settings

_service: AsyncClient | None = None


async def service_client() -> AsyncClient:
    global _service
    if _service is None:
        s = get_settings()
        _service = await acreate_client(
            s.supabase_url, s.supabase_service_role_key.get_secret_value()
        )
    return _service


async def user_client(user: CurrentUser) -> AsyncClient:
    if user.access_token is None:
        return await service_client()
    s = get_settings()
    return await acreate_client(
        s.supabase_url,
        s.supabase_anon_key.get_secret_value(),
        options=AsyncClientOptions(
            headers={"Authorization": f"Bearer {user.access_token}"},
            auto_refresh_token=False,
            persist_session=False,
        ),
    )


def reset_clients() -> None:
    """For tests."""
    global _service
    _service = None
