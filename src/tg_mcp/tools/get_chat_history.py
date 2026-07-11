from fastmcp import FastMCP
from telethon import TelegramClient

from tg_mcp.client import TelegramClientDep, parse_chat
from tg_mcp.models import MessageInfo
from tg_mcp.tools._common import message_info

mcp = FastMCP()


@mcp.tool
async def get_chat_history(
    chat: str,
    limit: int = 20,
    client: TelegramClient = TelegramClientDep,
) -> list[MessageInfo]:
    """Fetch the most recent messages from a chat, newest first.

    `chat` may be a numeric id, an @username, a phone number, or "me"
    (the Saved Messages chat).
    """
    entity = await client.get_entity(parse_chat(chat))
    messages: list[MessageInfo] = []
    async for msg in client.iter_messages(entity, limit=limit):
        messages.append(message_info(msg))
    return messages
