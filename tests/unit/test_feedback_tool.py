import json
import re
from datetime import timedelta

import pytest

from makan.llm.fake import FakeLLM
from makan.tools import feedback as fb_tool
from makan.tools import recommend as rec
from tests.unit.test_profile_tools import USER, MemFeedback, MemProfiles
from tests.unit.test_recommend_tool import (
    DISHES,
    NOW,
    FakeGeocoder,
    FakePlaces,
    MemBatches,
    make_llm,
    onboarded,
    place,
)


async def recommend(batches, feedback, profiles, llm=None, now=NOW):
    batches.now = now
    return await rec.recommend_meal(
        "Bangsar",
        "lunch",
        None,
        user_id=USER,
        llm=llm or make_llm(),
        profiles=profiles,
        feedback=feedback,
        batches=batches,
        geocoder=FakeGeocoder(),
        places=FakePlaces({d["places_query"]: [place(f"p-{d['places_query']}")] for d in DISHES}),
        now=now,
    )


@pytest.fixture
async def shown_once():
    profiles = MemProfiles()
    profiles.p = onboarded()
    batches, feedback = MemBatches(), MemFeedback()
    out = await recommend(batches, feedback, profiles)
    return out, batches, feedback, profiles


def fb_llm(items, profile_hint=None) -> FakeLLM:
    return FakeLLM({"extract_feedback": {"items": items, "profile_hint": profile_hint}})


def item(ref=None, dish=None, score=1, tags=(), place_name=None, meal_slot=None):
    return {
        "matched_ref": ref,
        "dish": dish,
        "place_name": place_name,
        "meal_slot": meal_slot,
        "tags": list(tags),
        "score": score,
    }


async def test_matched_feedback_links_recommendation_and_inherits_place(shown_once):
    out, batches, feedback, _ = shown_once
    first = batches.created[0].recommendations[0]
    llm = fb_llm([item("b1.1", score=1, tags=["good value"])])

    r = await fb_tool.give_feedback(
        "the first one was quite good", llm=llm, feedback=feedback, batches=batches
    )

    (e,) = feedback.events
    assert e.recommendation_id == first.id
    assert e.dish == first.dish and e.place_id == first.place_id
    assert e.meal_slot == "lunch" and e.score == 1 and e.source == "feedback"
    assert "good value" in e.tags and set(first.tags) <= set(e.tags)
    assert r["recorded"][0]["matched_recommendation"] is True
    assert r["message"].startswith(f"Noted: {first.dish} at {first.place_name} +1")

    # The LLM saw the shown items with refs
    shown = json.loads(
        re.search(r"<recently_shown>\n(.*?)\n</recently_shown>", llm.calls[0].user, re.S)[1]
    )
    assert [s["ref"] for s in shown] == ["b1.1", "b1.2", "b1.3"]
    assert "<user_message>\nthe first one was quite good\n</user_message>" in llm.calls[0].user


async def test_multiple_items_in_one_message(shown_once):
    _, batches, feedback, _ = shown_once
    llm = fb_llm([item("b1.1", score=1), item("b1.2", score=-1, tags=["oily"])])
    r = await fb_tool.give_feedback(
        "first good, second too oily", llm=llm, feedback=feedback, batches=batches
    )
    assert [e.score for e in feedback.events] == [1, -1]
    assert len(r["recorded"]) == 2 and "oily" in r["message"]


async def test_free_standing_meal_and_unknown_ref():
    batches, feedback = MemBatches(), MemFeedback()
    llm = fb_llm(
        [
            item(None, dish="Nasi Kerabu", score=2, tags=["herby"], meal_slot="lunch"),
            item("b9.9", dish="Roti John", score=-1),  # hallucinated ref -> free-standing
            item(None, dish=None, score=1),  # nothing identifiable -> skipped
        ]
    )
    r = await fb_tool.give_feedback(
        "had nasi kerabu, loved it; roti john meh", llm=llm, feedback=feedback, batches=batches
    )
    assert [(e.dish, e.score, e.recommendation_id) for e in feedback.events] == [
        ("Nasi Kerabu", 2, None),
        ("Roti John", -1, None),
    ]
    assert feedback.events[0].meal_slot == "lunch"
    assert all(not x["matched_recommendation"] for x in r["recorded"])


async def test_duplicate_mentions_recorded_once(shown_once):
    _, batches, feedback, _ = shown_once
    llm = fb_llm([item("b1.1", score=2), item("b1.1", score=1)])
    await fb_tool.give_feedback(
        "loved it. really good", llm=llm, feedback=feedback, batches=batches
    )
    assert [e.score for e in feedback.events] == [2]


async def test_nothing_recognised():
    feedback = MemFeedback()
    r = await fb_tool.give_feedback("hmm", llm=fb_llm([]), feedback=feedback, batches=MemBatches())
    assert feedback.events == [] and r["recorded"] == []
    assert "couldn't tell" in r["message"]


async def test_allergy_mention_never_changes_profile(shown_once):
    _, batches, feedback, profiles = shown_once
    before = profiles.p.model_copy(deep=True)
    llm = fb_llm([item("b1.1", score=-2)], profile_hint="allergic to shellfish")
    r = await fb_tool.give_feedback(
        "the first one made me sick, I think I'm allergic to prawns",
        llm=llm,
        feedback=feedback,
        batches=batches,
    )
    assert profiles.p == before
    assert r["profile_hint"] == "allergic to shellfish"
    assert "update your profile" in r["message"]
    assert [j.job for j in llm.calls] == ["extract_feedback"]


async def test_empty_message_rejected():
    with pytest.raises(ValueError):
        await fb_tool.give_feedback(
            "  ", llm=fb_llm([]), feedback=MemFeedback(), batches=MemBatches()
        )


async def test_score_clamped(shown_once):
    _, batches, feedback, _ = shown_once
    await fb_tool.give_feedback(
        "best ever", llm=fb_llm([item("b1.1", score=5)]), feedback=feedback, batches=batches
    )
    assert feedback.events[0].score == 2


# ------------------------------------------------------------------ P8-T8 loop


async def test_loop_feedback_raises_rank_in_next_recommendation(shown_once):
    out, batches, feedback, profiles = shown_once
    last = out["options"][-1]
    assert last["position"] == 3

    llm = fb_llm([item("b1.3", score=2, tags=["amazing"])])
    await fb_tool.give_feedback(
        f"the {last['dish']} was amazing", llm=llm, feedback=feedback, batches=batches
    )

    # Within 3 days the repeat rule still hides it ...
    soon = await recommend(batches, feedback, profiles, now=NOW + timedelta(days=1))
    assert last["dish"] not in {o["dish"] for o in soon["options"]}

    # ... after that, the learned preference puts it first.
    later = await recommend(batches, feedback, profiles, now=NOW + timedelta(days=4))
    assert later["options"][0]["dish"] == last["dish"]
