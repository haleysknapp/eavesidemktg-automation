#!/bin/bash
# One-shot: publish this folder to github.com/haleysknapp/eavesidemktg-automation
set -e
cd "$(dirname "$0")"
CRED_FILE=""
# 2026-08-13 (Fix Queue #24): the ONLY .env that exists on the Mac is
# mktg-bot/gads-report/.env — the tree the bot actually runs. The old list checked
# gads-report/.env, which does not exist, so push.sh failed with "github_token not
# found" on a clean checkout. Also added ../../../gads-credentials.txt: the repo now
# lives at "Roofing Agency/03 Eaveside Product/automation/eavesidemktg-automation",
# which is three levels down from the credentials file, not two.
for c in \
  "mktg-bot/gads-report/.env" \
  "gads-report/.env" \
  "/home/claude/gads-report/.env" \
  "$HOME/gads-report/.env" \
  "../../../gads-credentials.txt" \
  "../../gads-credentials.txt" \
  "../gads-credentials.txt" \
  "$HOME/gads-credentials.txt" \
  "/home/claude/gads-credentials.txt" ; do
  [ -f "$c" ] && grep -q '^github_token=' "$c" && CRED_FILE="$c" && break
done
[ -n "$CRED_FILE" ] || {
  echo "❌ github_token not found. Checked:"
  echo "   mktg-bot/gads-report/.env   <- the one the bot loads"
  echo "   gads-report/.env"
  echo "   ../../../gads-credentials.txt"
  exit 1
}
echo "→ credentials: $CRED_FILE"
TOKEN=$(grep '^github_token=' "$CRED_FILE" | cut -d= -f2)
[ -n "$TOKEN" ] || { echo "❌ github_token line present but empty in $CRED_FILE"; exit 1; }
git init -q -b main 2>/dev/null || true
git add -A
git -c user.email="haleysknapp@gmail.com" -c user.name="Haley Knapp" commit -qm "Roofing Force automation: scripts, live bot, task queue" || echo "(nothing new to commit)"
git remote remove origin 2>/dev/null || true
git remote add origin "https://x-access-token:${TOKEN}@github.com/haleysknapp/eavesidemktg-automation.git"
git push -q -u origin main
echo "✅ pushed to github.com/haleysknapp/eavesidemktg-automation"
