"""Integration fixtures: real local Supabase (`make db-up`). Skipped if unreachable."""

import uuid
from dataclasses import dataclass

import httpx
import pytest
from supabase import AsyncClient, acreate_client

from makan.auth import CurrentUser
from makan.config import get_settings
from makan.db import client as db_client


@dataclass
class TestUser:
    user: CurrentUser
    client: AsyncClient


def _supabase_up() -> bool:
    try:
        httpx.get(f"{get_settings().supabase_url}/auth/v1/health", timeout=2)
        return True
    except httpx.HTTPError:
        return False


@pytest.fixture(autouse=True)
def _require_supabase():
    if not _supabase_up() or not get_settings().supabase_service_role_key.get_secret_value():
        pytest.skip("local Supabase not running / keys not set (run `make db-up`)")
    db_client.reset_clients()


@pytest.fixture
async def service() -> AsyncClient:
    return await db_client.service_client()


@pytest.fixture
async def make_user(service: AsyncClient):
    """Create real auth users with JWTs; deleted afterwards (data cascades)."""
    created: list[str] = []
    s = get_settings()

    async def _make() -> TestUser:
        email = f"test-{uuid.uuid4().hex[:10]}@makan.local"
        password = uuid.uuid4().hex
        res = await service.auth.admin.create_user(
            {"email": email, "password": password, "email_confirm": True}
        )
        created.append(res.user.id)
        anon = await acreate_client(s.supabase_url, s.supabase_anon_key.get_secret_value())
        session = (
            await anon.auth.sign_in_with_password({"email": email, "password": password})
        ).session
        user = CurrentUser(user_id=res.user.id, access_token=session.access_token)
        return TestUser(user=user, client=await db_client.user_client(user))

    yield _make
    for uid in created:
        await service.auth.admin.delete_user(uid)
