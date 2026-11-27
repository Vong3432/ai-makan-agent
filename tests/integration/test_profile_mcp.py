"""End-to-end through the MCP server (dev-auth user) with a fake LLM and the real local DB."""

import pytest
from fastmcp import Client

from makan import deps
from makan.config import get_settings
from makan.llm.fake import FakeLLM
from makan.server import create_mcp


@pytest.fixture
async def clean_dev_user(service):
    uid = get_settings().dev_user_id

    async def wipe():
        await service.table("feedback_events").delete().eq("user_id", uid).execute()
        await service.table("profiles").delete().eq("user_id", uid).execute()

    await wipe()
    yield
    await wipe()
    deps.override_llm(None)


async def test_update_and_get_profile_over_mcp(clean_dev_user):
    deps.override_llm(
        FakeLLM(
            {
                "extract_profile": {
                    "add_allergies": ["peanut"],
                    "no_dietary_rules": True,
                    "loves": ["laksa", "nasi lemak", "roti canai"],
                    "dislikes": ["durian", "okra", "liver"],
                    "budget_per_meal": 20,
                    "currency": "MYR",
                    "default_radius_km": 3,
                }
            }
        )
    )
    async with Client(create_mcp()) as client:
        tools = {t.name for t in await client.list_tools()}
        assert {"update_profile", "get_profile"} <= tools

        r = (await client.call_tool("update_profile", {"message": "everything at once"})).data
        assert r["onboarding_complete"] is True
        assert "added allergy: peanut" in r["safety_changes"]

        p = (await client.call_tool("get_profile", {})).data
        assert p["profile"]["allergies"] == ["peanut"] and p["profile"]["onboarded"]
        assert set(p["top_likes"]) == {"laksa", "nasi lemak", "roti canai"}
