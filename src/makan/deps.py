"""Per-request dependencies for tools. Tests can override the LLM."""

from dataclasses import dataclass

from makan.auth import CurrentUser, current_user
from makan.config import get_settings
from makan.db.client import service_client, user_client
from makan.db.repos import BatchRepo, CacheRepo, FeedbackRepo, ProfileRepo
from makan.llm import LLMProvider, get_llm
from makan.location.geocode import Geocoder
from makan.location.google import GooglePlacesHTTP
from makan.location.places import PlacesFinder

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


@dataclass
class LocationDeps:
    geocoder: Geocoder
    places: PlacesFinder


_location: LocationDeps | None = None


async def location_deps() -> LocationDeps:
    """Shared (not per-user): caches use the service-role client."""
    global _location
    if _location is None:
        s = get_settings()
        http = GooglePlacesHTTP(
            s.google_api_key.get_secret_value(), region_code=s.places_region_code
        )
        cache = CacheRepo(await service_client())
        _location = LocationDeps(Geocoder(cache, http), PlacesFinder(cache, http))
    return _location


def override_location(value: LocationDeps | None) -> None:
    """For tests: replace (or reset with None) the location services."""
    global _location
    _location = value


async def user_deps() -> UserDeps:
    user = current_user()
    db = await user_client(user)
    return UserDeps(
        user=user,
        profiles=ProfileRepo(db, user.user_id),
        feedback=FeedbackRepo(db, user.user_id),
        batches=BatchRepo(db, user.user_id),
    )
