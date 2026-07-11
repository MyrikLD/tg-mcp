import sqlalchemy as sa

from tg_mcp.orm.base import Base


class RevokedToken(Base):
    """JWT jti blocklist. Survives restarts and works across multiple
    server instances, unlike an in-memory set."""

    __tablename__ = "revoked_tokens"

    jti = sa.Column(sa.String(255), primary_key=True)
    expires_at = sa.Column(sa.DateTime(timezone=False), nullable=False)
