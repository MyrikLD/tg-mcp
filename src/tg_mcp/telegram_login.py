"""Phone/code/2FA Telegram account linking, used by the OAuth login web flow.

Telethon ties a code request to the specific client/session instance that
made it (Telegram may migrate the connection to another data center as part
of the login), so the same `TelegramClient` object must be reused across the
send_code_request -> sign_in(code) -> sign_in(password) steps. We hold one
live, connected client per in-progress linking attempt, keyed by the same
`pending_id` the OAuth flow already uses, and tear it down once the attempt
finishes or expires.
"""

import logging
import time

from pydantic import BaseModel
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberBannedError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)
from telethon.sessions import StringSession

from tg_mcp.config import settings

logger = logging.getLogger(__name__)

LINK_ATTEMPT_TTL = 600  # 10 minutes to complete phone -> code -> (2fa) -> done


class LinkError(Exception):
    """User-facing error message for the current step of the linking form."""


class LinkedAccount(BaseModel):
    session_string: str
    telegram_user_id: int
    phone: str | None
    display_name: str | None


class _LinkAttempt(BaseModel):
    client: TelegramClient
    phone: str
    phone_code_hash: str
    needs_password: bool
    expires_at: float

    class Config:
        arbitrary_types_allowed = True


class TelegramLinker:
    """In-memory registry of in-progress Telegram account links."""

    def __init__(self) -> None:
        self._attempts: dict[str, _LinkAttempt] = {}

    def _sweep_expired(self) -> None:
        now = time.time()
        expired = [pid for pid, a in self._attempts.items() if a.expires_at < now]
        for pid in expired:
            attempt = self._attempts.pop(pid)
            logger.info("telegram_login: link attempt %s... expired, disconnecting", pid[:8])
            try:
                attempt.client.disconnect()
            except Exception:
                logger.exception("telegram_login: error disconnecting expired client")

    async def start(self, pending_id: str, phone: str) -> None:
        """Step 1: send the login code to `phone`."""
        self._sweep_expired()
        self.cancel(pending_id)  # a fresh phone submission replaces any prior attempt

        client = TelegramClient(StringSession(), settings.api_id, settings.api_hash)
        await client.connect()
        try:
            sent = await client.send_code_request(phone)
        except (PhoneNumberInvalidError, PhoneNumberBannedError) as exc:
            client.disconnect()
            raise LinkError("Invalid or banned phone number.") from exc
        except FloodWaitError as exc:
            client.disconnect()
            raise LinkError(f"Too many attempts. Try again in {exc.seconds}s.") from exc

        self._attempts[pending_id] = _LinkAttempt(
            client=client,
            phone=phone,
            phone_code_hash=sent.phone_code_hash,
            needs_password=False,
            expires_at=time.time() + LINK_ATTEMPT_TTL,
        )
        logger.info("telegram_login: code sent pending=%s... phone=%s", pending_id[:8], phone)

    async def submit_code(self, pending_id: str, code: str) -> LinkedAccount | None:
        """Step 2: submit the received code. Returns None if a 2FA password is
        also required (call submit_password next); returns the linked account
        on success."""
        attempt = self._require_attempt(pending_id)
        try:
            await attempt.client.sign_in(
                phone=attempt.phone, code=code, phone_code_hash=attempt.phone_code_hash
            )
        except SessionPasswordNeededError:
            attempt.needs_password = True
            attempt.expires_at = time.time() + LINK_ATTEMPT_TTL
            return None
        except (PhoneCodeInvalidError, PhoneCodeExpiredError) as exc:
            raise LinkError("Incorrect or expired code.") from exc

        return await self._finish(pending_id, attempt)

    async def submit_password(self, pending_id: str, password: str) -> LinkedAccount:
        """Step 3 (only if 2FA is enabled on the account)."""
        attempt = self._require_attempt(pending_id)
        if not attempt.needs_password:
            raise LinkError("No password step pending for this login attempt.")
        try:
            await attempt.client.sign_in(password=password)
        except PasswordHashInvalidError as exc:
            raise LinkError("Incorrect password.") from exc

        return await self._finish(pending_id, attempt)

    def cancel(self, pending_id: str) -> None:
        attempt = self._attempts.pop(pending_id, None)
        if attempt is not None:
            try:
                attempt.client.disconnect()
            except Exception:
                logger.exception("telegram_login: error disconnecting cancelled client")

    def needs_password(self, pending_id: str) -> bool:
        attempt = self._attempts.get(pending_id)
        return attempt is not None and attempt.needs_password

    def _require_attempt(self, pending_id: str) -> _LinkAttempt:
        self._sweep_expired()
        attempt = self._attempts.get(pending_id)
        if attempt is None:
            raise LinkError(
                "Login attempt expired or not found. Start over with your phone number."
            )
        return attempt

    async def _finish(self, pending_id: str, attempt: _LinkAttempt) -> LinkedAccount:
        me = await attempt.client.get_me()
        session_string = attempt.client.session.save()
        self._attempts.pop(pending_id, None)
        attempt.client.disconnect()
        logger.info(
            "telegram_login: linked pending=%s... telegram_user_id=%s", pending_id[:8], me.id
        )
        return LinkedAccount(
            session_string=session_string,
            telegram_user_id=me.id,
            phone=me.phone,
            display_name=" ".join(filter(None, [me.first_name, me.last_name])) or None,
        )


linker = TelegramLinker()
