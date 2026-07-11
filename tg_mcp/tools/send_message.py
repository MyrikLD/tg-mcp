from fastmcp import FastMCP
from telethon import TelegramClient

from tg_mcp.client import TelegramClientDep, parse_chat
from tg_mcp.models import MessageInfo
from tg_mcp.tools._common import message_info

mcp = FastMCP()


@mcp.tool
async def send_message(
    chat: str,
    text: str,
    reply_to: int | None = None,
    client: TelegramClient = TelegramClientDep,
) -> MessageInfo:
    """Send a text message to a chat, as the logged-in user.

    `chat` may be a numeric id, an @username, a phone number, or "me".
    `reply_to` optionally references the id of a message to reply to.
    """
    entity = await client.get_entity(parse_chat(chat))
    sent = await client.send_message(entity, text, reply_to=reply_to)
    return message_info(sent)
