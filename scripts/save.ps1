# One command to save your work to GitHub, safely.
#
#   powershell -ExecutionPolicy Bypass -File scripts\save.ps1 "what you did"
#
# Handles the case where a teammate pushed while you were working. Because each
# person edits only their own files (see WORKFLOW.md), the rebase never
# conflicts.
param([string]$Message = "progress")

Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "==> checking for credentials before anything else"
python scripts\secret_scan.py --quiet
if ($LASTEXITCODE -ne 0) {
  Write-Host ""
  Write-Host "STOPPED. A credential may be in your files. Nothing was pushed."
  Write-Host "Fix what it printed above, then run this again."
  exit 1
}

Write-Host "==> saving your changes locally"
git add -A
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) { git commit -q -m $Message }
else { Write-Host "    (nothing changed - skipping commit)" }

Write-Host "==> getting teammates' work and stacking yours on top"
git pull --rebase --autostash
if ($LASTEXITCODE -ne 0) {
  Write-Host ""
  Write-Host "The rebase stopped. This should not happen if you only edited your"
  Write-Host "own files. Run 'git status' and send the output to the group."
  Write-Host "To undo: git rebase --abort"
  exit 1
}

Write-Host "==> pushing"
$branch = git rev-parse --abbrev-ref HEAD
git push origin $branch
if ($LASTEXITCODE -ne 0) {
  Write-Host ""
  Write-Host "Push failed - someone pushed seconds ago. Run this same command again."
  exit 1
}

Write-Host ""
Write-Host "Done. Your work is on GitHub."
