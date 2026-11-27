"""Preference model: feedback events -> decayed per-tag scores.

See docs/specs/05-preference-model.md. Pure functions, no I/O.
"""

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

HALF_LIFE_DAYS = 60.0


def norm(text: str) -> str:
    """Canonical form for dishes and tags: lowercase, single spaces."""
    return re.sub(r"\s+", " ", text.strip().lower())


def place_tag(place_id: str) -> str:
    return f"place:{place_id}"


@dataclass(frozen=True)
class ScoredEvent:
    """Minimal view of a feedback event (decoupled from the DB model)."""

    created_at: datetime
    score: int  # -2..2
    tags: tuple[str, ...] = ()
    dish: str | None = None
    place_id: str | None = None


def decay_weight(age_days: float) -> float:
    """0.5 ** (age / half-life). Future-dated events count as fresh."""
    return 0.5 ** (max(age_days, 0.0) / HALF_LIFE_DAYS)


def event_tags(event: ScoredEvent) -> set[str]:
    tags = {norm(t) for t in event.tags if t.strip()}
    if event.dish and event.dish.strip():
        tags.add(norm(event.dish))
    if event.place_id:
        tags.add(place_tag(event.place_id))
    return tags


def tag_scores(events: Iterable[ScoredEvent], now: datetime) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)
    for e in events:
        w = e.score * decay_weight((now - e.created_at).total_seconds() / 86400)
        for t in event_tags(e):
            scores[t] += w
    return dict(scores)


def preference_score(candidate_tags: Iterable[str], scores: dict[str, float]) -> float:
    return sum(scores.get(t, 0.0) for t in {norm(t) for t in candidate_tags})


@dataclass(frozen=True)
class Summary:
    likes: list[tuple[str, float]] = field(default_factory=list)
    dislikes: list[tuple[str, float]] = field(default_factory=list)


def summarize(scores: dict[str, float], n: int = 5, threshold: float = 0.25) -> Summary:
    """Top likes / dislikes for get_profile. Place tags are excluded (ids aren't readable)."""
    readable = [(t, s) for t, s in scores.items() if not t.startswith("place:")]
    likes = sorted((x for x in readable if x[1] >= threshold), key=lambda x: (-x[1], x[0]))
    dislikes = sorted((x for x in readable if x[1] <= -threshold), key=lambda x: (x[1], x[0]))
    return Summary(likes=likes[:n], dislikes=dislikes[:n])
