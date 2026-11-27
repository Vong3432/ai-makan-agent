from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from postgrest.exceptions import APIError

from makan.db.models import GeocodeEntry, NewBatch, NewFeedbackEvent, NewRecommendation, Profile
from makan.db.repos import BatchRepo, CacheRepo, FeedbackRepo, ProfileRepo, UsageRepo


async def test_profile_roundtrip(make_user):
    u = await make_user()
    repo = ProfileRepo(u.client, u.user.user_id)
    assert await repo.get() is None

    saved = await repo.upsert(
        Profile(user_id=UUID(u.user.user_id), allergies=["peanut"], allergies_answered=True)
    )
    assert saved.allergies == ["peanut"]

    saved.default_radius_km = 3
    await repo.upsert(saved)
    got = await repo.get()
    assert got is not None and got.default_radius_km == 3 and got.updated_at is not None


async def test_batches_recent_and_since(make_user):
    u = await make_user()
    repo = BatchRepo(u.client, u.user.user_id)
    for slot in ("breakfast", "lunch"):
        await repo.create(
            NewBatch(meal_slot=slot, location="Bangsar", lat=3.13, lng=101.67),
            [NewRecommendation(position=i, dish=f"{slot}-{i}", tags=["x"]) for i in (2, 1, 3)],
        )

    recent = await repo.recent(limit=1)
    assert len(recent) == 1 and recent[0].meal_slot == "lunch"
    assert [r.position for r in recent[0].recommendations] == [1, 2, 3]

    since = await repo.recommendations_since(datetime.now(UTC) - timedelta(days=1))
    assert len(since) == 6


async def test_feedback_add_and_list(make_user):
    u = await make_user()
    repo = FeedbackRepo(u.client, u.user.user_id)
    await repo.add(
        [
            NewFeedbackEvent(
                raw_message="quite good", dish="fried rice", tags=["fried rice"], score=1
            ),
            NewFeedbackEvent(
                raw_message="too oily", dish="char kway teow", tags=["oily"], score=-1
            ),
        ]
    )
    events = await repo.list()
    assert {e.dish for e in events} == {"fried rice", "char kway teow"}
    with pytest.raises(ValueError):
        NewFeedbackEvent(raw_message="x", score=5)


async def test_usage_increment(make_user):
    u = await make_user()
    repo = UsageRepo(u.client, u.user.user_id)
    today = date.today()
    assert await repo.increment(today) == 1
    assert await repo.increment(today) == 2


async def test_caches(service):
    repo = CacheRepo(service)
    key = f"test-{uuid4().hex}"
    await repo.put_places(key, [{"name": "Ah Kow"}])
    assert await repo.get_places(key, timedelta(days=7)) == [{"name": "Ah Kow"}]
    assert await repo.get_places(key, timedelta(seconds=-1)) is None

    q = f"test-{uuid4().hex}"
    await repo.put_geocode(
        GeocodeEntry(query_norm=q, lat=3.1, lng=101.6, timezone="Asia/Kuala_Lumpur")
    )
    got = await repo.get_geocode(q)
    assert got is not None and got.timezone == "Asia/Kuala_Lumpur"


async def test_rls_isolates_users(make_user):
    a, b = await make_user(), await make_user()
    await ProfileRepo(a.client, a.user.user_id).upsert(
        Profile(user_id=UUID(a.user.user_id), allergies=["shellfish"])
    )
    await FeedbackRepo(a.client, a.user.user_id).add([NewFeedbackEvent(raw_message="x", score=2)])

    # B sees none of A's rows, even with no user_id filter.
    for table in ("profiles", "feedback_events"):
        rows = (await b.client.table(table).select("*").execute()).data
        assert rows == []

    # B cannot write rows as A.
    with pytest.raises(APIError):
        await (
            b.client.table("feedback_events")
            .insert({"user_id": a.user.user_id, "raw_message": "spoof", "score": 2})
            .execute()
        )


async def test_caches_closed_to_users(make_user):
    u = await make_user()
    with pytest.raises(APIError):
        await u.client.table("places_cache").select("*").execute()
