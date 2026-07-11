from fastmcp import FastMCP

from tg_mcp.client import telegram_lifespan
from tg_mcp.config import get_server_settings
from tg_mcp.tools import (
    get_chat_history,
    get_me,
    list_dialogs,
    search_messages,
    send_message,
)

mcp = FastMCP("tg-mcp", lifespan=telegram_lifespan)

mcp.mount(get_me)
mcp.mount(list_dialogs)
mcp.mount(get_chat_history)
mcp.mount(send_message)
mcp.mount(search_messages)


def main() -> None:
    settings = get_server_settings()
    mcp.run(transport="http", host=settings.host, port=settings.port, path=settings.path)


if __name__ == "__main__":
    main()
