from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.services.ai.base import (
    AIConfigurationError,
    AIProviderError,
    AIRateLimitError,
    AITimeoutError,
)
from app.services.github import (
    GitHubAuthError,
    GitHubError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)

_GITHUB_ERROR_STATUS: dict[type[GitHubError], int] = {
    GitHubNotFoundError: status.HTTP_404_NOT_FOUND,
    GitHubRateLimitError: status.HTTP_429_TOO_MANY_REQUESTS,
    # RepoPilot's own GitHub credentials failed, so this is an upstream problem, not the caller's.
    GitHubAuthError: status.HTTP_502_BAD_GATEWAY,
}

# AI provider limits and credentials belong to the server, not the caller, so they surface
# as 503 (temporarily unable to serve) rather than 429 or 401.
_AI_ERROR_STATUS: dict[type[AIProviderError], int] = {
    AIConfigurationError: status.HTTP_503_SERVICE_UNAVAILABLE,
    AIRateLimitError: status.HTTP_503_SERVICE_UNAVAILABLE,
    AITimeoutError: status.HTTP_504_GATEWAY_TIMEOUT,
}


def _error_response(message: str, status_code: int, retry_after: int | None = None) -> JSONResponse:
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
    return JSONResponse({"detail": message}, status_code=status_code, headers=headers)


async def handle_github_error(_: Request, exc: GitHubError) -> JSONResponse:
    status_code = _GITHUB_ERROR_STATUS.get(type(exc), status.HTTP_502_BAD_GATEWAY)
    retry_after = exc.retry_after if isinstance(exc, GitHubRateLimitError) else None
    return _error_response(exc.message, status_code, retry_after)


async def handle_ai_error(_: Request, exc: AIProviderError) -> JSONResponse:
    status_code = _AI_ERROR_STATUS.get(type(exc), status.HTTP_502_BAD_GATEWAY)
    retry_after = exc.retry_after if isinstance(exc, AIRateLimitError) else None
    return _error_response(exc.message, status_code, retry_after)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(GitHubError, handle_github_error)
    app.add_exception_handler(AIProviderError, handle_ai_error)
