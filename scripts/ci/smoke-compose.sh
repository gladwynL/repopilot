#!/usr/bin/env bash
# Start the production Compose stack from prebuilt images in production mode, with placeholder
# credentials, and check that it migrates, becomes ready, gates the API, and serves the SPA.
# Usage: smoke-compose.sh <api-image> <web-image>
set -euo pipefail

export API_IMAGE="${1:?api image}"
export WEB_IMAGE="${2:?web image}"
export MSYS_NO_PATHCONV=1  # keep URL paths intact under Git Bash

cd "$(git rev-parse --show-toplevel)"
# Inside the repo (gitignored via .env.*) so Docker can read it on every OS; always deleted.
env_file="$(mktemp .env.smoke.XXXXXX)"
random() { openssl rand -hex 24; }
cat >"$env_file" <<EOF
POSTGRES_USER=repopilot_smoke
POSTGRES_PASSWORD=$(random)
POSTGRES_DB=repopilot
SITE_ADDRESS=localhost
HTTP_PORT=8080
HTTPS_PORT=8443
EDGE_SUBNET=172.28.241.0/24
ENVIRONMENT=production
PUBLIC_APP_URL=https://localhost:8443
CORS_ORIGINS=
AUTH_ENABLED=true
GITHUB_OAUTH_CLIENT_ID=smoke-test-client
GITHUB_OAUTH_CLIENT_SECRET=$(random)
SESSION_SECRET=$(random)
AUTH_ALLOWED_GITHUB_USERS=smoke-test-user
OPENAI_API_KEY=placeholder-not-used-by-the-smoke-test
EOF

compose=(docker compose -p repopilot-smoke -f docker-compose.prod.yml --env-file "$env_file")
export APP_ENV_FILE="$env_file"
cleanup() {
  status=$?
  if [[ $status -ne 0 ]]; then "${compose[@]}" logs --no-color --tail 80 || true; fi
  "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -f "$env_file"
  exit $status
}
trap cleanup EXIT

"${compose[@]}" up -d --no-build --wait --wait-timeout 180

base="https://localhost:8443"
fetch() { curl -sk --max-time 15 -o /dev/null -w '%{http_code}' "$@"; }
expect() {
  local want="$1" got="$2" what="$3"
  if [[ "$got" != "$want" ]]; then echo "FAIL: $what (expected $want, got $got)"; exit 1; fi
  echo "ok: $what ($got)"
}

[[ "$("${compose[@]}" ps -a migrate --format '{{.ExitCode}}')" == "0" ]] || {
  echo "FAIL: migrations did not complete"; exit 1; }
echo "ok: migrations completed"
expect 200 "$(fetch "$base/health")" "liveness /health"
expect 200 "$(fetch "$base/ready")" "readiness /ready"
expect 401 "$(fetch "$base/api/reviews")" "history requires sign-in"
expect 401 "$(fetch -X POST -H 'Content-Type: application/json' \
  -d '{"owner":"octocat","repo":"Hello-World","pull_number":1}' "$base/api/reviews/github")" \
  "review run requires sign-in"
expect 200 "$(fetch "$base/reviews/00000000-0000-4000-8000-000000000000")" "SPA deep link"
expect 302 "$(fetch "$base/api/auth/login")" "login redirects to GitHub"
# Capture before matching: `grep -q` in a pipeline can SIGPIPE curl and trip pipefail.
login_headers="$(curl -sk --max-time 15 -i "$base/api/auth/login")"
grep -qiE '^location: https://github\.com/login/oauth/authorize\?' <<<"$login_headers" \
  || { echo "FAIL: login redirect target"; exit 1; }
echo "ok: login redirect target is GitHub"
auth_status="$(curl -sk --max-time 15 "$base/api/auth/me")"
grep -q '"auth_enabled":true' <<<"$auth_status" || { echo "FAIL: /api/auth/me"; exit 1; }
echo "ok: auth enabled"
echo "Production stack smoke test passed."
