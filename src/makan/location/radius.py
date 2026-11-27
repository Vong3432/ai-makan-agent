"""Travel radius: profile default, overridden by phrases in the request (P4-T6). Pure."""

import re

DEFAULT_RADIUS_KM = 3.0
WALKING_KM = 1.0
DRIVING_KM = 10.0
MIN_RADIUS_KM = 0.2
MAX_RADIUS_KM = 50.0  # Places API maximum

_EXPLICIT = re.compile(r"(\d+(?:\.\d+)?)\s*(km|kilometers?|kilometres?|m|meters?|metres?)\b", re.I)
_WALK = re.compile(r"\b(walk(?:ing|able)?|on foot|stroll)\b", re.I)
_DRIVE = re.compile(r"\b(driv(?:e|ing)|by car|willing to travel|don'?t mind travel)", re.I)


def clamp(km: float) -> float:
    return min(MAX_RADIUS_KM, max(MIN_RADIUS_KM, km))


def radius_from_request(request: str | None) -> float | None:
    """Radius implied by the request text, or None if it says nothing about distance.

    An explicit distance ("within 2 km", "500m") wins over walking/driving phrases.
    """
    if not request:
        return None
    if m := _EXPLICIT.search(request):
        value = float(m[1])
        km = value if m[2].lower().startswith("k") else value / 1000
        if km > 0:
            return clamp(km)
    if _WALK.search(request):
        return WALKING_KM
    if _DRIVE.search(request):
        return DRIVING_KM
    return None


def resolve_radius(profile_default_km: float | None, request: str | None) -> float:
    if (km := radius_from_request(request)) is not None:
        return km
    if profile_default_km and profile_default_km > 0:
        return clamp(profile_default_km)
    return DEFAULT_RADIUS_KM
