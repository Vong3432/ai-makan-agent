"""recommend_meal end-to-end over MCP: fake LLM + fake places, real local DB."""

import pytest
from fastmcp import Client

from makan import deps
from makan.config import get_settings
from makan.db.models import NewFeedbackEvent, Profile
from makan.db.repos import BatchRepo, FeedbackRepo, ProfileRepo
from makan.server import create_mcp
from tests.unit.test_recommend_tool import FakeGeocoder, FakePlaces, make_llm, onboarded, place


@pytest.fixture
async def dev_user(service):
    uid = get_settings().dev_user_id

    async def wipe():
        for t in ("recommendation_batches", "feedback_events", "profiles"):
            await service.table(t).delete().eq("user_id", uid).execute()

    await wipe()
    yield uid
    await wipe()
    deps.override_llm(None)
    deps.override_location(None)


async def test_recommend_meal_over_mcp(service, dev_user):
    await ProfileRepo(service, dev_user).upsert(
        Profile(**onboarded().model_dump() | {"user_id": dev_user})
    )
    await FeedbackRepo(service, dev_user).add(
        [
            NewFeedbackEvent(raw_message="x", source="profile", dish=d, tags=[d], score=s)
            for d, s in [
                ("laksa", 2),
                ("satay", 2),
                ("sushi", 2),
                ("okra", -2),
                ("liver", -2),
                ("durian", -2),
            ]
        ]
    )
    deps.override_llm(make_llm())
    deps.override_location(
        deps.LocationDeps(
            FakeGeocoder(), FakePlaces({"laksa": [place("L")], "satay": [place("S")]})
        )  # type: ignore[arg-type]
    )

    async with Client(create_mcp()) as client:
        assert "recommend_meal" in {t.name for t in await client.list_tools()}
        out = (await client.call_tool("recommend_meal", {"location": "Bangsar"})).data

    assert out["status"] == "ok" and len(out["options"]) == 3
    batches = await BatchRepo(service, dev_user).recent(1)
    assert [r.dish for r in batches[0].recommendations] == [o["dish"] for o in out["options"]]
    prof = await ProfileRepo(service, dev_user).get()
    assert prof and prof.timezone == "Asia/Kuala_Lumpur"
