from fastmcp import FastMCP
from telethon import TelegramClient

from tg_mcp.client import TelegramClientDep
from tg_mcp.models import MeInfo

mcp = FastMCP()


@mcp.tool
async def get_me(client: TelegramClient = TelegramClientDep) -> MeInfo:
    """Return information about the currently logged-in Telegram account."""
    me = await client.get_me()
    return MeInfo(
        id=me.id,
        first_name=me.first_name,
        last_name=me.last_name,
        username=me.username,
        phone=me.phone,
    )
