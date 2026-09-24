"""Sign in with GitHub: OAuth web flow with state and PKCE (S256).

The OAuth access token is used once to read the user's public profile and then discarded; it is
never stored or logged. It is unrelated to GITHUB_TOKEN, which only reads pull requests.
"""

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx2 as httpx
from pydantic import BaseModel

from app.core.config import Settings

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
USER_URL = "https://api.github.com/user"
CALLBACK_PATH = "/api/auth/callback"
PENDING_LOGIN_TTL_SECONDS = 600
REQUEST_TIMEOUT_SECONDS = 10.0
SESSION_USER_KEY = "user"
SESSION_PENDING_KEY = "oauth"


class SessionUser(BaseModel):
    login: str
    name: str | None = None
    avatar_url: str | None = None


class GitHubOAuthError(Exception):
    """The OAuth exchange or profile lookup failed. Carries no tokens or response bodies."""


@dataclass(frozen=True)
class PendingLogin:
    """What the callback needs to verify; stored in the (signed) session cookie."""

    state: str
    verifier: str
    next_path: str
    created_at: float

    def to_session(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "verifier": self.verifier,
            "next": self.next_path,
            "created_at": self.created_at,
        }

    @classmethod
    def from_session(cls, data: object) -> "PendingLogin | None":
        if not isinstance(data, dict):
            return None
        try:
            return cls(
                state=str(data["state"]),
                verifier=str(data["verifier"]),
                next_path=safe_next_path(str(data["next"])),
                created_at=float(data["created_at"]),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def expired(self, now: float | None = None) -> bool:
        return (now or time.time()) - self.created_at > PENDING_LOGIN_TTL_SECONDS


def new_pending_login(next_path: str | None) -> PendingLogin:
    return PendingLogin(
        state=secrets.token_urlsafe(32),
        verifier=secrets.token_urlsafe(64),
        next_path=safe_next_path(next_path),
        created_at=time.time(),
    )


def safe_next_path(value: str | None) -> str:
    """Only same-origin absolute paths; anything else (URLs, `//host`, `/\\host`) becomes `/`."""
    if not value or not value.startswith("/") or value.startswith(("//", "/\\")):
        return "/"
    if any(ch in value for ch in "\r\n\t") or ":" in value.split("?", 1)[0]:
        return "/"
    return value


def code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def callback_url(settings: Settings) -> str:
    return f"{settings.public_app_url}{CALLBACK_PATH}"


def authorize_url(settings: Settings, pending: PendingLogin) -> str:
    params = {
        "client_id": settings.github_oauth_client_id or "",
        "redirect_uri": callback_url(settings),
        "state": pending.state,
        "code_challenge": code_challenge(pending.verifier),
        "code_challenge_method": "S256",
        "allow_signup": "false",
        # No scope: the token can only read public profile information.
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def is_allowed(settings: Settings, login: str) -> bool:
    return login.lower() in settings.auth_allowed_github_users


def create_oauth_http_client(
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={"User-Agent": "RepoPilot"},
        transport=transport,
    )


class GitHubOAuthClient:
    def __init__(self, http: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http
        self._settings = settings

    async def identify(self, code: str, verifier: str) -> SessionUser:
        """Exchange the code for a token, read the profile, and drop the token."""
        token = await self._exchange_code(code, verifier)
        return await self._fetch_user(token)

    async def _exchange_code(self, code: str, verifier: str) -> str:
        secret = self._settings.github_oauth_client_secret
        try:
            response = await self._http.post(
                TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": self._settings.github_oauth_client_id or "",
                    "client_secret": secret.get_secret_value() if secret else "",
                    "code": code,
                    "redirect_uri": callback_url(self._settings),
                    "code_verifier": verifier,
                },
            )
            payload = response.json() if response.status_code == 200 else {}
        except (httpx.HTTPError, ValueError) as exc:
            raise GitHubOAuthError("token exchange failed") from exc
        # GitHub reports errors such as bad_verification_code with a 200 and an "error" field.
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            raise GitHubOAuthError("token exchange failed")
        return token

    async def _fetch_user(self, token: str) -> SessionUser:
        try:
            response = await self._http.get(
                USER_URL,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": self._settings.github_api_version,
                },
            )
            if response.status_code != 200:
                raise GitHubOAuthError("user lookup failed")
            data = response.json()
            return SessionUser(
                login=str(data["login"]),
                name=data.get("name"),
                avatar_url=data.get("avatar_url"),
            )
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise GitHubOAuthError("user lookup failed") from exc
