from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from tg_mcp.auth import verify_password
from tg_mcp.orm.user import User


@dataclass
class UserInfo:
    id: int
    username: str
    telegram_linked: bool
    telegram_phone: str | None
    telegram_display_name: str | None


class UserDao:
    def __init__(self, s: AsyncSession) -> None:
        self._s = s

    async def exists_by_username(self, username: str) -> bool:
        result = await self._s.scalar(
            select(User.id).where(User.username == username.strip().lower())
        )
        return result is not None

    async def authenticate(self, username: str, password: str) -> UserInfo | None:
        row = (
            (
                await self._s.execute(
                    select(
                        User.id,
                        User.username,
                        User.hashed_password,
                        User.telegram_session_enc,
                        User.telegram_phone,
                        User.telegram_display_name,
                    ).where(User.username == username.strip().lower())
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None or not verify_password(password, row["hashed_password"]):
            return None
        return UserInfo(
            id=row["id"],
            username=row["username"],
            telegram_linked=row["telegram_session_enc"] is not None,
            telegram_phone=row["telegram_phone"],
            telegram_display_name=row["telegram_display_name"],
        )

    async def create(self, username: str, hashed_password: str) -> UserInfo:
        user_id = await self._s.scalar(
            pg_insert(User)
            .values(username=username.strip().lower(), hashed_password=hashed_password)
            .returning(User.id)
        )
        assert user_id is not None
        return UserInfo(
            id=user_id,
            username=username.strip().lower(),
            telegram_linked=False,
            telegram_phone=None,
            telegram_display_name=None,
        )

    async def get_by_id(self, user_id: int) -> UserInfo | None:
        row = (
            (
                await self._s.execute(
                    select(
                        User.id,
                        User.username,
                        User.telegram_session_enc,
                        User.telegram_phone,
                        User.telegram_display_name,
                    ).where(User.id == user_id)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return UserInfo(
            id=row["id"],
            username=row["username"],
            telegram_linked=row["telegram_session_enc"] is not None,
            telegram_phone=row["telegram_phone"],
            telegram_display_name=row["telegram_display_name"],
        )

    async def get_encrypted_session(self, user_id: int) -> str | None:
        return await self._s.scalar(select(User.telegram_session_enc).where(User.id == user_id))

    async def set_telegram_session(
        self,
        user_id: int,
        encrypted_session: str,
        telegram_user_id: int,
        phone: str | None,
        display_name: str | None,
    ) -> None:
        await self._s.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                telegram_session_enc=encrypted_session,
                telegram_user_id=telegram_user_id,
                telegram_phone=phone,
                telegram_display_name=display_name,
            )
        )

    async def clear_telegram_session(self, user_id: int) -> None:
        await self._s.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                telegram_session_enc=None,
                telegram_user_id=None,
                telegram_phone=None,
                telegram_display_name=None,
            )
        )
