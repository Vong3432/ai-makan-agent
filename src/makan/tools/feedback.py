"""give_feedback tool logic (P8), independent of FastMCP for testability.

The LLM matches feedback to recently shown items (refs like "b1.2" = latest batch, option 2)
and extracts tags + a score. Matched items inherit the shown dish, place and tags so the
preference model learns about the place and cuisine too. Allergies and dietary rules are
never changed here: they come back as a hint to use update_profile.
"""

from typing import Any, Protocol

from makan.db.models import Batch, NewFeedbackEvent, Recommendation
from makan.domain.preferences import norm
from makan.llm.base import LLMProvider
from makan.llm.jobs import FeedbackItem, ShownItem, extract_feedback
from makan.tools.profile import FeedbackStore

RECENT_BATCHES = 3


class RecentBatches(Protocol):
    async def recent(self, limit: int = 3) -> list[Batch]: ...


def _shown(batches: list[Batch]) -> tuple[list[ShownItem], dict[str, Recommendation]]:
    items: list[ShownItem] = []
    by_ref: dict[str, Recommendation] = {}
    for i, b in enumerate(batches, start=1):  # newest first
        for r in b.recommendations:
            ref = f"b{i}.{r.position}"
            by_ref[ref] = r
            items.append(
                ShownItem(
                    ref=ref,
                    shown_at=b.created_at,
                    meal_slot=b.meal_slot,
                    dish=r.dish,
                    place_name=r.place_name,
                )
            )
    return items, by_ref


def _event(
    item: FeedbackItem, rec: Recommendation | None, slot_of: dict[str, str], message: str
) -> NewFeedbackEvent | None:
    dish = (rec.dish if rec else None) or (item.dish or "").strip() or None
    if dish is None:
        return None
    tags = {norm(t) for t in [*item.tags, *(rec.tags if rec else [])] if t.strip()}
    return NewFeedbackEvent(
        raw_message=message,
        source="feedback",
        recommendation_id=rec.id if rec else None,
        dish=dish,
        place_id=rec.place_id if rec else None,
        meal_slot=slot_of.get(str(rec.batch_id)) if rec else item.meal_slot,
        tags=sorted(tags),
        score=max(-2, min(2, item.score)),
    )


def _describe(e: NewFeedbackEvent, place_name: str | None) -> str:
    where = f" at {place_name}" if place_name else ""
    tags = [t for t in e.tags if t != norm(e.dish or "")]
    why = f" ({', '.join(tags)})" if tags else ""
    return f"{e.dish}{where} {e.score:+d}{why}"


async def give_feedback(
    message: str,
    *,
    llm: LLMProvider,
    feedback: FeedbackStore,
    batches: RecentBatches,
) -> dict[str, Any]:
    message = (message or "").strip()
    if not message:
        raise ValueError("message is required, e.g. 'the laksa was great'.")

    recent = await batches.recent(RECENT_BATCHES)
    shown, by_ref = _shown(recent)
    slot_of = {str(b.id): b.meal_slot for b in recent}
    extraction = await extract_feedback(llm, message, shown)

    events: list[NewFeedbackEvent] = []
    names: list[str | None] = []
    seen: set[tuple[str, str | None]] = set()
    for item in extraction.items:
        rec = by_ref.get(item.matched_ref or "")
        e = _event(item, rec, slot_of, message)
        if e is None:
            continue
        key = (norm(e.dish or ""), str(e.recommendation_id) if e.recommendation_id else None)
        if key in seen:  # same item mentioned twice: keep the first
            continue
        seen.add(key)
        events.append(e)
        names.append(rec.place_name if rec else item.place_name)

    await feedback.add(events)
    recorded = [_describe(e, n) for e, n in zip(events, names, strict=True)]

    hint = (extraction.profile_hint or "").strip().rstrip(".") or None
    lines: list[str] = []
    if recorded:
        lines.append("Noted: " + "; ".join(recorded) + ".")
        lines.append("If I matched the wrong meal, tell me the dish name and I'll fix it.")
    else:
        lines.append(
            "I couldn't tell which meal that was about. Name the dish (and place) and "
            "say how it was."
        )
    if hint:
        lines.append(
            f"That sounds like a profile change ({hint}). I haven't changed your allergies "
            "or dietary rules from feedback; say it again and I'll update your profile."
        )
    return {
        "recorded": [
            {
                "dish": e.dish,
                "place_name": n,
                "score": e.score,
                "tags": e.tags,
                "matched_recommendation": e.recommendation_id is not None,
            }
            for e, n in zip(events, names, strict=True)
        ],
        "profile_hint": hint,
        "message": "\n".join(lines),
    }
