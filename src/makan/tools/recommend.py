"""recommend_meal tool logic (P7), independent of FastMCP for testability.

Pipeline (docs/specs/04-recommendation-pipeline.md):
onboarding gate -> resolve context -> candidate dishes -> hard filters -> places ->
score + variety + select three -> reasons + allergen notes -> persist -> respond.
"""

import asyncio
import logging
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Protocol, get_args
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from makan.db.models import (
    Batch,
    FeedbackEvent,
    MealSlot,
    NewBatch,
    NewRecommendation,
    Profile,
    Recommendation,
)
from makan.domain.budget import budget_to_price_level
from makan.domain.preferences import ScoredEvent, norm, summarize, tag_scores
from makan.domain.ranking import (
    DISH_REPEAT_WINDOW,
    SOFT_REPEAT_WINDOW,
    Candidate,
    Habits,
    HistoryItem,
    Scored,
    apply_hard_filters,
    score_candidates,
    select_three,
)
from makan.domain.slots import infer_slot
from makan.llm.base import LLMError, LLMProvider
from makan.llm.jobs import (
    DishContext,
    PickForReason,
    ProposedDish,
    check_safety,
    propose_dishes,
    write_reasons,
)
from makan.location.geo import LatLng
from makan.location.geocode import GeoPoint
from makan.location.google import PlacesAPIError
from makan.location.places import Place
from makan.location.radius import clamp, resolve_radius
from makan.tools.profile import FeedbackStore, ProfileStore, load_profile, onboarding_gate

log = logging.getLogger(__name__)

CANDIDATE_COUNT = 8
MAX_PLACE_QUERIES = 5  # cost cap: distinct Places searches per recommendation
PLACES_PER_DISH = 3  # alternatives per dish, so a repeated place doesn't sink the dish
NO_PLACE_PENALTY = 1.0  # prefer dishes we can point to a real place for
REQUESTED_BONUS = 3.0  # a dish the user asked for by name should win
MIN_RATING = 3.5  # places rated below this are skipped (unrated places are kept)
WIDEN_FACTOR = 2.0

VALID_SLOTS: tuple[str, ...] = get_args(MealSlot)


class BatchStore(Protocol):
    async def create(self, batch: NewBatch, recs: list[NewRecommendation]) -> Batch: ...
    async def recommendations_since(
        self, since: datetime
    ) -> list[tuple[datetime, Recommendation]]: ...


class GeocoderLike(Protocol):
    async def geocode(self, query: str) -> GeoPoint | None: ...


class PlacesLike(Protocol):
    async def find(self, origin: LatLng, cuisine: str, radius_km: float) -> list[Place]: ...


@dataclass(frozen=True)
class _Option:
    dish: ProposedDish
    place: Place | None


# =====================================================================================
# Entry point
# =====================================================================================


async def recommend_meal(
    location: str,
    meal_slot: str | None = None,
    request: str | None = None,
    *,
    user_id: str,
    llm: LLMProvider,
    profiles: ProfileStore,
    feedback: FeedbackStore,
    batches: BatchStore,
    geocoder: GeocoderLike,
    places: PlacesLike,
    now: datetime,
) -> dict[str, Any]:
    # --- P7-T1 validate ---
    location = (location or "").strip()
    if not location:
        raise ValueError("location is required, e.g. 'Bangsar' or 'near KLCC'.")
    slot_arg = (meal_slot or "").strip().lower() or None
    if slot_arg is not None and slot_arg not in VALID_SLOTS:
        raise ValueError(f"meal_slot must be one of {', '.join(VALID_SLOTS)}.")
    request = (request or "").strip() or None

    # --- P7-T2 onboarding gate ---
    questions = await onboarding_gate(user_id, profiles, feedback)
    if questions:
        return {
            "status": "needs_onboarding",
            "onboarding_questions": questions,
            "message": "Before I can recommend meals, I need a few things "
            "(answer in your own words; I'll save them with update_profile):\n- "
            + "\n- ".join(questions),
        }
    profile = await load_profile(user_id, profiles)

    # --- P7-T3 resolve context ---
    point = await geocoder.geocode(location)
    if point is None:
        return {
            "status": "location_not_found",
            "message": f"I couldn't find “{location}”. Try a neighbourhood, landmark or "
            "street with the city, e.g. “Bangsar, Kuala Lumpur”.",
        }
    if point.timezone and point.timezone != profile.timezone:
        profile = await profiles.upsert(profile.model_copy(update={"timezone": point.timezone}))
    local = _local_time(now, point.timezone or profile.timezone)
    current_slot = infer_slot(local.time(), profile.slot_windows)
    slot: MealSlot = slot_arg or current_slot  # type: ignore[assignment]
    radius_km = resolve_radius(profile.default_radius_km, request)
    origin = LatLng(point.lat, point.lng)

    # --- history & preferences ---
    events = await feedback.list()
    scores = tag_scores((_scored_event(e) for e in events), now)
    summary = summarize(scores, n=8)
    tried = {norm(e.dish) for e in events if e.dish}
    history = [
        HistoryItem(at, r.dish, r.place_id)
        for at, r in await batches.recommendations_since(now - SOFT_REPEAT_WINDOW)
    ]
    avoid = sorted(
        d
        for d in {norm(h.dish) for h in history if now - h.shown_at < DISH_REPEAT_WINDOW}
        if not (request and d in norm(request))  # asked for again by name
    )

    # --- P7-T4 candidate dishes, P7-T5 hard filters (never relaxed) ---
    ctx = DishContext(
        meal_slot=slot,
        local_time=local.strftime("%A %H:%M"),
        location=location,
        request=request,
        allergies=profile.allergies,
        dietary_rules=profile.dietary_rules,
        health_goals=profile.health_goals,
        likes=[t for t, _ in summary.likes],
        dislikes=[t for t, _ in summary.dislikes],
        avoid_dishes=avoid,
        count=CANDIDATE_COUNT,
    )
    dishes = _dedupe((await propose_dishes(llm, ctx)).dishes)
    safe, excluded_count = await _hard_filter(llm, dishes, profile)
    if len(safe) < 3:
        # Strict allergy/diet checks can reject most proposals. Ask once more for
        # different dishes (never relax the filter itself).
        tried_names = {norm(d.dish) for d in dishes}
        more = await propose_dishes(
            llm, ctx.model_copy(update={"avoid_dishes": sorted(set(avoid) | tried_names)})
        )
        extra = [d for d in _dedupe(more.dishes) if norm(d.dish) not in tried_names]
        if extra:
            extra_safe, extra_excluded = await _hard_filter(llm, extra, profile)
            safe += extra_safe
            excluded_count += extra_excluded
    if not safe:
        return {
            "status": "no_safe_options",
            "meal_slot": slot,
            "message": "I couldn't find dishes that are safe for your allergies and dietary "
            "rules this time. Try again with a different request, e.g. a cuisine you like.",
        }

    habits = Habits(
        max_price_level=budget_to_price_level(profile.budget_per_meal, profile.currency),
        spice_tolerance=profile.spice_tolerance,
        dine_preference=profile.dine_preference,
    )

    def score(options: list[_Option]) -> list[tuple[Scored, _Option]]:
        """Score options; returns (scored, option) pairs. Repetition violations are dropped."""
        opt_of = {_candidate(o, request): o for o in options}
        out: list[tuple[Scored, _Option]] = []
        for sc in score_candidates(opt_of, scores, habits, history, tried, now):
            o = opt_of[sc.candidate]
            if o.place is None:
                sc = replace(sc, score=sc.score - NO_PLACE_PENALTY)
            if sc.candidate.explicitly_requested:
                sc = replace(sc, score=sc.score + REQUESTED_BONUS)
            out.append((sc, o))
        return out

    # --- P7-T6 places, cache-first, only for the most promising searches ---
    dish_only = [_Option(d, None) for d in safe]
    prelim = sorted(score(dish_only), key=lambda x: -x[0].score)
    queries: list[str] = []
    for _, o in prelim:
        q = norm(o.dish.places_query or o.dish.cuisine)
        if q and q not in queries:
            queries.append(q)
    queries = queries[:MAX_PLACE_QUERIES]
    found = await _lookup_places(places, origin, queries, radius_km)
    check_open = slot == current_slot  # open-now only matters when eating now

    placed: list[_Option] = []
    for d in safe:
        ps = found.get(norm(d.places_query or d.cuisine), [])
        ps = [p for p in ps if not (check_open and p.open_now is False)]
        ps = [p for p in ps if p.rating is None or p.rating >= MIN_RATING]
        ps.sort(key=_place_quality, reverse=True)
        placed += [_Option(d, p) for p in ps[:PLACES_PER_DISH]]

    # --- P7-T7 score + variety + select three ---
    scored = score(placed + dish_only)
    opt_of = {sc.candidate: o for sc, o in scored}
    picks = select_three([sc for sc, _ in scored])
    if not picks:
        return {
            "status": "no_options",
            "meal_slot": slot,
            "message": "Everything I came up with was suggested in the last few days. "
            "Ask again with a specific request, or name a dish you'd like again.",
        }
    chosen = [(p, opt_of[p.candidate]) for p in picks]

    # --- P7-T9 reasons + allergen notes ---
    reasons = await _reasons(llm, chosen, scores)
    allergen_note = _allergen_note(profile)

    # --- P7-T10 persist ---
    batch = await batches.create(
        NewBatch(meal_slot=slot, location=location, lat=point.lat, lng=point.lng),
        [
            NewRecommendation(
                position=i,
                dish=o.dish.dish,
                place_id=o.place.place_id if o.place else None,
                place_name=o.place.name if o.place else None,
                tags=sorted({norm(t) for t in [*o.dish.tags, o.dish.cuisine] if t.strip()}),
                is_explore=s.is_explore,
            )
            for i, (s, o) in enumerate(chosen, start=1)
        ],
    )

    # --- P7-T8 / T11 respond ---
    options = [
        {
            "position": i,
            "dish": o.dish.dish,
            "place": _place_json(o.place, show_open=check_open),
            "reason": reasons.get(norm(o.dish.dish)) or _fallback_reason(s, o),
            "allergen_note": allergen_note,
            "is_explore": s.is_explore,
        }
        for i, (s, o) in enumerate(chosen, start=1)
    ]
    no_places = all(o["place"] is None for o in options)
    widen = _widen(radius_km) if no_places else None
    return {
        "status": "ok",
        "batch_id": str(batch.id),
        "meal_slot": slot,
        "location": {
            "query": location,
            "lat": point.lat,
            "lng": point.lng,
            "timezone": point.timezone,
        },
        "radius_km": radius_km,
        "options": options,
        "no_places_found": no_places,
        "suggested_radius_km": widen,
        "excluded_for_safety": excluded_count,
        "message": _message(slot, location, radius_km, options, widen),
    }


# =====================================================================================
# Helpers
# =====================================================================================


def _local_time(now: datetime, tz: str | None) -> datetime:
    try:
        return now.astimezone(ZoneInfo(tz)) if tz else now
    except ZoneInfoNotFoundError:
        return now


def _scored_event(e: FeedbackEvent) -> ScoredEvent:
    return ScoredEvent(e.created_at, e.score, tuple(e.tags), e.dish, e.place_id)


def _dedupe(dishes: list[ProposedDish]) -> list[ProposedDish]:
    seen: dict[str, ProposedDish] = {}
    for d in dishes:
        if d.dish.strip():
            seen.setdefault(norm(d.dish), d)
    return list(seen.values())


async def _hard_filter(
    llm: LLMProvider, dishes: list[ProposedDish], profile: Profile
) -> tuple[list[ProposedDish], int]:
    """Allergen + dietary filter. Dishes the checker didn't return are treated as unsafe."""
    allergies = [a for a in profile.allergies if a.strip()]
    rules = [r for r in profile.dietary_rules if r.strip()]
    flags: dict[str, list[str]] = {}
    violations: dict[str, list[str]] = {}
    if allergies or rules:
        check = await check_safety(llm, [d.dish for d in dishes], allergies, rules)
        for r in check.results:
            flags[norm(r.dish)] = r.likely_contains
            violations[norm(r.dish)] = r.dietary_violations
        if rules:
            for d in dishes:
                violations.setdefault(norm(d.dish), ["dietary check missing"])
    cands = [Candidate(dish=d.dish) for d in dishes]
    survivors, excluded = apply_hard_filters(cands, allergies, flags, violations)
    for x in excluded:
        log.info("excluded dish=%r reasons=%s", x.candidate.dish, x.reasons)
    keep = {c.key for c in survivors}
    return [d for d in dishes if norm(d.dish) in keep], len(excluded)


def _candidate(o: _Option, request: str | None) -> Candidate:
    d = o.dish
    price = o.place.price_level if o.place and o.place.price_level is not None else None
    return Candidate(
        dish=d.dish,
        tags=frozenset(t for t in [*d.tags, d.cuisine] if t.strip()),
        place_id=o.place.place_id if o.place else None,
        place_name=o.place.name if o.place else None,
        price_level=price if price is not None else d.typical_price_level,
        spice_level=d.spice_level,
        violated_health_goals=frozenset(d.violates_health_goals),
        explicitly_requested=bool(request) and norm(d.dish) in norm(request or ""),
    )


async def _lookup_places(
    places: PlacesLike, origin: LatLng, queries: list[str], radius_km: float
) -> dict[str, list[Place]]:
    async def one(q: str) -> list[Place]:
        try:
            return await places.find(origin, q, radius_km)
        except PlacesAPIError as e:  # degrade to dish-only for this query
            log.warning("places lookup failed query=%r: %s", q, e)
            return []

    results = await asyncio.gather(*(one(q) for q in queries))
    return dict(zip(queries, results, strict=True))


def _place_quality(p: Place) -> float:
    """Higher is better: rating (unrated ~ 3.8) minus a small distance cost."""
    return (p.rating if p.rating is not None else 3.8) - 0.15 * (p.distance_km or 0.0)


async def _reasons(
    llm: LLMProvider, chosen: list[tuple[Scored, _Option]], scores: dict[str, float]
) -> dict[str, str]:
    picks = [
        PickForReason(
            dish=o.dish.dish,
            place_name=o.place.name if o.place else None,
            distance_km=o.place.distance_km if o.place else None,
            is_explore=s.is_explore,
            matched_likes=sorted(t for t in s.candidate.all_tags() if scores.get(t, 0) > 0.25),
        )
        for s, o in chosen
    ]
    try:
        out = await write_reasons(llm, picks)
    except LLMError as e:  # reasons are nice-to-have; never fail the recommendation
        log.warning("write_reasons failed: %s", e)
        return {}
    return {norm(r.dish): r.reason for r in out.reasons if r.reason.strip()}


def _fallback_reason(s: Scored, o: _Option) -> str:
    if s.is_explore:
        return "Something new for you to try."
    if o.place and o.place.distance_km is not None:
        return f"A good fit for you, {o.place.distance_km:.1f} km away."
    return "A good fit for your tastes."


def _allergen_note(profile: Profile) -> str | None:
    allergies = [a for a in profile.allergies if a.strip()]
    if not allergies:
        return None
    return (
        f"Checked against your allergies ({', '.join(allergies)}), but recipes vary — "
        "please confirm with the vendor."
    )


def _place_json(p: Place | None, *, show_open: bool) -> dict[str, Any] | None:
    """`open_now` is only reported when the meal is now; for a later meal it's misleading."""
    if p is None:
        return None
    return {
        "place_id": p.place_id,
        "name": p.name,
        "distance_km": p.distance_km,
        "rating": p.rating,
        "open_now": p.open_now if show_open else None,
    }


def _widen(radius_km: float) -> float:
    return clamp(max(radius_km * WIDEN_FACTOR, radius_km + 2))


def _message(
    slot: str,
    location: str,
    radius_km: float,
    options: list[dict[str, Any]],
    widen: float | None,
) -> str:
    lines = [f"{slot.capitalize()} ideas near {location} (within {radius_km:g} km):"]
    for o in options:
        p = o["place"]
        where = ""
        if p:
            where = f" at {p['name']}"
            if p["distance_km"] is not None:
                where += f" ({p['distance_km']:.1f} km"
                where += f", ★{p['rating']:g})" if p["rating"] is not None else ")"
            if p["open_now"] is False:
                where += " — closed now"
        tag = " [new for you]" if o["is_explore"] else ""
        lines.append(f"{o['position']}. {o['dish']}{where}{tag} — {o['reason']}")
    note = next((o["allergen_note"] for o in options if o["allergen_note"]), None)
    if note:
        lines.append(note)
    if widen:
        lines.append(
            f"I couldn't find a suitable place within {radius_km:g} km. "
            f"Want me to search within {widen:g} km instead?"
        )
    lines.append("Tell me how it was afterwards and I'll learn your taste.")
    return "\n".join(lines)
