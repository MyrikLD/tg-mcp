from fastmcp import FastMCP
from telethon import TelegramClient

from tg_mcp.client import TelegramClientDep
from tg_mcp.models import DialogInfo

mcp = FastMCP()


@mcp.tool
async def list_dialogs(
    limit: int = 20,
    archived: bool = False,
    client: TelegramClient = TelegramClientDep,
) -> list[DialogInfo]:
    """List the most recent dialogs (chats, groups and channels).

    Use the returned `id` as the `chat` argument for other tools.
    """
    dialogs: list[DialogInfo] = []
    async for d in client.iter_dialogs(limit=limit, archived=archived):
        dialogs.append(
            DialogInfo(
                id=d.id,
                name=d.name or "",
                username=getattr(d.entity, "username", None),
                is_user=d.is_user,
                is_group=d.is_group,
                is_channel=d.is_channel,
                unread_count=d.unread_count,
                last_message_date=d.date,
            )
        )
    return dialogs
