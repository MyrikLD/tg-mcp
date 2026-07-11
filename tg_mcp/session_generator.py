"""Interactive generator for the Telethon user session string.

Run it once to log in as your Telegram user and obtain a portable session
string that the MCP server uses to act on your behalf:

    python -m tg_mcp.session_generator

Requires TELEGRAM_API_ID and TELEGRAM_API_HASH (from https://my.telegram.org/apps)
to be available in the environment or in a local .env file.
"""

import asyncio
from getpass import getpass

from telethon import TelegramClient, errors
from telethon.sessions import StringSession

from tg_mcp.config import get_settings


async def _generate() -> str:
    settings = get_settings()
    client = TelegramClient(StringSession(), settings.api_id, settings.api_hash)
    await client.connect()
    try:
        phone = input("Phone number (international format, e.g. +12345678901): ").strip()
        await client.send_code_request(phone)
        code = input("Login code you received in Telegram: ").strip()
        try:
            await client.sign_in(phone, code)
        except errors.SessionPasswordNeededError:
            password = getpass("Two-factor authentication password: ")
            await client.sign_in(password=password)

        me = await client.get_me()
        session_string = StringSession.save(client.session)
    finally:
        await client.disconnect()

    print(f"\nLogged in as {me.first_name or ''} (@{me.username or 'no username'}, id={me.id})")
    print("\nAdd this line to your .env file (keep it secret!):\n")
    print(f"TELEGRAM_SESSION_STRING={session_string}")
    return session_string


def main() -> None:
    try:
        asyncio.run(_generate())
    except (errors.PhoneNumberInvalidError, errors.PhoneCodeInvalidError) as exc:
        raise SystemExit(f"Login failed: {exc}") from exc
    except KeyboardInterrupt:
        raise SystemExit("\nAborted.") from None


if __name__ == "__main__":
    main()
