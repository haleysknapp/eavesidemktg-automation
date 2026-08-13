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

# ----------------------------------------------------------------------------------
# 2026-08-13: gads-report divergence guard.
#
# There are two copies of gads-report:
#   gads-report/            <- the working copy Haley and cloud sessions edit
#   mktg-bot/gads-report/   <- THE ONE THE MAC BOT ACTUALLY EXECUTES
#
# They are separate on purpose (the bot copy owns .env, out/ and state/), but the
# CODE must match. When it drifted, the bot silently kept running an older report:
# weekly_exec.py in the bot tree had lost the basis_notes counting-basis guard, so
# the report that actually went out was missing a caveat the other copy printed.
# Nothing errored. That is exactly how a wrong number reaches a client.
#
# Fix drift with:  bash push.sh --sync   (copies gads-report/ -> mktg-bot/gads-report/)
# ----------------------------------------------------------------------------------
SYNC_EXCLUDE='^(\.env|out|state|__pycache__|token-cost-log\.csv|\.DS_Store)$'
sync_pairs() {
  ( cd gads-report 2>/dev/null && ls -A ) | grep -vE "$SYNC_EXCLUDE"
}
if [ -d gads-report ] && [ -d mktg-bot/gads-report ]; then
  if [ "$1" = "--sync" ]; then
    for f in $(sync_pairs); do cp -R "gads-report/$f" "mktg-bot/gads-report/$f"; done
    echo "→ synced gads-report/ → mktg-bot/gads-report/"
  fi
  DRIFT=""
  for f in $(sync_pairs); do
    if [ ! -e "mktg-bot/gads-report/$f" ]; then
      DRIFT="$DRIFT\n   MISSING in bot tree : $f"
    elif ! diff -rq "gads-report/$f" "mktg-bot/gads-report/$f" >/dev/null 2>&1; then
      DRIFT="$DRIFT\n   DIFFERS             : $f"
    fi
  done
  if [ -n "$DRIFT" ]; then
    echo "❌ gads-report/ and mktg-bot/gads-report/ have diverged."
    echo "   mktg-bot/gads-report/ is the tree the Mac bot RUNS — if the change you are"
    echo "   pushing is not in it, the bot's behaviour does not change."
    printf "$DRIFT\n"
    echo ""
    echo "   Fix:  bash push.sh --sync     (then re-run: bash push.sh)"
    echo "   Skip: PUSH_ALLOW_DRIFT=1 bash push.sh   (only if the drift is intentional)"
    [ "$PUSH_ALLOW_DRIFT" = "1" ] || exit 1
    echo "   ⚠️  PUSH_ALLOW_DRIFT=1 set — pushing anyway."
  else
    echo "→ gads-report trees in sync"
  fi
fi

TOKEN=$(grep '^github_token=' "$CRED_FILE" | cut -d= -f2)
[ -n "$TOKEN" ] || { echo "❌ github_token line present but empty in $CRED_FILE"; exit 1; }
git init -q -b main 2>/dev/null || true
git add -A
git -c user.email="haleysknapp@gmail.com" -c user.name="Haley Knapp" commit -qm "Roofing Force automation: scripts, live bot, task queue" || echo "(nothing new to commit)"
git remote remove origin 2>/dev/null || true
git remote add origin "https://x-access-token:${TOKEN}@github.com/haleysknapp/eavesidemktg-automation.git"
git push -q -u origin main
echo "✅ pushed to github.com/haleysknapp/eavesidemktg-automation"
