from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from makan.domain.ranking import (
    Candidate,
    Habits,
    HistoryItem,
    Scored,
    apply_hard_filters,
    habit_penalty,
    recently_shown,
    score_candidates,
    select_three,
    violates_repetition,
)

NOW = datetime(2026, 11, 27, 12, tzinfo=UTC)


def c(dish: str, **kw) -> Candidate:
    return Candidate(dish=dish, **kw)


def h(dish: str, days_ago: float, place_id=None) -> HistoryItem:
    return HistoryItem(NOW - timedelta(days=days_ago), dish, place_id)


# ---------- hard filters ----------


def test_hard_filters_allergens_and_diet():
    cands = [c("Prawn Mee"), c("Fried Rice"), c("Beef Rendang"), c("Unchecked Dish")]
    ok, out = apply_hard_filters(
        cands,
        allergies=["shellfish"],
        allergen_flags={"prawn mee": ["shellfish"], "fried rice": [], "beef rendang": []},
        dietary_violations={"beef rendang": ["no beef"]},
    )
    assert [x.dish for x in ok] == ["Fried Rice"]
    reasons = {e.candidate.dish: e.reasons for e in out}
    assert reasons["Prawn Mee"] == ("may contain shellfish",)
    assert reasons["Beef Rendang"] == ("breaks rule: no beef",)
    assert reasons["Unchecked Dish"] == ("allergen check missing",)


def test_hard_filters_no_allergies_needs_no_check():
    ok, out = apply_hard_filters(
        [c("Anything")], allergies=["  "], allergen_flags={}, dietary_violations={}
    )
    assert [x.dish for x in ok] == ["Anything"] and out == []


# ---------- variety ----------


def test_dish_repeat_window():
    assert violates_repetition(c("Laksa"), [h("laksa", 2.9)], NOW)
    assert not violates_repetition(c("Laksa"), [h("laksa", 3.1)], NOW)


def test_place_repeat_window():
    assert violates_repetition(c("Nasi Lemak", place_id="p1"), [h("roti", 1.5, "p1")], NOW)
    assert not violates_repetition(c("Nasi Lemak", place_id="p1"), [h("roti", 2.5, "p1")], NOW)
    assert not violates_repetition(c("Nasi Lemak"), [h("roti", 1, None)], NOW)


def test_explicit_request_overrides_repetition():
    assert not violates_repetition(c("Laksa", explicitly_requested=True), [h("laksa", 0)], NOW)


def test_recently_shown_soft_window():
    assert recently_shown(c("Laksa"), [h("laksa", 6)], NOW)
    assert not recently_shown(c("Laksa"), [h("laksa", 8)], NOW)


# ---------- habits ----------


def test_habit_penalty_components():
    habits = Habits(max_price_level=1, spice_tolerance=1, dine_preference="delivery")
    cand = c(
        "X",
        price_level=3,
        spice_level=2,
        violated_health_goals=frozenset({"low-carb"}),
        dine_modes=frozenset({"dine_in"}),
    )
    assert habit_penalty(cand, habits) == 2 * 1.0 + 1 * 0.75 + 0.75 + 0.5


def test_habit_penalty_none_when_unknown_or_within_limits():
    assert (
        habit_penalty(
            c("X"), Habits(max_price_level=1, spice_tolerance=1, dine_preference="delivery")
        )
        == 0
    )
    within = c("X", price_level=1, spice_level=0, dine_modes=frozenset({"delivery"}))
    assert habit_penalty(within, Habits(1, 1, "delivery")) == 0
    assert (
        habit_penalty(c("X", dine_modes=frozenset({"dine_in"})), Habits(dine_preference="either"))
        == 0
    )


# ---------- scoring ----------


def test_score_candidates():
    scored = score_candidates(
        [c("Laksa", tags=frozenset({"spicy"})), c("Fried Rice"), c("Roti", place_id="p1")],
        tag_scores={"spicy": 1.0, "fried rice": 2.0},
        habits=Habits(),
        history=[h("fried rice", 5), h("x", 1, "p1")],
        tried_dishes=["Fried Rice"],
        now=NOW,
    )
    by = {s.candidate.dish: s for s in scored}
    assert "Roti" not in by  # place repeated within 2 days
    assert by["Laksa"].score == 1.0 + 0.3 and by["Laksa"].is_explore
    assert by["Fried Rice"].score == 2.0 - 0.5 and not by["Fried Rice"].is_explore


# ---------- selection ----------


def s(dish: str, score: float, explore: bool = False) -> Scored:
    return Scored(c(dish), score, explore)


def test_select_three_reserves_explore_slot():
    picks = select_three([s("a", 5), s("b", 4), s("c", 3), s("new", 1, True)])
    assert [p.candidate.dish for p in picks] == ["a", "b", "new"]
    assert [p.is_explore for p in picks] == [False, False, True]


def test_select_three_only_one_flagged_when_many_untried():
    picks = select_three([s("a", 5, True), s("b", 4, True), s("c", 3, True)])
    assert [p.candidate.dish for p in picks] == ["a", "b", "c"]
    assert sum(p.is_explore for p in picks) == 1 and picks[0].is_explore


def test_select_three_without_explore_and_dedupes_dishes():
    picks = select_three([s("a", 5), s("A", 4), s("b", 3), s("c", 2), s("d", 1)])
    assert [p.candidate.dish for p in picks] == ["a", "b", "c"]
    assert not any(p.is_explore for p in picks)


def test_select_three_fewer_than_three():
    assert select_three([]) == []
    assert [p.candidate.dish for p in select_three([s("a", 1)])] == ["a"]


# ---------- safety property ----------

dishes = st.lists(st.text("abcdef", min_size=1, max_size=4), min_size=1, max_size=8, unique=True)


@given(
    dishes=dishes,
    flagged=st.data(),
    scores=st.dictionaries(st.text("abcdef", min_size=1, max_size=4), st.floats(-1e6, 1e6)),
)
def test_allergen_flagged_dish_never_selected(dishes, flagged, scores):
    bad = set(flagged.draw(st.lists(st.sampled_from(dishes), unique=True)))
    cands = [c(d, explicitly_requested=True) for d in dishes]
    flags = {d: (["peanut"] if d in bad else []) for d in dishes}
    survivors, _ = apply_hard_filters(cands, ["peanut"], flags, {})
    picks = select_three(
        score_candidates(survivors, scores, Habits(), [], tried_dishes=[], now=NOW)
    )
    assert not {p.candidate.key for p in picks} & bad


def test_liked_place_boosts_candidate():
    scored = score_candidates(
        [c("Roti", place_id="p1"), c("Roti Canai", place_id="p2")],
        tag_scores={"place:p1": 1.0},
        habits=Habits(),
        history=[],
        tried_dishes=["roti", "roti canai"],
        now=NOW,
    )
    by = {s.candidate.dish: s.score for s in scored}
    assert by["Roti"] == 1.0 and by["Roti Canai"] == 0.0
