from datetime import UTC, datetime
from uuid import uuid4

from makan.db.models import FeedbackEvent, NewFeedbackEvent, Profile
from makan.llm.fake import FakeLLM
from makan.tools import profile as tools

NOW = datetime(2026, 11, 27, 12, tzinfo=UTC)
USER = "00000000-0000-0000-0000-0000000000aa"


class MemProfiles:
    def __init__(self) -> None:
        self.p: Profile | None = None

    async def get(self):
        return self.p

    async def upsert(self, profile):
        self.p = profile.model_copy(deep=True)
        return self.p


class MemFeedback:
    def __init__(self) -> None:
        self.events: list[FeedbackEvent] = []

    async def add(self, events: list[NewFeedbackEvent]):
        saved = [
            FeedbackEvent(**{**e.model_dump(), "created_at": NOW}, id=uuid4(), user_id=USER)
            for e in events
        ]
        self.events += saved
        return saved

    async def list(self, since=None):
        return list(self.events)

    async def profile_item_counts(self):
        prof = [e for e in self.events if e.source == "profile" and e.dish]
        return (
            len({e.dish.lower() for e in prof if e.score > 0}),
            len({e.dish.lower() for e in prof if e.score < 0}),
        )


def llm_returning(**changes) -> FakeLLM:
    return FakeLLM({"extract_profile": changes})


async def call(message, llm, profiles, feedback):
    return await tools.update_profile(
        message, user_id=USER, llm=llm, profiles=profiles, feedback=feedback
    )


async def test_onboarding_flow_completes_over_several_messages():
    profiles, feedback = MemProfiles(), MemFeedback()

    gate = await tools.onboarding_gate(USER, profiles, feedback)
    assert len(gate) == 6

    r = await call(
        "allergic to prawns, halal",
        llm_returning(add_allergies=["shellfish"], add_dietary_rules=["halal"]),
        profiles,
        feedback,
    )
    assert r["safety_changes"] == ["added allergy: shellfish", "added dietary rule: halal"]
    assert "Please confirm" in r["message"] and not r["onboarding_complete"]
    assert len(r["onboarding_questions"]) == 4

    r = await call(
        "love laksa, satay, sushi; hate durian, okra, liver",
        llm_returning(loves=["laksa", "satay", "sushi"], dislikes=["durian", "okra", "liver"]),
        profiles,
        feedback,
    )
    assert len(r["onboarding_questions"]) == 2
    assert {e.score for e in feedback.events} == {2, -2}

    r = await call(
        "RM15, walking distance",
        llm_returning(budget_per_meal=15, currency="MYR", default_radius_km=1),
        profiles,
        feedback,
    )
    assert r["onboarding_complete"] and r["onboarding_questions"] == []
    assert "ready" in r["message"]
    assert await tools.onboarding_gate(USER, profiles, feedback) == []


async def test_repeated_love_counts_once():
    profiles, feedback = MemProfiles(), MemFeedback()
    for _ in range(3):
        await call("I love laksa", llm_returning(loves=["laksa"]), profiles, feedback)
    assert await feedback.profile_item_counts() == (1, 0)


async def test_nothing_changed_message():
    r = await call("hello", llm_returning(), MemProfiles(), MemFeedback())
    assert r["message"].startswith("Nothing in that message changed your profile.")


async def test_get_profile_summarises_likes():
    profiles, feedback = MemProfiles(), MemFeedback()
    await call(
        "love laksa, hate okra",
        llm_returning(loves=["laksa"], dislikes=["okra"]),
        profiles,
        feedback,
    )
    out = await tools.get_profile(user_id=USER, profiles=profiles, feedback=feedback, now=NOW)
    assert out["top_likes"] == ["laksa"] and out["top_dislikes"] == ["okra"]
    assert not out["onboarding_complete"] and out["onboarding_questions"]
    assert "user_id" not in out["profile"]


async def test_get_profile_for_new_user():
    out = await tools.get_profile(
        user_id=USER, profiles=MemProfiles(), feedback=MemFeedback(), now=NOW
    )
    assert out["top_likes"] == [] and len(out["onboarding_questions"]) == 6
