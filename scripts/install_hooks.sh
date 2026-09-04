#!/usr/bin/env bash
# Install a pre-commit hook that refuses to commit a credential.
#   bash scripts/install_hooks.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$ROOT/.git/hooks/pre-commit"
if [ ! -d "$ROOT/.git" ]; then
  echo "not a git repository yet - run 'git init' first" >&2
  exit 1
fi
cat > "$HOOK" <<'HOOKEOF'
#!/usr/bin/env bash
# Waypoint: block commits containing credentials.
ROOT="$(git rev-parse --show-toplevel)"
python "$ROOT/scripts/secret_scan.py" --staged || {
  echo ""
  echo "Commit blocked by scripts/secret_scan.py."
  echo "Fix the finding above, or use --no-verify only if you are certain."
  exit 1
}
HOOKEOF
chmod +x "$HOOK"
echo "installed: $HOOK"
