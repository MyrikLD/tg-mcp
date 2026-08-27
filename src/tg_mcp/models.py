from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field
from telethon.tl.custom import Dialog


class DialogType(StrEnum):
    USER = "user"
    GROUP = "group"
    CHANNEL = "channel"

    @classmethod
    def get(cls, dialog: Dialog) -> "DialogType":
        if dialog.is_user:
            return cls.USER
        if dialog.is_group:
            return cls.GROUP
        if dialog.is_channel:
            return cls.CHANNEL
        raise ValueError("Invalid dialog type")


class MeInfo(BaseModel):
    id: int = Field(description="Telegram user id of the logged-in account")
    first_name: str | None = Field(default=None, description="First name")
    last_name: str | None = Field(default=None, description="Last name")
    username: str | None = Field(default=None, description="Public @username, if set")
    phone: str | None = Field(default=None, description="Phone number in international format")


class DialogInfo(BaseModel):
    id: int = Field(description="Chat/peer id usable as the `chat` argument of other tools")
    name: str = Field(description="Display name of the dialog")
    username: str | None = Field(default=None, description="Public @username, if any")
    dialog_type: DialogType = Field(description="Type of the dialog")
    unread_count: int = Field(description="Number of unread messages")
    last_message_date: datetime | None = Field(
        default=None, description="Timestamp of the most recent message"
    )


class MessageInfo(BaseModel):
    id: int = Field(description="Message id within its chat")
    date: datetime | None = Field(default=None, description="When the message was sent")
    sender_name: str | None = Field(default=None, description="Display name of the sender")
    text: str = Field(description="Text body of the message (empty for media-only messages)")
    outgoing: bool = Field(description="True if the message was sent by the logged-in account")
    reply_to_msg_id: int | None = Field(
        default=None, description="Id of the message this one replies to, if any"
    )
