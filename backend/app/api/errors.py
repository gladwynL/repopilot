from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

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


async def handle_github_error(_: Request, exc: GitHubError) -> JSONResponse:
    status_code = _GITHUB_ERROR_STATUS.get(type(exc), status.HTTP_502_BAD_GATEWAY)
    headers = None
    if isinstance(exc, GitHubRateLimitError) and exc.retry_after is not None:
        headers = {"Retry-After": str(exc.retry_after)}
    return JSONResponse({"detail": exc.message}, status_code=status_code, headers=headers)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(GitHubError, handle_github_error)
