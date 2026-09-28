from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from mcp.types import ToolAnnotations
from telethon import TelegramClient

from tg_mcp.client import TelegramClientDep, parse_chat
from tg_mcp.models import MessageInfo
from tg_mcp.tools._common import MESSAGE_LIST_SCHEMA, message_info, message_list_result

mcp = FastMCP()


@mcp.tool(
    output_schema=MESSAGE_LIST_SCHEMA,
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def get_chat_history(
    chat: str,
    limit: int = 20,
    client: TelegramClient = TelegramClientDep,
) -> ToolResult:
    """Fetch the most recent messages from a chat, newest first.

    `chat` may be a numeric id, an @username, a phone number, or "me"
    (the Saved Messages chat).
    """
    entity = await client.get_entity(parse_chat(chat))
    messages: list[MessageInfo] = []
    async for msg in client.iter_messages(entity, limit=limit):
        messages.append(message_info(msg))
    return message_list_result(messages)
