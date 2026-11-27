"""Authentication: dev mode (fixed user) or Supabase OAuth 2.1 (P2)."""

from dataclasses import dataclass

from fastmcp.server.auth import AuthProvider
from fastmcp.server.dependencies import get_access_token

from makan.config import Settings, get_settings


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    access_token: str | None  # None in dev mode


def build_auth_provider(settings: Settings) -> AuthProvider | None:
    if settings.auth_mode == "dev":
        return None
    raise NotImplementedError("Supabase OAuth is implemented in P2.")


def current_user() -> CurrentUser:
    """Resolve the caller. Works in both auth modes."""
    settings = get_settings()
    if settings.auth_mode == "dev":
        return CurrentUser(user_id=settings.dev_user_id, access_token=None)

    token = get_access_token()
    if token is None or not token.claims.get("sub"):
        raise PermissionError("Not authenticated.")
    return CurrentUser(user_id=token.claims["sub"], access_token=token.token)
