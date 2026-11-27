"""FastMCP server: app construction and tool registration."""

from fastmcp import FastMCP
from starlette.applications import Starlette

from makan.auth import build_auth_provider, current_user
from makan.config import get_settings

INSTRUCTIONS = (
    "AI Makan Agent recommends meals (breakfast, lunch, tea, dinner, supper) "
    "personalised to the user's habits, preferences and allergies, near a location "
    "the user gives."
)


def create_mcp() -> FastMCP:
    settings = get_settings()
    mcp = FastMCP(
        name="ai-makan-agent",
        instructions=INSTRUCTIONS,
        auth=build_auth_provider(settings),
    )

    @mcp.tool
    def ping() -> dict[str, str]:
        """Health check. Returns 'ok' and the caller's user id."""
        return {"status": "ok", "user_id": current_user().user_id}

    return mcp


def create_http_app() -> Starlette:
    """ASGI factory used by uvicorn (`--factory`)."""
    return create_mcp().http_app(path="/mcp")


def main() -> None:
    settings = get_settings()
    create_mcp().run(transport="http", host=settings.host, port=settings.port, path="/mcp")


if __name__ == "__main__":
    main()
