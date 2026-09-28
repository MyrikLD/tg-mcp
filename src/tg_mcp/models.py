from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field
from telethon.tl.custom import Dialog, Message


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


class MediaType(StrEnum):
    PHOTO = "photo"
    VIDEO = "video"
    VIDEO_NOTE = "video_note"
    GIF = "gif"
    VOICE = "voice"
    AUDIO = "audio"
    STICKER = "sticker"
    DOCUMENT = "document"

    @classmethod
    def get(cls, msg: Message) -> "MediaType":
        # Stickers, GIFs and video notes are also videos/documents, so the
        # more specific kinds are checked first.
        if msg.sticker:
            return cls.STICKER
        if msg.gif:
            return cls.GIF
        if msg.video_note:
            return cls.VIDEO_NOTE
        if msg.video:
            return cls.VIDEO
        if msg.voice:
            return cls.VOICE
        if msg.audio:
            return cls.AUDIO
        if msg.photo:
            return cls.PHOTO
        return cls.DOCUMENT


class MediaInfo(BaseModel):
    media_type: MediaType = Field(description="Kind of the attached file")
    uri: str = Field(description="MCP resource URI to read the file contents from")
    mime_type: str | None = Field(default=None, description="MIME type of the file")
    file_name: str | None = Field(default=None, description="Original file name, if any")
    size: int | None = Field(default=None, description="File size in bytes")
    width: int | None = Field(default=None, description="Width in pixels (photos and videos)")
    height: int | None = Field(default=None, description="Height in pixels (photos and videos)")


class MessageInfo(BaseModel):
    id: int = Field(description="Message id within its chat")
    date: datetime | None = Field(default=None, description="When the message was sent")
    sender_name: str | None = Field(default=None, description="Display name of the sender")
    text: str = Field(
        description="Text body of the message, or the caption for media (may be empty)"
    )
    outgoing: bool = Field(description="True if the message was sent by the logged-in account")
    reply_to_msg_id: int | None = Field(
        default=None, description="Id of the message this one replies to, if any"
    )
    media: MediaInfo | None = Field(
        default=None, description="Attached file, if the message carries one"
    )
