from fastapi import Request

from app.services.github import GitHubClient


def get_github_client(request: Request) -> GitHubClient:
    return GitHubClient(request.app.state.github_http)
