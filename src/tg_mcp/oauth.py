import logging
import secrets
import time
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timezone
from urllib.parse import urlencode

import sqlalchemy as sa
from fastmcp.server.auth import OAuthProvider
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.auth.jwt_issuer import JWTIssuer, derive_jwt_key
from fastmcp.server.auth.redirect_validation import matches_allowed_pattern
from joserfc.errors import JoseError
from mcp.server.auth.provider import (
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    RefreshToken,
    TokenError,
    construct_redirect_uri,
)
from mcp.server.auth.settings import ClientRegistrationOptions, RevocationOptions
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyUrl, BaseModel
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response
from starlette.routing import Route

from tg_mcp.auth import encrypt_session, hash_password
from tg_mcp.dao.user import UserDao
from tg_mcp.orm.oauth_client import OAuthClient
from tg_mcp.orm.revoked_token import RevokedToken
from tg_mcp.telegram_login import LinkedAccount, LinkError, linker
from tg_mcp.utils.inject_client_id import InjectClientIdMiddleware

logger = logging.getLogger(__name__)


class _PatternMatchingClient(OAuthClientInformationFull):
    """OAuthClientInformationFull that matches redirect_uris by path, ignoring query string."""

    def validate_redirect_uri(self, redirect_uri: AnyUrl | None) -> AnyUrl:
        if redirect_uri is not None:
            uri_str = str(redirect_uri)
            for pattern in self.redirect_uris or []:
                if matches_allowed_pattern(uri_str, str(pattern)):
                    return redirect_uri
        return super().validate_redirect_uri(redirect_uri)


ACCESS_TOKEN_TTL = 3600  # 1 hour
REFRESH_TOKEN_TTL = 30 * 24 * 3600  # 30 days
AUTH_CODE_TTL = 300  # 5 minutes
PENDING_TTL = 900  # 15 minutes to complete login + Telegram linking

_CARD_STYLE = """\
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; background: #f5f5f5; color: #111;
       display: flex; align-items: center; justify-content: center; min-height: 100vh; }
.card { background: #fff; border: 1px solid #e5e7eb; border-radius: 12px;
        padding: 2rem; width: 100%; max-width: 380px;
        box-shadow: 0 2px 8px rgba(0,0,0,.08); }
h1 { font-size: 1.25rem; font-weight: 600; margin-bottom: 1.5rem; color: #111; }
label { display: block; font-size: 0.875rem; color: #555; margin-bottom: 0.375rem; }
input[type=text], input[type=password], input[type=tel] {
    width: 100%; padding: 0.625rem 0.75rem;
    border: 1px solid #d1d5db; border-radius: 6px; color: #111;
    font-size: 0.875rem; outline: none; margin-bottom: 1rem; }
input:focus { border-color: #6366f1; }
button { width: 100%; margin-top: 0.25rem; padding: 0.625rem;
         background: #6366f1; border: none; border-radius: 6px;
         color: #fff; font-size: 0.875rem; font-weight: 500; cursor: pointer; }
button:hover { background: #4f46e5; }
.error { margin-top: 1rem; padding: 0.5rem 0.75rem; background: #fef2f2;
         border: 1px solid #f87171; border-radius: 6px;
         color: #dc2626; font-size: 0.8125rem; }
.meta { margin-top: 1rem; font-size: 0.75rem; color: #9ca3af; }
.hint { margin-bottom: 1rem; font-size: 0.8125rem; color: #6b7280; }
"""

_LOGIN_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>tg-mcp — Sign in</title>
  <style>{style}</style>
</head>
<body>
  <div class="card">
    <h1>tg-mcp</h1>
    <form method="post">
      <input type="hidden" name="id" value="{pending_id}">
      <input type="hidden" name="action" value="login">
      <label for="username">Username</label>
      <input type="text" id="username" name="username" autofocus required
             autocomplete="username" value="{username}">
      <label for="pw">Password</label>
      <input type="password" id="pw" name="password" required
             autocomplete="current-password">
      <button type="submit">Sign in</button>
      {error_block}
    </form>
    <p class="meta">Client: {client_id}</p>
  </div>
</body>
</html>
"""

_REGISTER_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>tg-mcp — Create account</title>
  <style>{style}</style>
</head>
<body>
  <div class="card">
    <h1>Create account</h1>
    <p class="hint">No account found for <strong>{username}</strong>. Create one to continue.</p>
    <form method="post">
      <input type="hidden" name="id" value="{pending_id}">
      <input type="hidden" name="action" value="register">
      <input type="hidden" name="username" value="{username}">
      <label for="pw">Password</label>
      <input type="password" id="pw" name="password" autofocus required
             autocomplete="new-password">
      <label for="pw2">Confirm password</label>
      <input type="password" id="pw2" name="password2" required
             autocomplete="new-password">
      <button type="submit">Create account</button>
      {error_block}
    </form>
    <p class="meta">Client: {client_id}</p>
  </div>
</body>
</html>
"""

_PHONE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>tg-mcp — Link Telegram</title>
  <style>{style}</style>
</head>
<body>
  <div class="card">
    <h1>Link your Telegram account</h1>
    <p class="hint">Signed in as <strong>{username}</strong>. Enter your phone number in
       international format (e.g. +48123456789) to link the Telegram account these tools
       will act on.</p>
    <form method="post">
      <input type="hidden" name="id" value="{pending_id}">
      <input type="hidden" name="action" value="telegram_phone">
      <label for="phone">Phone number</label>
      <input type="tel" id="phone" name="phone" autofocus required
             autocomplete="tel" placeholder="+48123456789" value="{phone}">
      <button type="submit">Send code</button>
      {error_block}
    </form>
  </div>
</body>
</html>
"""

_CODE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>tg-mcp — Link Telegram</title>
  <style>{style}</style>
</head>
<body>
  <div class="card">
    <h1>Enter the code</h1>
    <p class="hint">A login code was sent to <strong>{phone}</strong> via Telegram (or SMS).</p>
    <form method="post">
      <input type="hidden" name="id" value="{pending_id}">
      <input type="hidden" name="action" value="telegram_code">
      <label for="code">Code</label>
      <input type="text" id="code" name="code" autofocus required
             autocomplete="one-time-code" inputmode="numeric">
      <button type="submit">Continue</button>
      {error_block}
    </form>
  </div>
</body>
</html>
"""

_PASSWORD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>tg-mcp — Link Telegram</title>
  <style>{style}</style>
</head>
<body>
  <div class="card">
    <h1>Two-factor password</h1>
    <p class="hint">This Telegram account has cloud password (2FA) enabled.</p>
    <form method="post">
      <input type="hidden" name="id" value="{pending_id}">
      <input type="hidden" name="action" value="telegram_password">
      <label for="password">Password</label>
      <input type="password" id="password" name="password" autofocus required
             autocomplete="current-password">
      <button type="submit">Continue</button>
      {error_block}
    </form>
  </div>
</body>
</html>
"""


class _PendingAuth(BaseModel):
    client_id: str
    params: AuthorizationParams
    scopes: list[str]
    expires_at: float
    # Set once the account (login or register) is resolved; from that point
    # on we're walking the Telegram phone/code/(password) linking steps.
    user_id: int | None = None
    username: str | None = None


class TgMcpOAuthProvider(OAuthProvider):
    """Full in-process OAuth 2.1 authorization server.

    Login is username+password, self-service registration. Accounts with no
    Telegram account linked yet are walked through a phone -> code -> (2FA
    password) flow, reusing Telethon's login handshake, before an
    authorization code is ever issued back to the MCP client.
    """

    def __init__(
        self,
        base_url: str,
        jwt_secret: str,
        session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    ) -> None:
        super().__init__(
            base_url=base_url,
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                valid_scopes=["mcp"],
                default_scopes=["mcp"],
            ),
            revocation_options=RevocationOptions(enabled=True),
            required_scopes=["mcp"],
        )
        self._base_url = base_url.rstrip("/")

        self._signing_key = derive_jwt_key(
            high_entropy_material=jwt_secret, salt="tg-mcp-oauth-jwt"
        )
        self._jwt = JWTIssuer(
            issuer=self._base_url,
            audience=self._base_url,
            signing_key=self._signing_key,
        )

        self._auth_codes: dict[str, AuthorizationCode] = {}
        self._pending: dict[str, _PendingAuth] = {}

        self.session = session_factory

    # ------------------------------------------------------------------
    # Login / registration / Telegram linking pages
    # ------------------------------------------------------------------

    def set_mcp_path(self, mcp_path: str | None) -> None:
        super().set_mcp_path(mcp_path)
        # Per RFC 8707, tokens must be bound to the resource they are issued for.
        audience = (
            str(self._resource_url).rstrip("/")
            if self._resource_url is not None
            else self._base_url
        )
        self._jwt = JWTIssuer(
            issuer=self._base_url,
            audience=audience,
            signing_key=self._signing_key,
        )
        logger.debug("set_mcp_path: JWT audience updated to %s", audience)

    def get_middleware(self) -> list:
        middlewares = super().get_middleware()
        middlewares.append(
            Middleware(InjectClientIdMiddleware, auth_codes=self._auth_codes)  # type: ignore[arg-type]
        )
        return middlewares

    def get_routes(self, mcp_path: str | None = None) -> list[Route]:
        routes = super().get_routes(mcp_path)
        routes += [Route("/login", endpoint=self._login, methods=["GET", "POST"])]

        # RFC 9728: alias path-specific well-known at root so both work.
        for route in list(routes):
            if isinstance(route, Route) and route.path.startswith(
                "/.well-known/oauth-protected-resource/"
            ):
                routes.append(
                    Route(
                        "/.well-known/oauth-protected-resource",
                        endpoint=route.endpoint,
                        methods=["GET", "OPTIONS"],
                    )
                )
                break

        return routes

    async def _login(self, request: Request) -> Response:
        if request.method == "GET":
            return self._login_get(request)
        return await self._login_post(request)

    def _get_pending(self, pending_id: str) -> _PendingAuth | None:
        pending = self._pending.get(pending_id)
        if not pending or pending.expires_at < time.time():
            self._pending.pop(pending_id, None)
            linker.cancel(pending_id)
            return None
        return pending

    def _login_get(self, request: Request) -> Response:
        pending_id = request.query_params.get("id", "")
        pending = self._get_pending(pending_id)
        if not pending:
            logger.warning("login GET: invalid/expired pending_id=%s...", pending_id[:8])
            return HTMLResponse(
                "<h3>Authorization request expired. Please try again.</h3>",
                status_code=400,
            )

        if pending.user_id is None:
            return HTMLResponse(
                _LOGIN_HTML.format(
                    style=_CARD_STYLE,
                    pending_id=pending_id,
                    client_id=pending.client_id,
                    username="",
                    error_block="",
                )
            )

        # Account resolved, walk (or resume) the Telegram linking steps.
        if linker.needs_password(pending_id):
            return HTMLResponse(
                _PASSWORD_HTML.format(style=_CARD_STYLE, pending_id=pending_id, error_block="")
            )
        return HTMLResponse(
            _PHONE_HTML.format(
                style=_CARD_STYLE,
                pending_id=pending_id,
                username=pending.username or "",
                phone="",
                error_block="",
            )
        )

    async def _login_post(self, request: Request) -> Response:
        form = await request.form()
        pending_id = str(form.get("id", ""))
        action = str(form.get("action", "login"))

        pending = self._get_pending(pending_id)
        if not pending:
            logger.warning("login POST: invalid/expired pending_id=%s...", pending_id[:8])
            return HTMLResponse(
                "<h3>Authorization request expired. Please try again.</h3>",
                status_code=400,
            )

        handlers = {
            "login": self._handle_login,
            "register": self._handle_register,
            "telegram_phone": self._handle_phone,
            "telegram_code": self._handle_code,
            "telegram_password": self._handle_password,
        }
        handler = handlers.get(action)
        if handler is None:
            return HTMLResponse("<h3>Unknown action.</h3>", status_code=400)
        return await handler(form, pending_id, pending)

    async def _handle_login(self, form, pending_id: str, pending: "_PendingAuth") -> Response:
        username = str(form.get("username", "")).strip().lower()
        password = str(form.get("password", ""))

        async with self.session() as s:
            exists = await UserDao(s).exists_by_username(username)
            if not exists:
                logger.info("login: unknown username, showing register form username=%s", username)
                return HTMLResponse(
                    _REGISTER_HTML.format(
                        style=_CARD_STYLE,
                        pending_id=pending_id,
                        client_id=pending.client_id,
                        username=username,
                        error_block="",
                    )
                )
            user = await UserDao(s).authenticate(username, password)

        if user is None:
            logger.warning(
                "login: wrong password username=%s client_id=%s", username, pending.client_id
            )
            return HTMLResponse(
                _LOGIN_HTML.format(
                    style=_CARD_STYLE,
                    pending_id=pending_id,
                    client_id=pending.client_id,
                    username=username,
                    error_block='<p class="error">Incorrect password.</p>',
                ),
                status_code=401,
            )

        return await self._after_auth(pending_id, pending, user.id, username, user.telegram_linked)

    async def _handle_register(self, form, pending_id: str, pending: "_PendingAuth") -> Response:
        username = str(form.get("username", "")).strip().lower()
        password = str(form.get("password", ""))
        password2 = str(form.get("password2", ""))

        def _reg_error(msg: str) -> Response:
            return HTMLResponse(
                _REGISTER_HTML.format(
                    style=_CARD_STYLE,
                    pending_id=pending_id,
                    client_id=pending.client_id,
                    username=username,
                    error_block=f'<p class="error">{msg}</p>',
                ),
                status_code=400,
            )

        if not username:
            return _reg_error("Username is required.")
        if not password:
            return _reg_error("Password is required.")
        if password != password2:
            return _reg_error("Passwords do not match.")

        async with self.session() as s:
            if await UserDao(s).exists_by_username(username):
                return _reg_error("An account with this username already exists.")
            user = await UserDao(s).create(
                username=username, hashed_password=hash_password(password)
            )

        logger.info("register: created user id=%d username=%s", user.id, username)
        return await self._after_auth(pending_id, pending, user.id, username, telegram_linked=False)

    async def _after_auth(
        self,
        pending_id: str,
        pending: "_PendingAuth",
        user_id: int,
        username: str,
        telegram_linked: bool,
    ) -> Response:
        if telegram_linked:
            return await self._issue_code(pending_id, pending, user_id)

        pending.user_id = user_id
        pending.username = username
        self._pending[pending_id] = pending
        return HTMLResponse(
            _PHONE_HTML.format(
                style=_CARD_STYLE,
                pending_id=pending_id,
                username=username,
                phone="",
                error_block="",
            )
        )

    async def _handle_phone(self, form, pending_id: str, pending: "_PendingAuth") -> Response:
        if pending.user_id is None:
            return HTMLResponse("<h3>Sign in first.</h3>", status_code=400)
        phone = str(form.get("phone", "")).strip()

        try:
            await linker.start(pending_id, phone)
        except LinkError as exc:
            return HTMLResponse(
                _PHONE_HTML.format(
                    style=_CARD_STYLE,
                    pending_id=pending_id,
                    username=pending.username or "",
                    phone=phone,
                    error_block=f'<p class="error">{exc}</p>',
                ),
                status_code=400,
            )

        return HTMLResponse(
            _CODE_HTML.format(style=_CARD_STYLE, pending_id=pending_id, phone=phone, error_block="")
        )

    async def _handle_code(self, form, pending_id: str, pending: "_PendingAuth") -> Response:
        if pending.user_id is None:
            return HTMLResponse("<h3>Sign in first.</h3>", status_code=400)
        code = str(form.get("code", "")).strip()

        try:
            linked = await linker.submit_code(pending_id, code)
        except LinkError as exc:
            return HTMLResponse(
                _CODE_HTML.format(
                    style=_CARD_STYLE,
                    pending_id=pending_id,
                    phone="",
                    error_block=f'<p class="error">{exc}</p>',
                ),
                status_code=400,
            )

        if linked is None:
            # 2FA cloud password required.
            return HTMLResponse(
                _PASSWORD_HTML.format(style=_CARD_STYLE, pending_id=pending_id, error_block="")
            )

        return await self._complete_link(pending_id, pending, linked)

    async def _handle_password(self, form, pending_id: str, pending: "_PendingAuth") -> Response:
        if pending.user_id is None:
            return HTMLResponse("<h3>Sign in first.</h3>", status_code=400)
        password = str(form.get("password", ""))

        try:
            linked = await linker.submit_password(pending_id, password)
        except LinkError as exc:
            return HTMLResponse(
                _PASSWORD_HTML.format(
                    style=_CARD_STYLE,
                    pending_id=pending_id,
                    error_block=f'<p class="error">{exc}</p>',
                ),
                status_code=400,
            )

        return await self._complete_link(pending_id, pending, linked)

    async def _complete_link(
        self, pending_id: str, pending: "_PendingAuth", linked: LinkedAccount
    ) -> Response:
        assert pending.user_id is not None
        async with self.session() as s:
            await UserDao(s).set_telegram_session(
                pending.user_id,
                encrypt_session(linked.session_string),
                telegram_user_id=linked.telegram_user_id,
                phone=linked.phone,
                display_name=linked.display_name,
            )
        return await self._issue_code(pending_id, pending, pending.user_id)

    async def _issue_code(self, pending_id: str, pending: "_PendingAuth", user_id: int) -> Response:
        self._pending.pop(pending_id, None)
        linker.cancel(pending_id)

        # Link this OAuth client to the authenticated user.
        async with self.session() as s:
            await s.execute(
                sa.update(OAuthClient)
                .where(OAuthClient.client_id == pending.client_id)
                .values(user_id=user_id)
            )

        code = secrets.token_urlsafe(32)
        self._auth_codes[code] = AuthorizationCode(
            code=code,
            client_id=pending.client_id,
            redirect_uri=pending.params.redirect_uri,
            redirect_uri_provided_explicitly=pending.params.redirect_uri_provided_explicitly,
            scopes=pending.scopes,
            expires_at=time.time() + AUTH_CODE_TTL,
            code_challenge=pending.params.code_challenge,
            resource=pending.params.resource,
        )
        redirect = construct_redirect_uri(
            str(pending.params.redirect_uri), code=code, state=pending.params.state
        )
        logger.info(
            "issue_code: success client_id=%s user_id=%d code=%s...",
            pending.client_id,
            user_id,
            code[:8],
        )
        return RedirectResponse(redirect, status_code=302)

    # ------------------------------------------------------------------
    # OAuthAuthorizationServerProvider
    # ------------------------------------------------------------------

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        async with self.session() as s:
            data = await s.scalar(
                sa.select(OAuthClient.data).where(OAuthClient.client_id == client_id)
            )

        if data is None:
            logger.warning("get_client: client_id=%s not found in DB", client_id)
            return None

        return _PatternMatchingClient.model_validate(data)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        if client_info.client_id is None:
            raise ValueError("client_id required")
        logger.info(
            "register_client client_id=%s redirect_uris=%s scope=%s",
            client_info.client_id,
            client_info.redirect_uris,
            client_info.scope,
        )
        data = client_info.model_dump(mode="json")
        async with self.session() as s:
            existing_data = await s.scalar(
                sa.select(OAuthClient.data).where(OAuthClient.client_id == client_info.client_id)
            )
            if existing_data:
                existing_uris: list[str] = existing_data.get("redirect_uris") or []
                new_uris: list[str] = data.get("redirect_uris") or []
                merged = list(dict.fromkeys(existing_uris + new_uris))
                data["redirect_uris"] = merged
            await s.execute(
                pg_insert(OAuthClient)
                .values(client_id=client_info.client_id, data=data)
                .on_conflict_do_update(
                    index_elements=[OAuthClient.client_id],
                    set_={"data": data},
                )
            )

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        if client.client_id is None:
            raise AuthorizeError(
                error="unauthorized_client",
                error_description="Missing client_id",
            )

        scopes = list(params.scopes or [])
        if client.scope:
            allowed = set(client.scope.split())
            scopes = [s for s in scopes if s in allowed] or list(allowed)

        pending_id = secrets.token_urlsafe(32)
        self._pending[pending_id] = _PendingAuth(
            client_id=client.client_id,
            params=params,
            scopes=scopes,
            expires_at=time.time() + PENDING_TTL,
        )
        login_url = f"{self._base_url}/login?{urlencode({'id': pending_id})}"
        logger.info(
            "authorize → login client_id=%s pending=%s...",
            client.client_id,
            pending_id[:8],
        )
        return login_url

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        entry = self._auth_codes.get(authorization_code)
        if not entry or entry.client_id != client.client_id:
            return None
        if entry.expires_at < time.time():
            del self._auth_codes[authorization_code]
            return None
        return entry

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        if authorization_code.code not in self._auth_codes:
            raise TokenError("invalid_grant", "Code already used or expired")
        del self._auth_codes[authorization_code.code]
        if client.client_id is None:
            raise TokenError("invalid_client", "Missing client_id")
        token = self._issue_token_pair(client.client_id, authorization_code.scopes)
        logger.info(
            "exchange_authorization_code issued access=%s... scopes=%s",
            token.access_token[:16],
            token.scope,
        )
        return token

    async def load_access_token(self, token: str) -> AccessToken | None:  # type: ignore[override]
        try:
            claims = self._jwt.verify_token(token)
        except JoseError as exc:
            logger.debug("load_access_token JWT invalid: %s", exc)
            return None
        jti = claims.get("jti")
        if not jti:
            return None

        # Check revocation in DB (survives restarts, works cross-instance).
        async with self.session() as s:
            revoked = await s.scalar(sa.select(RevokedToken.jti).where(RevokedToken.jti == jti))
        if revoked is not None:
            logger.debug("load_access_token: jti revoked jti=%s...", jti[:8])
            return None

        client_id = claims.get("client_id", "")
        scopes = claims.get("scope", "").split() if claims.get("scope") else []
        exp = claims.get("exp")
        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=scopes,
            expires_at=int(exp) if exp else None,
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        try:
            claims = self._jwt.verify_token(refresh_token, expected_token_use="refresh")
        except JoseError as exc:
            logger.debug("load_refresh_token JWT invalid: %s", exc)
            return None
        token_client_id = claims.get("client_id", "")
        if token_client_id != client.client_id:
            return None
        scopes = claims.get("scope", "").split() if claims.get("scope") else []
        exp = claims.get("exp")
        return RefreshToken(
            token=refresh_token,
            client_id=token_client_id,
            scopes=scopes,
            expires_at=int(exp) if exp else None,
        )

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        if scopes and not set(scopes).issubset(set(refresh_token.scopes)):
            raise TokenError("invalid_scope", "Requested scopes exceed original grant")
        effective_scopes = scopes or refresh_token.scopes
        await self._revoke_pair(refresh_token_str=refresh_token.token)
        if client.client_id is None:
            raise TokenError("invalid_client", "Missing client_id")
        token = self._issue_token_pair(client.client_id, effective_scopes)
        logger.info(
            "exchange_refresh_token issued access=%s... scopes=%s",
            token.access_token[:16],
            token.scope,
        )
        return token

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:  # type: ignore[override]
        logger.info("revoke_token type=%s", type(token).__name__)
        if isinstance(token, AccessToken):
            await self._revoke_pair(access_token_str=token.token)
        else:
            await self._revoke_pair(refresh_token_str=token.token)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _issue_token_pair(self, client_id: str, scopes: list[str]) -> OAuthToken:
        jti = secrets.token_urlsafe(32)
        access_str = self._jwt.issue_access_token(
            client_id=client_id, scopes=scopes, jti=jti, expires_in=ACCESS_TOKEN_TTL
        )

        refresh_jti = secrets.token_urlsafe(32)
        refresh_str = self._jwt.issue_refresh_token(
            client_id=client_id,
            scopes=scopes,
            jti=refresh_jti,
            expires_in=REFRESH_TOKEN_TTL,
        )

        return OAuthToken(
            access_token=access_str,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_TTL,
            refresh_token=refresh_str,
            scope=" ".join(scopes),
        )

    async def _revoke_pair(
        self,
        access_token_str: str | None = None,
        refresh_token_str: str | None = None,
    ) -> None:
        to_revoke: list[tuple[str, datetime]] = []
        for token_str, token_use in [
            (access_token_str, "access"),
            (refresh_token_str, "refresh"),
        ]:
            if token_str is None:
                continue
            try:
                claims = self._jwt.verify_token(token_str, expected_token_use=token_use)
                jti = claims.get("jti")
                exp = claims.get("exp")
                if jti:
                    expires_at = datetime.fromtimestamp(
                        exp if exp else time.time() + REFRESH_TOKEN_TTL,
                        tz=timezone.utc,
                    ).replace(tzinfo=None)
                    to_revoke.append((jti, expires_at))
            except JoseError:
                pass

        if to_revoke:
            async with self.session() as s:
                for jti, expires_at in to_revoke:
                    await s.execute(
                        pg_insert(RevokedToken)
                        .values(jti=jti, expires_at=expires_at)
                        .on_conflict_do_nothing()
                    )
