from telethon import utils

from tg_mcp.models import MessageInfo


def message_info(msg) -> MessageInfo:
    sender_name = None
    if msg.sender is not None:
        sender_name = utils.get_display_name(msg.sender) or None
    return MessageInfo(
        id=msg.id,
        chat_id=msg.chat_id,
        date=msg.date,
        sender_id=msg.sender_id,
        sender_name=sender_name,
        text=msg.message or "",
        outgoing=bool(msg.out),
        reply_to_msg_id=msg.reply_to_msg_id,
    )
