# tg-mcp

An [MCP](https://modelcontextprotocol.io/) server that exposes your **Telegram user account** (not a bot) over a streamable HTTP endpoint, built with [FastMCP](https://gofastmcp.com/) and [Telethon](https://docs.telethon.dev/).

It connects as you, using a Telethon `StringSession`, so tools operate on your real chats, dialogs and message history.

## Tools

| Tool | Description |
| --- | --- |
| `get_me` | Info about the logged-in account |
| `list_dialogs` | Recent dialogs (chats, groups, channels) with ids for the other tools |
| `get_chat_history` | Recent messages from a chat, newest first |
| `send_message` | Send a text message (optionally as a reply) |
| `search_messages` | Search messages in one chat or across the whole account |

`chat` arguments accept a numeric id, an `@username`, a phone number, or `"me"` (Saved Messages).

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Telegram **api_id** / **api_hash** from <https://my.telegram.org/apps>

## Setup

```bash
uv sync
cp .env.example .env   # fill in TELEGRAM_API_ID and TELEGRAM_API_HASH
```

Generate a session string by logging in once (phone code + 2FA if enabled):

```bash
python -m tg_mcp.session_generator
```

Copy the printed `TELEGRAM_SESSION_STRING=...` line into your `.env`.

> The session string grants full access to your account — keep it secret, never commit it.

## Running

Local:

```bash
python -m tg_mcp
# -> http://127.0.0.1:8000/mcp
```

Docker Compose:

```bash
docker compose up --build
```

The image binds to `0.0.0.0:8000` inside the container; credentials are read from `.env`.

## Configuration

All settings come from the environment (or `.env`).

| Variable | Default | Description |
| --- | --- | --- |
| `TELEGRAM_API_ID` | — | API id from my.telegram.org |
| `TELEGRAM_API_HASH` | — | API hash from my.telegram.org |
| `TELEGRAM_SESSION_STRING` | — | Telethon session string (see Setup) |
| `MCP_HOST` | `127.0.0.1` | HTTP bind host |
| `MCP_PORT` | `8000` | HTTP port |
| `MCP_PATH` | `/mcp` | HTTP endpoint path |

## Connecting an MCP client

A ready-to-use config is in `.mcp.json`:

```json
{
  "mcpServers": {
    "tg-mcp": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp"
    }
  }
}
```

## Project layout

```
tg_mcp/
├── server.py              # FastMCP app, lifespan, mounts the tool sub-servers
├── client.py              # Telethon client singleton + FastMCP dependency
├── config.py              # pydantic-settings (TELEGRAM_* and MCP_*)
├── models.py              # Pydantic result models
├── session_generator.py   # interactive login -> session string
└── tools/                 # one FastMCP sub-server per tool
    ├── get_me.py
    ├── list_dialogs.py
    ├── get_chat_history.py
    ├── send_message.py
    └── search_messages.py
```

The connected Telethon client is provided to tools through a FastMCP dependency
(`TelegramClientDep`), so each tool just declares `client: TelegramClient = TelegramClientDep`.

## Development

```bash
ruff check .
ruff format --check .
```

CI (GitHub Actions) runs ruff and, on `main`/tags, builds and pushes a multi-arch image to GHCR.
