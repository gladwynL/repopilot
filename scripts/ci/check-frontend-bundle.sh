#!/usr/bin/env bash
# The browser bundle may only contain VITE_* values; fail if backend-only settings leaked in.
set -euo pipefail
dist="${1:-frontend/dist}"
[[ -d "$dist" ]] || { echo "::error::$dist not found; build the frontend first."; exit 1; }
if grep -rnE 'OPENAI_API_KEY|SESSION_SECRET|GITHUB_OAUTH_CLIENT_SECRET|GITHUB_TOKEN|DATABASE_URL|sk-(proj-)?[A-Za-z0-9_-]{32,}' "$dist"; then
  echo "::error::Backend-only configuration found in the frontend bundle."; exit 1
fi
echo "Frontend bundle contains no backend secrets."
