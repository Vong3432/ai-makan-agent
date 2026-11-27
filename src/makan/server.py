"""FastMCP server: app construction and tool registration."""

from datetime import UTC, datetime
from typing import Any

from fastmcp import FastMCP
from starlette.applications import Starlette

from makan import deps
from makan.auth import build_auth_provider, current_user
from makan.config import get_settings
from makan.tools import feedback as feedback_tools
from makan.tools import profile as profile_tools
from makan.tools import recommend as recommend_tools

INSTRUCTIONS = (
    "AI Makan Agent recommends meals (breakfast, lunch, tea, dinner, supper) "
    "personalised to the user's habits, preferences and allergies, near a location "
    "the user gives. Pass the user's own words to tools; the server interprets them. "
    "Always show the user the `message` field of tool results."
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

    @mcp.tool
    async def recommend_meal(
        location: str, meal_slot: str | None = None, request: str | None = None
    ) -> dict[str, Any]:
        """Recommend 3 meal options (dish + a nearby place) personalised to the user.

        - `location` (required): where the user is or will eat, in their words, e.g.
          "Bangsar" or "near KLCC". Ask the user if you don't know it.
        - `meal_slot`: breakfast | lunch | tea | dinner | supper. Omit to infer from the
          local time at the location.
        - `request`: optional nuance in the user's words, e.g. "something soupy",
          "walking distance", "can drive".

        Show the user the returned `message`. If `status` is "needs_onboarding", ask the
        listed questions and save the answers with update_profile, then try again. If
        `suggested_radius_km` is set, offer to search again with that radius (pass it in
        `request`, e.g. "within 6 km"). Never drop an `allergen_note`. Keep each place's
        `maps_url` so the user can open it.
        """
        d = await deps.user_deps()
        loc = await deps.location_deps()
        return await recommend_tools.recommend_meal(
            location,
            meal_slot,
            request,
            user_id=d.user.user_id,
            llm=deps.llm(),
            profiles=d.profiles,
            feedback=d.feedback,
            batches=d.batches,
            geocoder=loc.geocoder,
            places=loc.places,
            now=datetime.now(UTC),
        )

    @mcp.tool
    async def give_feedback(message: str) -> dict[str, Any]:
        """Record how a meal was, in the user's own words, so future picks learn from it.

        Use when the user says how a recommended (or any other) meal was, e.g. "the laksa
        was great", "first one too oily", "had nasi lemak today, loved it". Several meals in
        one message are fine. Pass the message as-is.

        Show the user the returned `message`. If `profile_hint` is set, the user stated an
        allergy, dietary rule or other profile fact: confirm it with them and call
        update_profile — feedback never changes allergies or dietary rules.
        """
        d = await deps.user_deps()
        return await feedback_tools.give_feedback(
            message, llm=deps.llm(), feedback=d.feedback, batches=d.batches
        )

    @mcp.tool
    async def update_profile(message: str) -> dict[str, Any]:
        """Update the user's food profile from what they said, in their own words.

        Use whenever the user states allergies, dietary rules (halal, vegetarian, no beef…),
        foods they love or dislike, budget per meal, how far they'll travel, spice tolerance,
        meals they usually skip, dine-in vs delivery, health goals, or usual meal times.
        Also use to answer onboarding questions.

        Show the user the returned `message`. If `safety_changes` is not empty, ask the user
        to confirm them (allergies and dietary rules are safety-critical).
        """
        d = await deps.user_deps()
        return await profile_tools.update_profile(
            message,
            user_id=d.user.user_id,
            llm=deps.llm(),
            profiles=d.profiles,
            feedback=d.feedback,
        )

    @mcp.tool
    async def get_profile() -> dict[str, Any]:
        """Show what the agent knows about the user: allergies, dietary rules, habits,
        top learned likes/dislikes, and any onboarding questions still unanswered."""
        d = await deps.user_deps()
        return await profile_tools.get_profile(
            user_id=d.user.user_id,
            profiles=d.profiles,
            feedback=d.feedback,
            now=datetime.now(UTC),
        )

    return mcp


def create_http_app() -> Starlette:
    """ASGI factory used by uvicorn (`--factory`)."""
    return create_mcp().http_app(path="/mcp")


def main() -> None:
    settings = get_settings()
    create_mcp().run(transport="http", host=settings.host, port=settings.port, path="/mcp")


if __name__ == "__main__":
    main()
