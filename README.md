# tg-mcp

An [MCP](https://modelcontextprotocol.io/) server that exposes a **Telegram user account** (not a bot) over a streamable HTTP endpoint, built with [FastMCP](https://gofastmcp.com/) and [Telethon](https://docs.telethon.dev/).

It's multi-account: anyone can register a login on the server and link their own Telegram account to it. Each account maps to exactly one linked Telegram account, and tools always act on the caller's own linked account — never someone else's.

## Tools

| Tool | Description |
| --- | --- |
| `get_me` | Info about the logged-in account |
| `list_dialogs` | Recent dialogs (chats, groups, channels) with ids for the other tools |
| `get_chat_history` | Recent messages from a chat, newest first |
| `send_message` | Send a text message (optionally as a reply) |
| `search_messages` | Search messages in one chat or across the whole account |

`chat` arguments accept a numeric id, an `@username`, a phone number, or `"me"` (Saved Messages).

## Authentication

The MCP endpoint is protected by a self-hosted OAuth 2.1 authorization server (no third-party IdP). When an MCP client connects, it's redirected through a browser flow:

1. **Sign in or register** with a username and password.
2. **Link Telegram** (first time only): enter your phone number, the code Telegram sends you, and your two-factor password if you have one set. This is the same handshake the official Telegram apps use — nothing is stored until it succeeds.
3. The client gets back an access/refresh token pair (JWT, 1h/30d) scoped to your account.

Registration is open: anyone who can reach the `/login` page can create an account, but every account is only ever able to act on the Telegram account *they personally* linked to it. If you don't want that, put the server behind something that gates access first (reverse proxy auth, a gateway like ContextForge, network-level restriction, etc.) — this server doesn't do invite codes itself.

Linked Telegram sessions are stored encrypted at rest (Fernet, key from `MCP_SESSION_ENCRYPTION_KEY`). A leaked database dump is not enough to hijack an account; a leaked database dump *plus* the encryption key is.

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Telegram **api_id** / **api_hash** from <https://my.telegram.org/apps>
- PostgreSQL (accounts, OAuth clients, revoked tokens)

## Setup

```bash
uv sync
cp .env.example .env
```

Fill in `.env`:

- `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` — from my.telegram.org
- `MCP_BASE_URL` — how clients actually reach this server (used as the OAuth issuer)
- `MCP_DB_URL` — Postgres connection string
- `MCP_OAUTH_JWT_SECRET` — `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- `MCP_SESSION_ENCRYPTION_KEY` — `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

Tables are created automatically on startup (no migration step).

## Running

Local (requires a reachable Postgres, see `MCP_DB_URL`):

```bash
python -m tg_mcp
# -> http://127.0.0.1:8000/mcp
```

Docker Compose (bundles Postgres):

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
| `MCP_HOST` | `127.0.0.1` | HTTP bind host |
| `MCP_PORT` | `8000` | HTTP port |
| `MCP_PATH` | `/mcp` | HTTP endpoint path |
| `MCP_BASE_URL` | `http://127.0.0.1:8000` | Externally reachable base URL (OAuth issuer/audience, login links) |
| `MCP_DB_URL` | `postgresql+asyncpg://tgmcp:tgmcp@localhost/tgmcp` | Async SQLAlchemy URL for Postgres |
| `MCP_DB_ECHO` | `false` | Log SQL statements |
| `MCP_OAUTH_JWT_SECRET` | *(insecure default)* | Signs OAuth access/refresh tokens — change this |
| `MCP_SESSION_ENCRYPTION_KEY` | — | Fernet key encrypting stored Telegram sessions |

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

Clients that support the MCP OAuth flow will open a browser to `/login` automatically on first connection.

## Project layout

```
tg_mcp/
├── server.py               # FastMCP app, lifespan, mounts the tool sub-servers
├── oauth.py                 # OAuth 2.1 authorization server: login/register + Telegram linking
├── telegram_login.py        # phone/code/2FA handshake used by the linking flow
├── client.py                 # per-account Telethon client cache + FastMCP dependency
├── auth.py                   # password hashing, session encryption, caller resolution
├── config.py                  # pydantic-settings (TELEGRAM_* and MCP_*)
├── db.py                      # async engine/session, schema creation
├── models.py                  # Pydantic result models returned by tools
├── orm/                       # SQLAlchemy models: User, OAuthClient, RevokedToken
├── dao/                       # data-access objects
├── utils/                     # OAuth protocol helpers
└── tools/                     # one FastMCP sub-server per tool
    ├── get_me.py
    ├── list_dialogs.py
    ├── get_chat_history.py
    ├── send_message.py
    └── search_messages.py
```

The connected Telethon client for the calling account is provided to tools through a FastMCP dependency (`TelegramClientDep`), so each tool just declares `client: TelegramClient = TelegramClientDep`.

## Development

```bash
ruff check .
ruff format --check .
```

CI (GitHub Actions) runs ruff and, on `main`/tags, builds and pushes a multi-arch image to GHCR.
