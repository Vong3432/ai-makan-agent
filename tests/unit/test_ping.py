from fastmcp import Client

from makan.config import get_settings
from makan.server import create_mcp


async def test_ping_returns_dev_user() -> None:
    async with Client(create_mcp()) as client:
        result = await client.call_tool("ping", {})
    assert result.data == {"status": "ok", "user_id": get_settings().dev_user_id}
