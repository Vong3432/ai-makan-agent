import json
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from makan.db.models import Batch, NewFeedbackEvent, Profile, Recommendation
from makan.domain.budget import budget_to_price_level
from makan.llm.base import LLMError
from makan.llm.fake import FakeLLM
from makan.location.geo import LatLng
from makan.location.geocode import GeoPoint
from makan.location.google import PlacesAPIError
from makan.location.places import Place
from makan.tools import recommend as rec
from tests.unit.test_profile_tools import USER, MemFeedback, MemProfiles

# Wednesday 12:30 in Kuala Lumpur (UTC+8) -> lunch
NOW = datetime(2026, 11, 25, 4, 30, tzinfo=UTC)
KL = GeoPoint("bangsar", 3.13, 101.68, "Asia/Kuala_Lumpur", cached=False)


def dish(name, cuisine, query=None, tags=(), spice=1, price=1, health=()):
    return {
        "dish": name,
        "cuisine": cuisine,
        "places_query": query or name.lower(),
        "tags": list(tags) or [cuisine.lower()],
        "spice_level": spice,
        "typical_price_level": price,
        "violates_health_goals": list(health),
    }


DISHES = [
    dish("Nasi Lemak", "Malay", tags=["malay", "rice", "spicy"]),
    dish("Laksa", "Malay", tags=["malay", "noodles", "soupy"]),
    dish("Chicken Rice", "Chinese", tags=["chinese", "rice", "chicken"]),
    dish("Satay", "Malay", tags=["malay", "grilled"]),
    dish("Banana Leaf Rice", "Indian", tags=["indian", "rice"]),
]


def place(pid, km=0.5, rating=4.3, open_now=None, price=None):
    return Place(
        place_id=pid,
        name=f"Place {pid}",
        lat=3.13,
        lng=101.68,
        rating=rating,
        open_now=open_now,
        price_level=price,
        distance_km=km,
    )


class MemBatches:
    def __init__(self, history: list[tuple[datetime, Recommendation]] | None = None) -> None:
        self.created: list[Batch] = []
        self.history = history or []

    async def create(self, batch, recs):
        bid = uuid4()
        saved = [
            Recommendation(**r.model_dump(), id=uuid4(), batch_id=bid, user_id=UUID(USER))
            for r in recs
        ]
        b = Batch(
            **batch.model_dump(),
            id=bid,
            user_id=UUID(USER),
            created_at=NOW,
            recommendations=saved,
        )
        self.created.append(b)
        return b

    async def recommendations_since(self, since):
        return [(at, r) for at, r in self.history if at >= since]


def shown(dish_name, days_ago, place_id=None) -> tuple[datetime, Recommendation]:
    return (
        NOW - timedelta(days=days_ago),
        Recommendation(
            id=uuid4(),
            batch_id=uuid4(),
            user_id=UUID(USER),
            position=1,
            dish=dish_name,
            place_id=place_id,
        ),
    )


class FakeGeocoder:
    def __init__(self, point: GeoPoint | None = KL) -> None:
        self.point = point
        self.calls: list[str] = []

    async def geocode(self, query):
        self.calls.append(query)
        return self.point


class FakePlaces:
    def __init__(self, by_query: dict[str, list[Place]] | None = None, fail: bool = False):
        self.by_query = by_query or {}
        self.fail = fail
        self.calls: list[tuple[str, float]] = []

    async def find(self, origin: LatLng, cuisine: str, radius_km: float):
        self.calls.append((cuisine, radius_km))
        if self.fail:
            raise PlacesAPIError("boom")
        return list(self.by_query.get(cuisine, []))


def safety(flags: dict[str, list[str]] | None = None, drop: set[str] | None = None):
    """check_safety responder: flags[dish] = allergens; dishes in `drop` are omitted."""
    flags = flags or {}
    drop = drop or set()

    def respond(user: str):
        dishes = json.loads(re.search(r"<dishes>\n(.*?)\n</dishes>", user, re.S)[1])
        return {
            "results": [
                {"dish": d, "likely_contains": flags.get(d, []), "dietary_violations": []}
                for d in dishes
                if d not in drop
            ]
        }

    return respond


def reasons(user: str):
    picks = json.loads(re.search(r"<picks>\n(.*?)\n</picks>", user, re.S)[1])
    return {"reasons": [{"dish": p["dish"], "reason": f"why {p['dish']}"} for p in picks]}


def make_llm(dishes=DISHES, check=None, reasons_fn=reasons) -> FakeLLM:
    return FakeLLM(
        {
            "propose_dishes": {"dishes": dishes},
            "check_safety": check or safety(),
            "write_reasons": reasons_fn,
        }
    )


def onboarded(**kw) -> Profile:
    base = dict(
        user_id=UUID(USER),
        onboarded=True,
        allergies=["peanut"],
        allergies_answered=True,
        dietary_answered=True,
        budget_per_meal=20,
        currency="MYR",
        default_radius_km=3,
    )
    return Profile(**{**base, **kw})


async def run(
    *,
    llm=None,
    profile=None,
    batches=None,
    geocoder=None,
    places=None,
    feedback=None,
    location="Bangsar",
    meal_slot=None,
    request=None,
):
    profiles = MemProfiles()
    profiles.p = profile if profile is not None else onboarded()
    deps = dict(
        llm=llm or make_llm(),
        profiles=profiles,
        feedback=feedback or MemFeedback(),
        batches=batches or MemBatches(),
        geocoder=geocoder or FakeGeocoder(),
        places=places
        or FakePlaces({d["places_query"]: [place(f"p-{d['places_query']}")] for d in DISHES}),
    )
    out = await rec.recommend_meal(location, meal_slot, request, user_id=USER, now=NOW, **deps)
    return out, deps


# ---------------------------------------------------------------------- happy path


async def test_happy_path_three_options_with_places():
    out, d = await run()
    assert out["status"] == "ok"
    assert out["meal_slot"] == "lunch"  # 12:30 local
    assert out["radius_km"] == 3
    opts = out["options"]
    assert [o["position"] for o in opts] == [1, 2, 3]
    assert len({o["dish"] for o in opts}) == 3
    assert all(o["place"] and o["place"]["name"].startswith("Place p-") for o in opts)
    assert all(o["reason"].startswith("why ") for o in opts)
    assert sum(o["is_explore"] for o in opts) == 1  # one explore pick
    assert all("confirm with the vendor" in o["allergen_note"] for o in opts)
    assert "confirm with the vendor" in out["message"]
    assert out["suggested_radius_km"] is None

    # persisted, and timezone saved to the profile
    (batch,) = d["batches"].created
    assert batch.meal_slot == "lunch" and batch.location == "Bangsar"
    assert [r.dish for r in batch.recommendations] == [o["dish"] for o in opts]
    assert all(r.place_id for r in batch.recommendations)
    assert out["batch_id"] == str(batch.id)
    assert d["profiles"].p.timezone == "Asia/Kuala_Lumpur"


async def test_explicit_slot_and_preferences_drive_ranking():
    fb = MemFeedback()
    await fb.add(
        [
            NewFeedbackEvent(
                raw_message="x", source="profile", dish="laksa", tags=["laksa"], score=2
            ),
            NewFeedbackEvent(raw_message="x", dish="soupy", tags=["soupy", "noodles"], score=2),
        ]
    )
    out, _ = await run(feedback=fb, meal_slot="Dinner")
    assert out["meal_slot"] == "dinner"
    assert out["options"][0]["dish"] == "Laksa"


async def test_no_allergies_skips_note_and_safety_call_when_no_rules():
    out, d = await run(profile=onboarded(allergies=[]))
    assert all(o["allergen_note"] is None for o in out["options"])
    assert "check_safety" not in [c.job for c in d["llm"].calls]


# ---------------------------------------------------------------------- safety


async def test_allergen_flagged_dishes_never_returned():
    llm = make_llm(check=safety({"Satay": ["peanut"], "Nasi Lemak": ["peanut"]}))
    out, _ = await run(llm=llm)
    dishes = {o["dish"] for o in out["options"]}
    assert not dishes & {"Satay", "Nasi Lemak"}
    assert out["excluded_for_safety"] == 2


async def test_unchecked_dish_is_excluded():
    llm = make_llm(check=safety(drop={"Laksa", "Chicken Rice"}))
    out, _ = await run(llm=llm)
    assert not {o["dish"] for o in out["options"]} & {"Laksa", "Chicken Rice"}


async def test_dietary_rule_unchecked_dish_excluded_even_without_allergies():
    llm = make_llm(check=safety(drop={"Satay"}))
    out, _ = await run(llm=llm, profile=onboarded(allergies=[], dietary_rules=["halal"]))
    assert "Satay" not in {o["dish"] for o in out["options"]}


async def test_all_unsafe_returns_no_safe_options():
    llm = make_llm(check=safety({d["dish"]: ["peanut"] for d in DISHES}))
    out, d = await run(llm=llm)
    assert out["status"] == "no_safe_options"
    assert d["batches"].created == []


# ---------------------------------------------------------------------- fallback


async def test_no_places_falls_back_to_dish_only_and_offers_wider_radius():
    out, d = await run(places=FakePlaces({}))
    assert out["status"] == "ok" and out["no_places_found"]
    assert len(out["options"]) == 3 and all(o["place"] is None for o in out["options"])
    assert out["suggested_radius_km"] == 6
    assert "within 6 km" in out["message"]
    assert all(r.place_id is None for r in d["batches"].created[0].recommendations)


async def test_places_api_error_degrades_to_dish_only():
    out, _ = await run(places=FakePlaces(fail=True))
    assert out["status"] == "ok" and out["no_places_found"]


async def test_partial_places_prefers_dishes_with_a_place():
    out, _ = await run(places=FakePlaces({"laksa": [place("L")], "satay": [place("S")]}))
    with_place = [o for o in out["options"] if o["place"]]
    assert {o["dish"] for o in with_place} == {"Laksa", "Satay"}
    assert not out["no_places_found"]


async def test_closed_and_low_rated_places_skipped_when_eating_now():
    places = FakePlaces(
        {
            "laksa": [place("closed", open_now=False, rating=4.9), place("open", km=1.5)],
            "satay": [place("bad", rating=2.9)],
        }
    )
    out, _ = await run(places=places)
    by_dish = {o["dish"]: o["place"] for o in out["options"]}
    if "Laksa" in by_dish:
        assert by_dish["Laksa"]["place_id"] == "open"
    if "Satay" in by_dish:
        assert by_dish["Satay"] is None


async def test_closed_now_ignored_for_a_later_slot():
    places = FakePlaces({"laksa": [place("closed", open_now=False)]})
    llm = make_llm(dishes=[DISHES[1]])
    out, _ = await run(places=places, llm=llm, meal_slot="dinner")
    assert out["options"][0]["place"]["place_id"] == "closed"
    assert out["options"][0]["place"]["open_now"] is None  # not "closed now" for later
    assert "closed now" not in out["message"]


# ---------------------------------------------------------------------- variety


async def test_dish_shown_recently_is_not_repeated():
    batches = MemBatches([shown("Laksa", 1), shown("Satay", 2)])
    out, d = await run(batches=batches)
    assert not {o["dish"] for o in out["options"]} & {"Laksa", "Satay"}
    # and the LLM was told to avoid them
    assert '"laksa"' in d["llm"].calls[0].user and '"satay"' in d["llm"].calls[0].user


async def test_explicitly_requested_dish_may_repeat():
    batches = MemBatches([shown("Laksa", 1)])
    out, _ = await run(batches=batches, request="I really want laksa again")
    assert "Laksa" in {o["dish"] for o in out["options"]}


async def test_recent_place_swapped_for_another():
    batches = MemBatches([shown("Something else", 1, place_id="L1")])
    places = FakePlaces({"laksa": [place("L1", rating=4.9), place("L2", rating=4.0)]})
    out, _ = await run(batches=batches, places=places, llm=make_llm(dishes=[DISHES[1]]))
    assert out["options"][0]["place"]["place_id"] == "L2"


async def test_everything_repeated_returns_no_options():
    batches = MemBatches([shown(d["dish"], 1) for d in DISHES])
    out, _ = await run(batches=batches)
    assert out["status"] == "no_options"


# ---------------------------------------------------------------------- context


async def test_request_radius_and_place_query_cap():
    many = [dish(f"Dish {i}", "Malay", query=f"q{i}") for i in range(8)]
    places = FakePlaces({})
    await run(llm=make_llm(dishes=many), places=places, request="walking distance")
    assert len(places.calls) == rec.MAX_PLACE_QUERIES
    assert {r for _, r in places.calls} == {1.0}


async def test_location_not_found():
    out, d = await run(geocoder=FakeGeocoder(None))
    assert out["status"] == "location_not_found"
    assert d["llm"].calls == []


async def test_needs_onboarding_before_anything_else():
    profile = Profile(user_id=UUID(USER))
    out, d = await run(profile=profile)
    assert out["status"] == "needs_onboarding"
    assert len(out["onboarding_questions"]) == 6
    assert d["llm"].calls == [] and d["geocoder"].calls == []


@pytest.mark.parametrize(("location", "slot"), [("  ", None), ("Bangsar", "brunch")])
async def test_invalid_input(location, slot):
    with pytest.raises(ValueError):
        await run(location=location, meal_slot=slot)


async def test_reason_failure_uses_fallback_text():
    def boom(_):
        raise LLMError("nope")

    out, _ = await run(llm=make_llm(reasons_fn=boom))
    assert out["status"] == "ok"
    assert all(o["reason"] and not o["reason"].startswith("why") for o in out["options"])


async def test_duplicate_proposals_are_merged():
    out, _ = await run(llm=make_llm(dishes=[DISHES[0], DISHES[0], DISHES[1]]))
    assert sorted(o["dish"] for o in out["options"]) == ["Laksa", "Nasi Lemak"]


# ---------------------------------------------------------------------- budget


@pytest.mark.parametrize(
    ("budget", "currency", "level"),
    [
        (10, "MYR", 1),
        (15, "myr", 1),
        (20, "MYR", 2),
        (80, "MYR", 3),
        (500, "MYR", 4),
        (20, "XYZ", None),
        (None, "MYR", None),
        (20, None, None),
        (0, "MYR", None),
    ],
)
def test_budget_to_price_level(budget, currency, level):
    assert budget_to_price_level(budget, currency) == level
