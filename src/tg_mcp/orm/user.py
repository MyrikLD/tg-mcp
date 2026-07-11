import sqlalchemy as sa

from tg_mcp.orm.base import Base


class User(Base):
    """An account on this MCP server. One account maps to at most one linked
    Telegram user account (1:1) — the account's password gates OAuth login,
    the linked Telegram session is what the tools act on once linked."""

    __tablename__ = "users"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    username = sa.Column(sa.Text, unique=True, nullable=False)
    hashed_password = sa.Column(sa.Text, nullable=False)

    # Populated once the user completes the phone/code/2FA linking flow.
    # telegram_session_enc is a Fernet-encrypted Telethon StringSession.
    telegram_session_enc = sa.Column(sa.Text, nullable=True)
    telegram_user_id = sa.Column(sa.BigInteger, nullable=True)
    telegram_phone = sa.Column(sa.Text, nullable=True)
    telegram_display_name = sa.Column(sa.Text, nullable=True)

    created_at = sa.Column(
        sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (sa.Index("ix_users_username", "username", unique=True),)
