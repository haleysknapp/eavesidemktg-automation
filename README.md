# eavesidemktg-automation

Eaveside's marketing automation for **Roofing Force** (Google Ads account 329-848-8566). This repo is the single source of truth for the report scripts — cloud scheduled tasks `git pull` it on every run, and the live Discord bot on Haley's Mac uses the same scripts.

**No credentials live in this repo.** Runtime credentials come from `gads-report/.env` (created at deploy time from Haley's `gads-credentials.txt`; git-ignored here).

## Layout
- `gads-report/` — report + action scripts (daily report, Mon/Thu search-terms analyzer with proposed negatives, Friday leadership report, monthly executive report, `apply_negative.py` with SOP guardrails, Discord posting lib).
- `mktg-bot/` — the live Discord listener that runs on Haley's Mac (launchd) and hands each channel message to a headless Claude Code session.
- `tasks/queue.json` — the escalation task queue. When the live bot hits something outside its powers (budget/bid changes, Chrome-required work), it writes a complete task spec here and tells Haley "say 'run the queue'". Any Claude session processes it with: read `tasks/queue.json`, execute each task, move finished entries to `tasks/done.json` with a `result` field, push.

## Task queue entry format
```json
{
  "id": "2026-08-02-budget-kc",
  "created": "2026-08-02T21:00:00Z",
  "requested_by": "Haley (Discord)",
  "needs": "live-session|chrome|any",
  "title": "Raise KC daily budget to $X",
  "spec": "Full self-contained instructions, context, and why — written so a fresh Claude session can execute without asking questions.",
  "source_message": "discord message link or quote"
}
```

## For any Claude session told to "run the queue"
1. `git clone` this repo (token in Haley's `gads-credentials.txt` as `github_token`).
2. Read `tasks/queue.json`; execute every task whose `needs` you can satisfy (chrome tasks need Haley's Chrome open via Claude-in-Chrome).
3. Move completed entries to `tasks/done.json` with `result` + timestamp; leave blocked ones with a `blocked` note; commit and push.
4. Post a one-line summary per completed task to the #roofing-force Discord channel via `gads-report/discord_post.py` `dp.say()`.
