from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from tg_mcp.client import disconnect_all_clients
from tg_mcp.config import get_server_settings, server_settings
from tg_mcp.db import dispose_engine, init_db, session
from tg_mcp.oauth import TgMcpOAuthProvider
from tg_mcp.tools import (
    get_chat_history,
    get_me,
    list_dialogs,
    search_messages,
    send_message,
)


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[None]:
    await init_db()
    try:
        yield
    finally:
        await disconnect_all_clients()
        await dispose_engine()


mcp = FastMCP(
    "tg-mcp",
    lifespan=lifespan,
    auth=TgMcpOAuthProvider(
        base_url=server_settings.base_url,
        jwt_secret=server_settings.oauth_jwt_secret,
        session_factory=session,
    ),
)

mcp.mount(get_me)
mcp.mount(list_dialogs)
mcp.mount(get_chat_history)
mcp.mount(send_message)
mcp.mount(search_messages)


def main() -> None:
    mcp.run(
        transport="http",
        host=server_settings.host,
        port=server_settings.port,
        path=server_settings.path,
    )


if __name__ == "__main__":
    main()
