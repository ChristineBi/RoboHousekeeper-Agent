#!/usr/bin/env bash
# Initialize this directory as a git repo and prepare it for pushing to GitHub.
#
# Usage:
#   bash scripts/init_github.sh                # init local repo
#   bash scripts/init_github.sh <github-url>   # init + add origin + push
#
# Tip: create the empty repo on GitHub first (without README / .gitignore / LICENSE),
# then pass its SSH or HTTPS URL.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

if [ -d .git ]; then
  echo "[init] .git already exists in $REPO_DIR; skipping git init."
else
  git init -b main
fi

git add .
git commit -m "M0: research doc + skill library + mock pipeline" || true

if [ "${1:-}" != "" ]; then
  URL="$1"
  if git remote get-url origin >/dev/null 2>&1; then
    echo "[init] origin already set to: $(git remote get-url origin)"
  else
    git remote add origin "$URL"
    echo "[init] origin set to: $URL"
  fi
  echo "[init] pushing to origin/main ..."
  git push -u origin main
fi

echo "[init] done."
