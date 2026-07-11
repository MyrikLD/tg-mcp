from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TELEGRAM_",
        env_file=".env",
        extra="ignore",
    )

    api_id: int = Field(description="Telegram API ID from https://my.telegram.org/apps")
    api_hash: str = Field(description="Telegram API hash from https://my.telegram.org/apps")
    session_string: str = Field(
        default="",
        description="Telethon StringSession for the user account (generated via session_generator)",
    )


class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        env_file=".env",
        extra="ignore",
    )

    host: str = Field(default="127.0.0.1", description="Host the HTTP server binds to")
    port: int = Field(default=8000, description="Port the HTTP server listens on")
    path: str = Field(default="/mcp", description="HTTP path the MCP endpoint is served at")


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_server_settings() -> ServerSettings:
    return ServerSettings()
