from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from telethon import TelegramClient

from tg_mcp.client import TelegramClientDep, parse_chat
from tg_mcp.models import MessageInfo
from tg_mcp.tools._common import message_info

mcp = FastMCP()


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def search_messages(
    query: str,
    chat: str | None = None,
    limit: int = 20,
    client: TelegramClient = TelegramClientDep,
) -> list[MessageInfo]:
    """Search messages by text.

    If `chat` is given, search only within that chat; otherwise search across
    all chats of the account.
    """
    entity = await client.get_entity(parse_chat(chat)) if chat else None
    messages: list[MessageInfo] = []
    async for msg in client.iter_messages(entity, search=query, limit=limit):
        messages.append(message_info(msg))
    return messages
