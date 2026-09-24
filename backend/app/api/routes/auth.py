import hmac
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel

from app.api.deps import get_current_user, get_oauth_client, get_settings_from_app
from app.core.config import Settings
from app.services.auth import (
    SESSION_PENDING_KEY,
    SESSION_USER_KEY,
    GitHubOAuthClient,
    GitHubOAuthError,
    PendingLogin,
    SessionUser,
    authorize_url,
    is_allowed,
    new_pending_login,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthStatus(BaseModel):
    auth_enabled: bool
    user: SessionUser | None


def _to_frontend(path: str = "/", error: str | None = None) -> RedirectResponse:
    # Relative redirects keep the user on the app's own origin.
    target = f"/?auth_error={error}" if error else path
    return RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/me", response_model=AuthStatus)
def me(
    settings: Annotated[Settings, Depends(get_settings_from_app)],
    user: Annotated[SessionUser | None, Depends(get_current_user)],
) -> AuthStatus:
    return AuthStatus(auth_enabled=settings.auth_enabled, user=user)


@router.get("/login")
def login(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings_from_app)],
    next_path: Annotated[str | None, Query(alias="next", max_length=2048)] = None,
) -> RedirectResponse:
    if not settings.auth_enabled:
        return _to_frontend()
    pending = new_pending_login(next_path)
    request.session[SESSION_PENDING_KEY] = pending.to_session()
    return RedirectResponse(authorize_url(settings, pending), status_code=status.HTTP_302_FOUND)


@router.get("/callback")
async def callback(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings_from_app)],
    oauth: Annotated[GitHubOAuthClient, Depends(get_oauth_client)],
    code: Annotated[str | None, Query(max_length=512)] = None,
    state: Annotated[str | None, Query(max_length=512)] = None,
    error: Annotated[str | None, Query(max_length=128)] = None,
) -> RedirectResponse:
    if not settings.auth_enabled:
        return _to_frontend()
    # Single use: whatever happens next, this pending login cannot be replayed.
    pending = PendingLogin.from_session(request.session.pop(SESSION_PENDING_KEY, None))

    if pending is None or pending.expired() or not state:
        logger.warning("auth.callback_rejected reason=missing_or_expired_state")
        return _to_frontend(error="invalid_state")
    if not hmac.compare_digest(pending.state, state):
        logger.warning("auth.callback_rejected reason=state_mismatch")
        return _to_frontend(error="invalid_state")
    if error or not code:
        logger.info("auth.callback_rejected reason=%s", "access_denied" if error else "no_code")
        return _to_frontend(error="access_denied")

    try:
        user = await oauth.identify(code, pending.verifier)
    except GitHubOAuthError as exc:
        logger.warning("auth.callback_failed reason=%s", exc)
        return _to_frontend(error="github_error")

    if not is_allowed(settings, user.login):
        logger.warning("auth.login_denied login=%s reason=not_allowlisted", user.login)
        return _to_frontend(error="not_allowed")

    request.session[SESSION_USER_KEY] = user.model_dump()
    logger.info("auth.login_succeeded login=%s", user.login)
    return _to_frontend(pending.next_path)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request, settings: Annotated[Settings, Depends(get_settings_from_app)]
) -> Response:
    if settings.auth_enabled:
        request.session.clear()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
