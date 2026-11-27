"""update_profile / get_profile tool logic, independent of FastMCP for testability."""

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from makan.db.models import FeedbackEvent, NewFeedbackEvent, Profile
from makan.domain.preferences import ScoredEvent, summarize, tag_scores
from makan.domain.profile import apply_changes, onboarding_status
from makan.llm.base import LLMProvider
from makan.llm.jobs import extract_profile_changes


class ProfileStore(Protocol):
    async def get(self) -> Profile | None: ...
    async def upsert(self, profile: Profile) -> Profile: ...


class FeedbackStore(Protocol):
    async def add(self, events: list[NewFeedbackEvent]) -> list[FeedbackEvent]: ...
    async def list(self, since: datetime | None = None) -> list[FeedbackEvent]: ...
    async def profile_item_counts(self) -> tuple[int, int]: ...


async def load_profile(user_id: str, profiles: ProfileStore) -> Profile:
    return await profiles.get() or Profile(user_id=UUID(user_id))


async def update_profile(
    message: str,
    *,
    user_id: str,
    llm: LLMProvider,
    profiles: ProfileStore,
    feedback: FeedbackStore,
) -> dict[str, Any]:
    changes = await extract_profile_changes(llm, message)
    current = await load_profile(user_id, profiles)
    result = apply_changes(current, changes)

    # Loves / dislikes become preference events (+2 / -2) so ranking uses them immediately.
    events = [
        NewFeedbackEvent(raw_message=message, source="profile", dish=d, tags=[d], score=2)
        for d in changes.loves
        if d.strip()
    ] + [
        NewFeedbackEvent(raw_message=message, source="profile", dish=d, tags=[d], score=-2)
        for d in changes.dislikes
        if d.strip()
    ]
    await feedback.add(events)

    loves, dislikes = await feedback.profile_item_counts()
    status = onboarding_status(result.profile, loves, dislikes)
    if status.complete:
        result.profile.onboarded = True
    saved = await profiles.upsert(result.profile)

    other = result.other_changes + [f"loves: {d}" for d in changes.loves]
    other += [f"dislikes: {d}" for d in changes.dislikes]
    return {
        "saved": True,
        "safety_changes": result.safety_changes,
        "other_changes": other,
        "notes": result.notes,
        "onboarding_complete": saved.onboarded,
        "onboarding_questions": [] if saved.onboarded else status.questions,
        "message": _summary(
            result.safety_changes, other, result.notes, saved.onboarded, status.questions
        ),
    }


def _summary(
    safety: list[str], other: list[str], notes: list[str], onboarded: bool, questions: list[str]
) -> str:
    lines: list[str] = []
    if safety:
        lines.append("Please confirm these safety settings: " + "; ".join(safety) + ".")
    if other:
        lines.append("Updated: " + "; ".join(other) + ".")
    if not safety and not other:
        lines.append("Nothing in that message changed your profile.")
    lines += notes
    if not onboarded and questions:
        lines.append("Before I can recommend meals, I still need:\n- " + "\n- ".join(questions))
    elif onboarded:
        lines.append("Your profile is ready — ask for a meal recommendation any time.")
    return "\n".join(lines)


async def get_profile(
    *, user_id: str, profiles: ProfileStore, feedback: FeedbackStore, now: datetime
) -> dict[str, Any]:
    profile = await load_profile(user_id, profiles)
    events = await feedback.list()
    scores = tag_scores(
        (ScoredEvent(e.created_at, e.score, tuple(e.tags), e.dish, e.place_id) for e in events),
        now,
    )
    summary = summarize(scores)
    loves, dislikes = await feedback.profile_item_counts()
    status = onboarding_status(profile, loves, dislikes)
    return {
        "profile": profile.model_dump(mode="json", exclude={"user_id", "created_at", "updated_at"}),
        "top_likes": [t for t, _ in summary.likes],
        "top_dislikes": [t for t, _ in summary.dislikes],
        "onboarding_complete": profile.onboarded or status.complete,
        "onboarding_questions": [] if profile.onboarded else status.questions,
    }


async def onboarding_gate(
    user_id: str, profiles: ProfileStore, feedback: FeedbackStore
) -> list[str]:
    """Questions still to answer before recommending (empty = ready). Used by recommend_meal."""
    profile = await load_profile(user_id, profiles)
    if profile.onboarded:
        return []
    loves, dislikes = await feedback.profile_item_counts()
    return onboarding_status(profile, loves, dislikes).questions
