#!/usr/bin/env bash
# Fail if tracked files include env files, build output, dependencies, or credential-like strings.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
status=0

tracked=$(git ls-files)
env_files=$(grep -E '(^|/)\.env(\.[^/]*)?$' <<<"$tracked" | grep -vE '(^|/)\.env\.example$' || true)
generated=$(grep -E '(^|/)(node_modules|dist|\.venv|__pycache__|\.pytest_cache|\.ruff_cache)/' <<<"$tracked" || true)
bad_paths=$(printf '%s\n%s\n' "$env_files" "$generated" | sed '/^$/d')
if [[ -n "$bad_paths" ]]; then
  echo "::error::Tracked files that must not be committed:"; echo "$bad_paths"; status=1
fi

# Real credential formats (OpenAI, GitHub, AWS, private keys). Test sentinels are deliberately
# shorter than these patterns.
patterns='sk-(proj-)?[A-Za-z0-9_-]{32,}|gh[pousr]_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{50,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----'
if git grep -nIE "$patterns" -- ':!*.lock' ':!**/package-lock.json'; then
  echo "::error::Possible credentials found in tracked files (see above)."; status=1
fi

[[ $status -eq 0 ]] && echo "Repository hygiene checks passed."
exit $status
