#!/bin/bash
# MKTG Bot live listener — one-shot installer. Run from inside the repo:
#   bash mktg-bot/install.sh
set -e
cd "$(dirname "$0")"
mkdir -p logs

echo "→ setting up python environment..."
python3 -m venv .venv
./.venv/bin/pip -q install --upgrade pip
./.venv/bin/pip -q install "discord.py" google-ads requests

echo "→ wiring report scripts..."
if [ ! -d gads-report ] && [ -d ../gads-report ]; then
  cp -R ../gads-report .
fi
[ -d gads-report ] || { echo "❌ gads-report folder not found"; exit 1; }

echo "→ wiring credentials..."
CREDS=""
for p in "../../../gads-credentials.txt" "../../gads-credentials.txt"; do
  [ -f "$p" ] && CREDS="$p" && break
done
[ -n "$CREDS" ] || { echo "❌ gads-credentials.txt not found in Roofing Agency folder"; exit 1; }
cp "$CREDS" gads-report/.env

echo "→ checking Claude Code CLI..."
command -v claude >/dev/null 2>&1 || {
  echo "❌ 'claude' command not found. Install Claude Code first (https://claude.com/claude-code), then re-run.";
  exit 1;
}

echo "→ installing launch agent (starts now + on every boot, auto-restarts)..."
PLIST="$HOME/Library/LaunchAgents/com.eaveside.mktgbot.plist"
mkdir -p "$HOME/Library/LaunchAgents"
sed "s|__DIR__|$(pwd)|g" com.eaveside.mktgbot.plist.template > "$PLIST"
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

sleep 3
if launchctl list | grep -q com.eaveside.mktgbot; then
  echo "✅ MKTG Bot is live. Try replying in #roofing-force. Logs: $(pwd)/logs/listener.log"
else
  echo "⚠️ Launch agent didn't start — check logs/listener.err"
fi
