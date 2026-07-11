from contextlib import asynccontextmanager
from functools import cache

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from fastmcp.dependencies import Depends as MCPDepends
from fastmcp.server.dependencies import get_access_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tg_mcp.config import server_settings
from tg_mcp.db import MCPSessionDep
from tg_mcp.orm.oauth_client import OAuthClient


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


@cache
def _fernet() -> Fernet:
    key = server_settings.session_encryption_key
    if not key:
        raise RuntimeError(
            "MCP_SESSION_ENCRYPTION_KEY is not set. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode())


def encrypt_session(raw_session_string: str) -> str:
    return _fernet().encrypt(raw_session_string.encode()).decode()


def decrypt_session(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError(
            "Failed to decrypt stored Telegram session — MCP_SESSION_ENCRYPTION_KEY "
            "may have changed since it was linked. Re-link the Telegram account."
        ) from exc


async def _current_user_gen(
    s: AsyncSession = MCPSessionDep,  # type: ignore[assignment]
):
    access_token = get_access_token()
    if access_token is None:
        raise PermissionError("Authentication required")
    user_id = await s.scalar(
        select(OAuthClient.user_id).where(OAuthClient.client_id == access_token.client_id)
    )
    if user_id is None:
        raise PermissionError("Unauthenticated")
    yield user_id


# Resolves to the `users.id` of the caller, based on the bearer access token
# presented to the MCP endpoint. Depend on this in any tool/dependency that
# needs to know which account is calling.
MCPUserDep = MCPDepends(asynccontextmanager(_current_user_gen))
