import logging

from fastmcp.dependencies import Depends
from telethon import TelegramClient
from telethon.sessions import StringSession

from tg_mcp.auth import MCPUserDep, decrypt_session
from tg_mcp.config import settings
from tg_mcp.dao.user import UserDao
from tg_mcp.db import session

logger = logging.getLogger(__name__)

# One connected Telethon client per authenticated account, kept alive across
# tool calls. Telegram accounts are 1:1 with accounts on this server, so this
# cache never mixes sessions between users.
_clients: dict[int, TelegramClient] = {}


async def provide_client(user_id: int = MCPUserDep) -> TelegramClient:
    """Dependency: return the connected, authorized Telethon client for the
    calling account, connecting it on first use."""
    client = _clients.get(user_id)
    if client is None:
        async with session() as s:
            encrypted = await UserDao(s).get_encrypted_session(user_id)
        if encrypted is None:
            raise RuntimeError(
                "No Telegram account linked to this login yet. "
                "Sign in again through the browser to complete the linking flow."
            )
        client = TelegramClient(
            StringSession(decrypt_session(encrypted)),
            settings.api_id,
            settings.api_hash,
        )
        _clients[user_id] = client

    if not client.is_connected():
        await client.connect()
    if not await client.is_user_authorized():
        # The linked session was revoked on Telegram's side (logged out
        # remotely, etc.) — drop it so a fresh connect is attempted next time.
        del _clients[user_id]
        raise RuntimeError(
            "Telegram session is no longer authorized. Sign in again through the "
            "browser to re-link the account."
        )
    return client


TelegramClientDep = Depends(provide_client)


async def disconnect_all_clients() -> None:
    for user_id, client in list(_clients.items()):
        try:
            await client.disconnect()
        except Exception:
            logger.exception("client: error disconnecting client for user_id=%d", user_id)
    _clients.clear()


def parse_chat(chat: str) -> str | int:
    """Normalize a chat identifier: numeric ids become int, everything else
    (usernames, phone numbers, ``"me"``) is passed through as-is."""
    chat = chat.strip()
    if chat.lstrip("-").isdigit():
        return int(chat)
    return chat
