from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError
from fastmcp.resources import ResourceContent, ResourceResult
from telethon import TelegramClient

from tg_mcp.client import TelegramClientDep
from tg_mcp.config import server_settings
from tg_mcp.tools._common import MEDIA_URI_TEMPLATE

mcp = FastMCP()


@mcp.resource(MEDIA_URI_TEMPLATE, name="message_media")
async def message_media(
    chat_id: int,
    message_id: int,
    client: TelegramClient = TelegramClientDep,
) -> ResourceResult:
    """File attached to a Telegram message (photo, video, voice, document, ...).

    URIs come from the `media.uri` field of messages returned by the tools.
    """
    msg = await client.get_messages(chat_id, ids=message_id)
    if msg is None or msg.file is None:
        raise ResourceError(f"Message {message_id} in chat {chat_id} has no attached file")
    if msg.file.size is not None and msg.file.size > server_settings.media_max_bytes:
        raise ResourceError(
            f"Attachment is {msg.file.size} bytes, over the "
            f"{server_settings.media_max_bytes} byte limit"
        )
    data = await client.download_media(msg, bytes)
    return ResourceResult(
        [ResourceContent(data, mime_type=msg.file.mime_type or "application/octet-stream")]
    )
