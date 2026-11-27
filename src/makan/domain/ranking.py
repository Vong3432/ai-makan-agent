"""Ranking: hard filters, habit fit, variety rules, final selection of three.

See docs/specs/04-recommendation-pipeline.md. Pure functions, no I/O.

Hard filters are deliberately separate from scoring: `apply_hard_filters` never sees
scores, and `select_three` only ever receives its survivors.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

from makan.domain.preferences import norm, place_tag, preference_score

DISH_REPEAT_WINDOW = timedelta(days=3)
PLACE_REPEAT_WINDOW = timedelta(days=2)
SOFT_REPEAT_WINDOW = timedelta(days=7)

NOVELTY_BONUS = 0.3
SOFT_REPEAT_PENALTY = 0.5
OVER_BUDGET_PENALTY = 1.0  # per price level above the user's max
SPICE_PENALTY = 0.75  # per level above tolerance
HEALTH_PENALTY = 0.75  # per violated health goal
DINE_MISMATCH_PENALTY = 0.5


@dataclass(frozen=True)
class Candidate:
    dish: str
    tags: frozenset[str] = frozenset()
    place_id: str | None = None
    place_name: str | None = None
    price_level: int | None = None  # 0..4 (Google scale)
    spice_level: int | None = None  # 0..4
    violated_health_goals: frozenset[str] = frozenset()
    dine_modes: frozenset[str] = frozenset()  # subset of {"dine_in", "delivery"}
    explicitly_requested: bool = False

    @property
    def key(self) -> str:
        return norm(self.dish)

    def all_tags(self) -> set[str]:
        tags = {norm(t) for t in self.tags} | {self.key}
        if self.place_id:
            tags.add(place_tag(self.place_id))
        return tags


@dataclass(frozen=True)
class Habits:
    max_price_level: int | None = None
    spice_tolerance: int | None = None
    dine_preference: str | None = None  # dine_in | delivery | either


@dataclass(frozen=True)
class HistoryItem:
    shown_at: datetime
    dish: str
    place_id: str | None = None


@dataclass(frozen=True)
class Excluded:
    candidate: Candidate
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Scored:
    candidate: Candidate
    score: float
    is_explore: bool = False
    breakdown: Mapping[str, float] = field(default_factory=dict)


# ---------- hard filters ----------


def apply_hard_filters(
    candidates: Iterable[Candidate],
    allergies: Iterable[str],
    allergen_flags: Mapping[str, Iterable[str]],
    dietary_violations: Mapping[str, Iterable[str]],
) -> tuple[list[Candidate], list[Excluded]]:
    """Exclude anything that may contain a declared allergen or breaks a dietary rule.

    `allergen_flags` / `dietary_violations` are keyed by normalised dish (from the LLM checks).
    Conservative: if the user has allergies and a dish was not checked, it is excluded.
    """
    has_allergies = any(a.strip() for a in allergies)
    survivors: list[Candidate] = []
    excluded: list[Excluded] = []
    for c in candidates:
        reasons: list[str] = []
        if has_allergies:
            if c.key not in allergen_flags:
                reasons.append("allergen check missing")
            else:
                reasons += [f"may contain {a}" for a in allergen_flags[c.key]]
        reasons += [f"breaks rule: {r}" for r in dietary_violations.get(c.key, ())]
        if reasons:
            excluded.append(Excluded(c, tuple(reasons)))
        else:
            survivors.append(c)
    return survivors, excluded


# ---------- variety ----------


def violates_repetition(c: Candidate, history: Iterable[HistoryItem], now: datetime) -> bool:
    if c.explicitly_requested:
        return False
    for h in history:
        age = now - h.shown_at
        if norm(h.dish) == c.key and age < DISH_REPEAT_WINDOW:
            return True
        if c.place_id and h.place_id == c.place_id and age < PLACE_REPEAT_WINDOW:
            return True
    return False


def recently_shown(c: Candidate, history: Iterable[HistoryItem], now: datetime) -> bool:
    return any(norm(h.dish) == c.key and now - h.shown_at < SOFT_REPEAT_WINDOW for h in history)


# ---------- scoring ----------


def habit_penalty(c: Candidate, habits: Habits) -> float:
    p = 0.0
    if habits.max_price_level is not None and c.price_level is not None:
        p += OVER_BUDGET_PENALTY * max(0, c.price_level - habits.max_price_level)
    if habits.spice_tolerance is not None and c.spice_level is not None:
        p += SPICE_PENALTY * max(0, c.spice_level - habits.spice_tolerance)
    p += HEALTH_PENALTY * len(c.violated_health_goals)
    if (
        habits.dine_preference in ("dine_in", "delivery")
        and c.dine_modes
        and habits.dine_preference not in c.dine_modes
    ):
        p += DINE_MISMATCH_PENALTY
    return p


def score_candidates(
    candidates: Iterable[Candidate],
    tag_scores: Mapping[str, float],
    habits: Habits,
    history: Iterable[HistoryItem],
    tried_dishes: Iterable[str],
    now: datetime,
) -> list[Scored]:
    """Score survivors of the hard filters; drops hard repetition violations."""
    history = list(history)
    tried = {norm(d) for d in tried_dishes}
    out: list[Scored] = []
    for c in candidates:
        if violates_repetition(c, history, now):
            continue
        pref = preference_score(c.all_tags(), dict(tag_scores))
        novelty = NOVELTY_BONUS if c.key not in tried else 0.0
        repeat = SOFT_REPEAT_PENALTY if recently_shown(c, history, now) else 0.0
        habit = habit_penalty(c, habits)
        out.append(
            Scored(
                candidate=c,
                score=pref + novelty - repeat - habit,
                is_explore=c.key not in tried,
                breakdown={
                    "preference": pref,
                    "novelty": novelty,
                    "repeat": -repeat,
                    "habit": -habit,
                },
            )
        )
    return out


# ---------- selection ----------


def select_three(scored: Iterable[Scored], n: int = 3) -> list[Scored]:
    """Pick up to `n` distinct dishes: the best untried ("explore") pick is always included
    when one exists; the rest are the highest scores. Returned best-first; only the
    reserved pick is flagged is_explore."""
    ranked = sorted(scored, key=lambda s: (-s.score, s.candidate.key))
    best_by_dish: dict[str, Scored] = {}
    for s in ranked:
        best_by_dish.setdefault(s.candidate.key, s)
    unique = list(best_by_dish.values())

    explore = next((s for s in unique if s.is_explore), None)
    picks = [s for s in unique if s is not explore][: n - 1 if explore else n]
    if explore:
        picks.append(explore)
    picks.sort(key=lambda s: (-s.score, s.candidate.key))
    return [replace(s, is_explore=s is explore) for s in picks]
