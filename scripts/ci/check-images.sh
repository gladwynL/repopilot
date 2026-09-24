#!/usr/bin/env bash
# Inspect built production images: no VCS metadata, env files, tests, or dev tooling.
set -euo pipefail
api_image="${1:?api image}"
web_image="${2:?web image}"

docker run --rm --entrypoint sh "$api_image" -c '
  set -e
  [ "$(id -u)" != "0" ] || { echo "API image runs as root"; exit 1; }
  for p in /app/.git /app/.env /app/tests /app/requirements-dev.txt; do
    [ ! -e "$p" ] || { echo "unexpected $p in API image"; exit 1; }
  done
  ! python -c "import pytest" 2>/dev/null || { echo "pytest in API image"; exit 1; }
  echo "API image OK"
'
docker run --rm --entrypoint sh "$web_image" -c '
  set -e
  [ -f /srv/index.html ] || { echo "index.html missing"; exit 1; }
  if find / \( -name .git -o -name ".env" -o -name ".env.*" -o -name node_modules \) \
       -not -path "/proc/*" 2>/dev/null | grep -q .; then
    echo "unexpected files in web image"; exit 1
  fi
  echo "Web image OK"
'
