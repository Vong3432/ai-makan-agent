"""recommend_meal end-to-end over MCP: fake LLM + fake places, real local DB."""

import pytest
from fastmcp import Client

from makan import deps
from makan.db.models import NewFeedbackEvent, Profile
from makan.db.repos import BatchRepo, FeedbackRepo, ProfileRepo
from makan.server import create_mcp
from tests.unit.test_recommend_tool import FakeGeocoder, FakePlaces, make_llm, onboarded, place


@pytest.fixture
def dev_user(mcp_user):
    yield mcp_user
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
    llm = make_llm()
    llm.responses["extract_feedback"] = {
        "items": [
            {
                "matched_ref": "b1.1",
                "dish": None,
                "place_name": None,
                "meal_slot": None,
                "tags": ["tasty"],
                "score": 2,
            }
        ],
        "profile_hint": None,
    }
    deps.override_llm(llm)
    deps.override_location(
        deps.LocationDeps(
            FakeGeocoder(), FakePlaces({"laksa": [place("L")], "satay": [place("S")]})
        )  # type: ignore[arg-type]
    )

    async with Client(create_mcp()) as client:
        assert "recommend_meal" in {t.name for t in await client.list_tools()}
        out = (await client.call_tool("recommend_meal", {"location": "Bangsar"})).data
        fb = (await client.call_tool("give_feedback", {"message": "first was great"})).data

    assert out["status"] == "ok" and len(out["options"]) == 3
    batches = await BatchRepo(service, dev_user).recent(1)
    assert [r.dish for r in batches[0].recommendations] == [o["dish"] for o in out["options"]]
    prof = await ProfileRepo(service, dev_user).get()
    assert prof and prof.timezone == "Asia/Kuala_Lumpur"

    first = batches[0].recommendations[0]
    assert fb["recorded"][0]["matched_recommendation"] is True
    events = [e for e in await FeedbackRepo(service, dev_user).list() if e.source == "feedback"]
    assert len(events) == 1 and events[0].recommendation_id == first.id
    assert events[0].score == 2 and "tasty" in events[0].tags
