
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Shared Telegram application credentials (from https://my.telegram.org/apps).

    These belong to the *application*, not to any individual account — every
    linked account authenticates through the same api_id/api_hash pair.
    """

    model_config = SettingsConfigDict(
        env_prefix="TELEGRAM_",
        env_file=".env",
        extra="ignore",
    )

    api_id: int = Field(description="Telegram API ID from https://my.telegram.org/apps")
    api_hash: str = Field(description="Telegram API hash from https://my.telegram.org/apps")


class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        env_file=".env",
        extra="ignore",
    )

    host: str = Field(default="0.0.0.0", description="Host the HTTP server binds to")
    port: int = Field(default=8000, description="Port the HTTP server listens on")
    path: str = Field(default="/mcp", description="HTTP path the MCP endpoint is served at")
    base_url: str = Field(
        default="http://127.0.0.1:8000",
        description="Externally reachable base URL, used as the OAuth issuer/audience "
        "and for building login links. Must match how clients actually reach this server.",
    )

    db_url: str = Field(
        default="postgresql+asyncpg://tgmcp:tgmcp@127.0.0.1:5432/tgmcp",
        description="Async SQLAlchemy URL for the Postgres database storing accounts, "
        "OAuth clients and revoked tokens",
    )
    db_echo: bool = Field(default=False, description="Log SQL statements (debugging)")

    oauth_jwt_secret: str = Field(
        default="tg-mcp-dev-secret-please-change",
        description="High-entropy secret used to derive the JWT signing key for "
        "OAuth access/refresh tokens. Change this in production.",
    )
    session_encryption_key: str = Field(
        description="Fernet key (44-char urlsafe base64) used to encrypt Telethon "
        "session strings at rest. Generate with: "
        "python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'",
    )


settings = Settings()


server_settings = ServerSettings()
