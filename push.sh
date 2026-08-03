#!/bin/bash
# One-shot: publish this folder to github.com/haleysknapp/eavesidemktg-automation
set -e
cd "$(dirname "$0")"
CRED_FILE=""
for c in "$HOME/gads-report/.env" "gads-report/.env" "../../gads-credentials.txt" "../gads-credentials.txt" "$HOME/gads-credentials.txt"; do
  [ -f "$c" ] && grep -q '^github_token=' "$c" && CRED_FILE="$c" && break
done
[ -n "$CRED_FILE" ] || { echo "❌ github_token not found (checked gads-report/.env and gads-credentials.txt)"; exit 1; }
TOKEN=$(grep '^github_token=' "$CRED_FILE" | cut -d= -f2)
[ -n "$TOKEN" ] || { echo "❌ github_token not found in gads-credentials.txt"; exit 1; }
git init -q -b main 2>/dev/null || true
git add -A
git -c user.email="haleysknapp@gmail.com" -c user.name="Haley Knapp" commit -qm "Roofing Force automation: scripts, live bot, task queue" || echo "(nothing new to commit)"
git remote remove origin 2>/dev/null || true
git remote add origin "https://x-access-token:${TOKEN}@github.com/haleysknapp/eavesidemktg-automation.git"
git push -q -u origin main
echo "✅ pushed to github.com/haleysknapp/eavesidemktg-automation"
