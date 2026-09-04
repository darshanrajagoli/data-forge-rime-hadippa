#!/usr/bin/env bash
# One command to save your work to GitHub, safely.
#
#   bash scripts/save.sh "what you did"
#
# Handles the case where a teammate pushed while you were working, which is
# the only git problem this project can produce. Because each person edits only
# their own files (see WORKFLOW.md), the rebase below never conflicts.
set -uo pipefail

MSG="${1:-progress}"
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "==> checking for credentials before anything else"
if ! python scripts/secret_scan.py --quiet; then
  echo ""
  echo "STOPPED. A credential may be in your files. Nothing was pushed."
  echo "Fix what it printed above, then run this again."
  exit 1
fi

echo "==> saving your changes locally"
git add -A
if git diff --cached --quiet; then
  echo "    (nothing changed - skipping commit)"
else
  git commit -q -m "$MSG" || true
fi

echo "==> getting teammates' work and stacking yours on top"
if ! git pull --rebase --autostash; then
  echo ""
  echo "The rebase stopped. This should not happen if you only edited your own"
  echo "files. Run this and send the output to the group:"
  echo "    git status"
  echo "To undo and get back to where you were:"
  echo "    git rebase --abort"
  exit 1
fi

echo "==> pushing"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if ! git push origin "$BRANCH"; then
  echo ""
  echo "Push failed. Someone pushed in the last few seconds. Just run this"
  echo "same command again - it will work."
  exit 1
fi

echo ""
echo "Done. Your work is on GitHub."
