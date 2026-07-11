from datetime import datetime

from pydantic import BaseModel, Field


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
    is_user: bool = Field(description="True for a private one-to-one chat")
    is_group: bool = Field(description="True for a basic group or megagroup")
    is_channel: bool = Field(description="True for a broadcast channel")
    unread_count: int = Field(description="Number of unread messages")
    last_message_date: datetime | None = Field(
        default=None, description="Timestamp of the most recent message"
    )


class MessageInfo(BaseModel):
    id: int = Field(description="Message id within its chat")
    chat_id: int = Field(description="Id of the chat the message belongs to")
    date: datetime | None = Field(default=None, description="When the message was sent")
    sender_id: int | None = Field(default=None, description="User/peer id of the sender")
    sender_name: str | None = Field(default=None, description="Display name of the sender")
    text: str = Field(description="Text body of the message (empty for media-only messages)")
    outgoing: bool = Field(description="True if the message was sent by the logged-in account")
    reply_to_msg_id: int | None = Field(
        default=None, description="Id of the message this one replies to, if any"
    )
