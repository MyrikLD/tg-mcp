from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from telethon import TelegramClient

from tg_mcp.client import TelegramClientDep
from tg_mcp.models import DialogInfo, DialogType

mcp = FastMCP()


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def list_dialogs(
    dialog_types: list[DialogType] | None = None,
    limit: int = 20,
    archived: bool = False,
    client: TelegramClient = TelegramClientDep,
) -> list[DialogInfo]:
    """List the most recent dialogs (chats, groups and channels).

    Only the first `limit` dialogs are returned, so a chat missing from the
    result may still exist.

    `dialog_types` keeps only dialogs of the given types, e.g. `["user", "group"]`
    for conversations with people without channels. Channels with many unread
    posts otherwise crowd personal chats out of the result.

    Use the returned `id` as the `chat` argument for other tools.
    """
    dialogs: list[DialogInfo] = []
    async for d in client.iter_dialogs(archived=archived):
        dialog_type = DialogType.get(d)
        if dialog_types and dialog_type not in dialog_types:
            continue
        dialogs.append(
            DialogInfo(
                id=d.id,
                name=d.name or "",
                dialog_type=dialog_type,
                username=getattr(d.entity, "username", None),
                unread_count=d.unread_count,
                last_message_date=d.date,
            )
        )
        if len(dialogs) >= limit:
            break
    return dialogs
