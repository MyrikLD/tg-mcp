import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from tg_mcp.orm.base import Base


class OAuthClient(Base):
    """Registered MCP client (via RFC 7591 dynamic client registration),
    linked to the account that authenticated it once login/linking completes."""

    __tablename__ = "oauth_clients"

    client_id = sa.Column(sa.String(255), primary_key=True)
    data = sa.Column(JSONB, nullable=False)
    user_id = sa.Column(sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    created_at = sa.Column(
        sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=False
    )
