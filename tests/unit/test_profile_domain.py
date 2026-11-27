from uuid import uuid4

from makan.db.models import Profile
from makan.domain.profile import apply_changes, onboarding_status
from makan.llm.jobs import ProfileChanges, SlotWindow


def profile(**kw) -> Profile:
    return Profile(user_id=uuid4(), **kw)


def test_allergies_merge_normalise_and_flag_answered():
    r = apply_changes(
        profile(allergies=["peanut"]), ProfileChanges(add_allergies=["Shellfish", "peanut "])
    )
    assert r.profile.allergies == ["peanut", "shellfish"]
    assert r.profile.allergies_answered
    assert r.safety_changes == ["added allergy: shellfish"]


def test_allergy_removed_only_when_explicitly_listed():
    p = profile(allergies=["peanut"], allergies_answered=True)
    assert apply_changes(p, ProfileChanges(loves=["satay"])).profile.allergies == ["peanut"]
    r = apply_changes(p, ProfileChanges(remove_allergies=["Peanut"]))
    assert r.profile.allergies == [] and r.safety_changes == ["removed allergy: peanut"]


def test_no_allergies_does_not_clear_existing_ones():
    r = apply_changes(profile(allergies=["egg"]), ProfileChanges(no_allergies=True))
    assert r.profile.allergies == ["egg"]
    assert "still have: egg" in r.notes[0]


def test_no_allergies_and_no_rules_on_empty_profile():
    r = apply_changes(profile(), ProfileChanges(no_allergies=True, no_dietary_rules=True))
    assert r.profile.allergies_answered and r.profile.dietary_answered
    assert r.safety_changes == ["no allergies", "no dietary rules"]


def test_dietary_rules_merge_and_conflict():
    r = apply_changes(profile(), ProfileChanges(add_dietary_rules=["Halal"]))
    assert r.profile.dietary_rules == ["halal"] and r.profile.dietary_answered
    r2 = apply_changes(r.profile, ProfileChanges(no_dietary_rules=True))
    assert r2.profile.dietary_rules == ["halal"] and "still have: halal" in r2.notes[0]
    r3 = apply_changes(r.profile, ProfileChanges(remove_dietary_rules=["halal"]))
    assert r3.profile.dietary_rules == [] and r3.safety_changes == ["removed dietary rule: halal"]


def test_soft_habits():
    r = apply_changes(
        profile(skipped_meals=["tea"]),
        ProfileChanges(
            budget_per_meal=15,
            currency="myr",
            spice_tolerance=9,
            default_radius_km=1,
            dine_preference="dine_in",
            add_skipped_meals=["breakfast"],
            remove_skipped_meals=["tea"],
            add_health_goals=["Low-carb"],
        ),
    )
    p = r.profile
    assert (p.budget_per_meal, p.currency, p.spice_tolerance, p.default_radius_km) == (
        15,
        "MYR",
        4,
        1,
    )
    assert p.dine_preference == "dine_in" and p.skipped_meals == ["breakfast"]
    assert p.health_goals == ["low-carb"]
    assert "budget: MYR 15" in r.other_changes and "dining: dine-in" in r.other_changes


def test_ignores_non_positive_budget_and_radius():
    r = apply_changes(profile(), ProfileChanges(budget_per_meal=0, default_radius_km=-1))
    assert r.profile.budget_per_meal is None and r.profile.default_radius_km is None
    assert r.other_changes == []


def test_slot_windows_and_not_understood():
    r = apply_changes(
        profile(),
        ProfileChanges(
            slot_windows=[
                SlotWindow(slot="breakfast", start="09:00", end="11:00"),
                SlotWindow(slot="lunch", start="noon", end="2pm"),
            ],
            not_understood=["blah"],
        ),
    )
    assert r.profile.slot_windows == {"breakfast": {"start": "09:00", "end": "11:00"}}
    assert any("lunch" in n for n in r.notes) and any("blah" in n for n in r.notes)


def test_apply_does_not_mutate_input():
    p = profile()
    apply_changes(p, ProfileChanges(add_allergies=["egg"]))
    assert p.allergies == []


def test_onboarding_status():
    s = onboarding_status(profile(), loves=1, dislikes=3)
    assert s.missing == ["allergies", "dietary_rules", "loves", "budget", "radius"]
    assert not s.complete and len(s.questions) == 5
    done = profile(
        allergies_answered=True, dietary_answered=True, budget_per_meal=10, default_radius_km=2
    )
    assert onboarding_status(done, 3, 3).complete
