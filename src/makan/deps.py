"""Per-request dependencies for tools. Tests can override the LLM."""

from dataclasses import dataclass

from makan.auth import CurrentUser, current_user
from makan.db.client import user_client
from makan.db.repos import BatchRepo, FeedbackRepo, ProfileRepo
from makan.llm import LLMProvider, get_llm

_llm: LLMProvider | None = None


def llm() -> LLMProvider:
    global _llm
    if _llm is None:
        _llm = get_llm()
    return _llm


def override_llm(provider: LLMProvider | None) -> None:
    """For tests: replace (or reset with None) the LLM used by tools."""
    global _llm
    _llm = provider


@dataclass
class UserDeps:
    user: CurrentUser
    profiles: ProfileRepo
    feedback: FeedbackRepo
    batches: BatchRepo


async def user_deps() -> UserDeps:
    user = current_user()
    db = await user_client(user)
    return UserDeps(
        user=user,
        profiles=ProfileRepo(db, user.user_id),
        feedback=FeedbackRepo(db, user.user_id),
        batches=BatchRepo(db, user.user_id),
    )
