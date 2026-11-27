from datetime import UTC, datetime, timedelta

import pytest

from makan.domain.preferences import (
    ScoredEvent,
    decay_weight,
    event_tags,
    norm,
    preference_score,
    summarize,
    tag_scores,
)

NOW = datetime(2026, 11, 27, 12, tzinfo=UTC)


def ev(score: int, days_ago: float = 0, tags=(), dish=None, place_id=None) -> ScoredEvent:
    return ScoredEvent(NOW - timedelta(days=days_ago), score, tuple(tags), dish, place_id)


def test_norm():
    assert norm("  Fried   RICE ") == "fried rice"


@pytest.mark.parametrize(("age", "w"), [(0, 1.0), (60, 0.5), (120, 0.25), (-5, 1.0)])
def test_decay_weight(age, w):
    assert decay_weight(age) == pytest.approx(w)


def test_event_tags_includes_dish_and_place_and_skips_blanks():
    assert event_tags(ev(1, tags=["Spicy", " "], dish="Fried Rice", place_id="p1")) == {
        "spicy",
        "fried rice",
        "place:p1",
    }
    assert event_tags(ev(1, dish="  ")) == set()


def test_tag_scores_sum_and_decay():
    scores = tag_scores([ev(2, 0, ["spicy"]), ev(-2, 60, ["spicy"]), ev(1, 0, ["soupy"])], NOW)
    assert scores["spicy"] == pytest.approx(2 - 1)
    assert scores["soupy"] == pytest.approx(1)


def test_recent_feedback_outweighs_old():
    scores = tag_scores([ev(2, 180, dish="laksa"), ev(-1, 0, dish="laksa")], NOW)
    assert scores["laksa"] < 0


def test_preference_score_normalises_and_dedupes():
    assert preference_score(["Spicy", "spicy", "unknown"], {"spicy": 1.5}) == 1.5


def test_summarize():
    s = summarize({"laksa": 2, "oily": -1.5, "place:x": 3, "meh": 0.1, "soupy": 0.5}, n=1)
    assert s.likes == [("laksa", 2)]
    assert s.dislikes == [("oily", -1.5)]
