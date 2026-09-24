"""Sign in with GitHub: every GitHub OAuth request is mocked; nothing leaves the process."""

import base64
import json
import logging
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_oauth_client, get_review_repository
from app.core.config import Settings
from app.main import SESSION_COOKIE_NAME, create_app
from app.services import auth as auth_service
from app.services.auth import GitHubOAuthClient, code_challenge, create_oauth_http_client
from tests.review_helpers import InMemoryReviewStore

ORIGIN = "https://repopilot.test"
CLIENT_SECRET = "oauth-client-secret-sentinel"
SESSION_SECRET = "session-secret-sentinel-" + "z" * 32
ACCESS_TOKEN = "gho_access-token-sentinel"
CODE = "oauth-code-sentinel"

Handler = Callable[[httpx.Request], httpx.Response]


def github_ok(login: str = "GladwynL") -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login/oauth/access_token":
            return httpx.Response(200, json={"access_token": ACCESS_TOKEN, "token_type": "bearer"})
        if request.url.path == "/user":
            return httpx.Response(
                200,
                json={"login": login, "name": "Gladwyn", "avatar_url": "https://avatars.test/u/1"},
            )
        return httpx.Response(404)

    return handler


@dataclass
class AuthHarness:
    client: TestClient
    settings: Settings
    github_requests: list[httpx.Request] = field(default_factory=list)
    github: Handler = field(default_factory=github_ok)

    def __post_init__(self) -> None:
        def record(request: httpx.Request) -> httpx.Response:
            self.github_requests.append(request)
            return self.github(request)

        http = create_oauth_http_client(transport=httpx.MockTransport(record))
        overrides = self.client.app.dependency_overrides
        overrides[get_oauth_client] = lambda: GitHubOAuthClient(http, self.settings)
        overrides[get_review_repository] = lambda: InMemoryReviewStore()

    def start_login(self, next_path: str | None = "/reviews") -> httpx.Response:
        params = {"next": next_path} if next_path is not None else None
        return self.client.get("/api/auth/login", params=params, follow_redirects=False)

    def state_from(self, login_response: httpx.Response) -> str:
        return parse_qs(urlparse(login_response.headers["location"]).query)["state"][0]

    def callback(self, **params: str) -> httpx.Response:
        return self.client.get("/api/auth/callback", params=params, follow_redirects=False)

    def sign_in(self) -> httpx.Response:
        state = self.state_from(self.start_login())
        return self.callback(code=CODE, state=state)

    def me(self) -> dict[str, object]:
        return self.client.get("/api/auth/me").json()


def auth_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "auth_enabled": True,
        "github_oauth_client_id": "client-id-123",
        "github_oauth_client_secret": CLIENT_SECRET,
        "session_secret": SESSION_SECRET,
        "auth_allowed_github_users": "GladwynL, second-user",
        "public_app_url": ORIGIN,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


@pytest.fixture
def harness() -> Iterator[AuthHarness]:
    settings = auth_settings()
    with TestClient(create_app(settings), base_url=ORIGIN) as client:
        yield AuthHarness(client, settings)


def session_payload(response: httpx.Response) -> dict[str, object]:
    """Decode the signed (not encrypted) session cookie, as the browser could."""
    cookie = response.cookies[SESSION_COOKIE_NAME]
    encoded = cookie.split(".")[0]
    return json.loads(base64.b64decode(encoded + "=" * (-len(encoded) % 4)))


def auth_error(response: httpx.Response) -> str | None:
    values = parse_qs(urlparse(response.headers["location"]).query).get("auth_error")
    return values[0] if values else None


# --- login redirect ------------------------------------------------------------------------


def test_login_redirects_to_github_with_state_and_pkce(harness: AuthHarness) -> None:
    response = harness.start_login()

    assert response.status_code == 302
    url = urlparse(response.headers["location"])
    assert f"{url.scheme}://{url.netloc}{url.path}" == auth_service.AUTHORIZE_URL
    params = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert params["client_id"] == "client-id-123"
    assert params["redirect_uri"] == f"{ORIGIN}/api/auth/callback"
    assert params["code_challenge_method"] == "S256"
    assert len(params["state"]) >= 40
    assert "scope" not in params
    pending = session_payload(response)["oauth"]
    assert isinstance(pending, dict)
    assert pending["state"] == params["state"]
    assert params["code_challenge"] == code_challenge(str(pending["verifier"]))
    assert CLIENT_SECRET not in response.headers["location"]


def test_each_login_gets_a_fresh_state(harness: AuthHarness) -> None:
    first = harness.state_from(harness.start_login())
    second = harness.state_from(harness.start_login())

    assert first != second


def test_session_cookie_flags(harness: AuthHarness) -> None:
    cookie = harness.start_login().headers["set-cookie"].lower()

    for flag in ("httponly", "secure", "samesite=lax", "path=/", "max-age=28800"):
        assert flag in cookie


# --- callback --------------------------------------------------------------------------------


def test_callback_signs_in_allowlisted_user(harness: AuthHarness) -> None:
    response = harness.sign_in()

    assert response.status_code == 303
    assert response.headers["location"] == "/reviews"
    assert harness.me() == {
        "auth_enabled": True,
        "user": {"login": "GladwynL", "name": "Gladwyn", "avatar_url": "https://avatars.test/u/1"},
    }
    token_request, user_request = harness.github_requests
    form = parse_qs(token_request.content.decode())
    assert form["client_secret"] == [CLIENT_SECRET]
    assert form["code"] == [CODE]
    assert form["redirect_uri"] == [f"{ORIGIN}/api/auth/callback"]
    assert code_challenge(form["code_verifier"][0])  # PKCE verifier is sent
    assert user_request.headers["authorization"] == f"Bearer {ACCESS_TOKEN}"


def test_oauth_token_is_not_kept_in_the_session(harness: AuthHarness) -> None:
    response = harness.sign_in()

    payload = json.dumps(session_payload(response))
    assert ACCESS_TOKEN not in payload
    assert "oauth" not in session_payload(response)  # pending state consumed


def test_allowlist_is_case_insensitive() -> None:
    settings = auth_settings(auth_allowed_github_users="GLADWYNL")
    with TestClient(create_app(settings), base_url=ORIGIN) as client:
        harness = AuthHarness(client, settings, github=github_ok(login="gladwynl"))
        harness.sign_in()

        assert harness.me()["user"] is not None


def test_non_allowlisted_user_is_rejected(harness: AuthHarness) -> None:
    harness.github = github_ok(login="stranger")

    response = harness.sign_in()

    assert auth_error(response) == "not_allowed"
    assert harness.me()["user"] is None


def test_mismatched_state_is_rejected(harness: AuthHarness) -> None:
    harness.start_login()

    response = harness.callback(code=CODE, state="forged-state")

    assert auth_error(response) == "invalid_state"
    assert harness.github_requests == []


def test_callback_without_pending_login_is_rejected(harness: AuthHarness) -> None:
    response = harness.callback(code=CODE, state="anything")

    assert auth_error(response) == "invalid_state"


def test_state_cannot_be_replayed(harness: AuthHarness) -> None:
    state = harness.state_from(harness.start_login())
    harness.callback(code=CODE, state=state)
    harness.client.post("/api/auth/logout")

    replay = harness.callback(code=CODE, state=state)

    assert auth_error(replay) == "invalid_state"


def test_expired_pending_login_is_rejected(
    harness: AuthHarness, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = harness.state_from(harness.start_login())
    real_time = auth_service.time.time
    monkeypatch.setattr(auth_service.time, "time", lambda: real_time() + 11 * 60)

    response = harness.callback(code=CODE, state=state)

    assert auth_error(response) == "invalid_state"


def test_denied_authorization_is_reported(harness: AuthHarness) -> None:
    state = harness.state_from(harness.start_login())

    response = harness.callback(error="access_denied", state=state)

    assert auth_error(response) == "access_denied"
    assert harness.github_requests == []


@pytest.mark.parametrize(
    "token_response",
    [
        httpx.Response(200, json={"error": "bad_verification_code"}),
        httpx.Response(500),
        httpx.Response(200, text="not json"),
    ],
)
def test_token_exchange_failure(harness: AuthHarness, token_response: httpx.Response) -> None:
    harness.github = lambda request: token_response

    response = harness.sign_in()

    assert auth_error(response) == "github_error"
    assert harness.me()["user"] is None


def test_token_exchange_network_failure(harness: AuthHarness) -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    harness.github = fail

    assert auth_error(harness.sign_in()) == "github_error"


def test_user_lookup_failure(harness: AuthHarness) -> None:
    ok = github_ok()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401) if request.url.path == "/user" else ok(request)

    harness.github = handler

    assert auth_error(harness.sign_in()) == "github_error"


@pytest.mark.parametrize(
    "next_path", ["https://evil.test/", "//evil.test/x", "/\\evil.test", "javascript:alert(1)"]
)
def test_next_path_cannot_redirect_off_site(harness: AuthHarness, next_path: str) -> None:
    state = harness.state_from(harness.start_login(next_path))

    response = harness.callback(code=CODE, state=state)

    assert response.headers["location"] == "/"


# --- session lifecycle -------------------------------------------------------------------------


def test_logout_clears_the_session(harness: AuthHarness) -> None:
    harness.sign_in()

    response = harness.client.post("/api/auth/logout")

    assert response.status_code == 204
    assert harness.me()["user"] is None
    assert harness.client.get("/api/reviews").status_code == 401


def test_tampered_session_cookie_is_ignored(harness: AuthHarness) -> None:
    harness.sign_in()
    cookie = harness.client.cookies[SESSION_COOKIE_NAME]
    harness.client.cookies.set(SESSION_COOKIE_NAME, "x" + cookie[1:])

    assert harness.me()["user"] is None


def test_removing_a_login_from_the_allowlist_revokes_access(harness: AuthHarness) -> None:
    harness.sign_in()
    harness.settings.auth_allowed_github_users = ["second-user"]

    assert harness.client.get("/api/reviews").status_code == 401


# --- authorization boundary --------------------------------------------------------------------

PROTECTED = [
    ("GET", "/api/reviews"),
    ("GET", f"/api/reviews/{uuid.uuid4()}"),
    ("POST", "/api/reviews/github"),
    ("GET", "/api/github/repos/octo-org/widgets/pulls/42"),
]


@pytest.mark.parametrize(("method", "path"), PROTECTED)
def test_protected_endpoints_reject_anonymous_callers(
    harness: AuthHarness, method: str, path: str
) -> None:
    body = {"owner": "octo-org", "repo": "widgets", "pull_number": 42}
    response = harness.client.request(method, path, json=body if method == "POST" else None)

    assert response.status_code == 401
    assert response.json() == {"detail": "Sign in to use RepoPilot."}


def test_signed_in_user_can_use_the_app(harness: AuthHarness) -> None:
    harness.sign_in()

    assert harness.client.get("/api/reviews").status_code == 200
    assert harness.client.get(f"/api/reviews/{uuid.uuid4()}").status_code == 404


@pytest.mark.parametrize("path", ["/health", "/api/auth/me"])
def test_probes_and_auth_status_stay_public(harness: AuthHarness, path: str) -> None:
    assert harness.client.get(path).status_code == 200


def test_auth_disabled_keeps_local_development_open() -> None:
    with TestClient(create_app(Settings(auth_enabled=False))) as client:
        client.app.dependency_overrides[get_review_repository] = lambda: InMemoryReviewStore()

        assert client.get("/api/auth/me").json() == {"auth_enabled": False, "user": None}
        assert client.get("/api/reviews").status_code == 200
        login = client.get("/api/auth/login", follow_redirects=False)
        assert (login.status_code, login.headers["location"]) == (303, "/")
        assert "set-cookie" not in login.headers


# --- secrets hygiene -----------------------------------------------------------------------------


def test_secrets_never_appear_in_responses_or_logs(
    harness: AuthHarness, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger="app")
    responses = [harness.start_login(), harness.sign_in()]
    harness.github = lambda request: httpx.Response(200, json={"error": "bad_verification_code"})
    responses.append(harness.sign_in())
    harness.github = github_ok(login="stranger")
    responses.append(harness.sign_in())

    visible = "\n".join(
        [r.text + json.dumps(dict(r.headers)) for r in responses]
        + [record.getMessage() for record in caplog.records]
    )
    for secret in (CLIENT_SECRET, SESSION_SECRET, ACCESS_TOKEN, CODE):
        assert secret not in visible
