from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import cache

from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from telethon import TelegramClient
from telethon.sessions import StringSession

from tg_mcp.config import get_settings


@cache
def get_telegram_client() -> TelegramClient:
    """Build the singleton Telethon user client (not yet connected)."""
    settings = get_settings()
    if not settings.session_string:
        raise RuntimeError(
            "TELEGRAM_SESSION_STRING is not set. "
            "Generate one with: python -m tg_mcp.session_generator"
        )
    return TelegramClient(
        StringSession(settings.session_string),
        settings.api_id,
        settings.api_hash,
    )


async def provide_client() -> TelegramClient:
    """Dependency: return the connected, authorized Telethon client.

    Resolved per tool call but backed by a single shared connection, so it
    works for tools mounted from sub-servers (unlike lifespan context).
    """
    client = get_telegram_client()
    if not client.is_connected():
        await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError(
            "Telegram session is not authorized. "
            "Regenerate the session string with: python -m tg_mcp.session_generator"
        )
    return client


TelegramClientDep = Depends(provide_client)


@asynccontextmanager
async def telegram_lifespan(server: FastMCP) -> AsyncIterator[None]:
    """Connect the client on startup and disconnect it on shutdown."""
    client = get_telegram_client()
    await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError(
            "Telegram session is not authorized. "
            "Regenerate the session string with: python -m tg_mcp.session_generator"
        )
    try:
        yield
    finally:
        await client.disconnect()


def parse_chat(chat: str) -> str | int:
    """Normalize a chat identifier: numeric ids become int, everything else
    (usernames, phone numbers, ``"me"``) is passed through as-is."""
    chat = chat.strip()
    if chat.lstrip("-").isdigit():
        return int(chat)
    return chat
