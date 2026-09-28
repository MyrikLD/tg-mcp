from fastmcp.tools import ToolResult
from mcp.types import ResourceLink, TextContent
from pydantic import BaseModel, TypeAdapter
from telethon import utils
from telethon.tl.custom import Message

from tg_mcp.models import MediaInfo, MediaType, MessageInfo

MEDIA_URI_TEMPLATE = "tg://chat/{chat_id}/message/{message_id}/media"


def media_info(msg: Message) -> MediaInfo | None:
    file = msg.file
    if file is None:
        return None
    return MediaInfo(
        media_type=MediaType.get(msg),
        uri=MEDIA_URI_TEMPLATE.format(chat_id=msg.chat_id, message_id=msg.id),
        mime_type=file.mime_type,
        file_name=file.name,
        size=file.size,
        width=file.width,
        height=file.height,
    )


def message_info(msg: Message) -> MessageInfo:
    sender_name = None
    if msg.sender is not None:
        sender_name = utils.get_display_name(msg.sender) or None
    return MessageInfo(
        id=msg.id,
        date=msg.date,
        sender_name=sender_name,
        text=msg.message or "",
        outgoing=bool(msg.out),
        reply_to_msg_id=msg.reply_to_msg_id,
        media=media_info(msg),
    )


def _resource_link(message: MessageInfo) -> ResourceLink | None:
    media = message.media
    if media is None:
        return None
    return ResourceLink(
        type="resource_link",
        uri=media.uri,
        name=media.file_name or f"{media.media_type}-{message.id}",
        mime_type=media.mime_type,
        size=media.size,
    )


class _MessageList(BaseModel):
    result: list[MessageInfo]


# Same shape FastMCP generates for a `-> list[MessageInfo]` annotation; it has to
# be spelled out because these tools return a ToolResult to attach resource links.
MESSAGE_LIST_SCHEMA = {**_MessageList.model_json_schema(), "x-fastmcp-wrap-result": True}

_message_list_adapter = TypeAdapter(list[MessageInfo])


def message_list_result(messages: list[MessageInfo]) -> ToolResult:
    """Tool result for a list of messages, with a resource link per attached file."""
    links = [link for m in messages if (link := _resource_link(m)) is not None]
    return ToolResult(
        content=[
            TextContent(type="text", text=_message_list_adapter.dump_json(messages).decode()),
            *links,
        ],
        structured_content={"result": _message_list_adapter.dump_python(messages, mode="json")},
        meta={"fastmcp": {"wrap_result": True}},
    )
