---
name: eaveside-ops
description: Bootstrap any session into Haley's Eaveside marketing automation (Discord bots, scheduled client reports, task queue, GitHub repo). Use when Haley says "run the queue", "check the bot", "check discord", "restore the report system", "onboard new client", "log:" entries for a client work log, or anything about the Roofing Force channel, MKTG Bot, negative keyword approvals, or client report automation. Loads full context so she never has to re-explain the setup.
---

# Eaveside Ops — session bootstrap

Haley runs a client-marketing automation system. You are already connected to
everything you need — do NOT ask her for context. Bootstrap, then act.

## Bootstrap (do this first, ~1 minute)

1. **Get credentials + code.** Preferred: stage the env file from her Mac via the
   device bridge — `device_stage_files` on
   `/Users/haleyk/Documents/Haley Personal Hub/Roofing Agency/automation/eavesidemktg-automation/gads-report/.env`
   — then `git clone https://x-access-token:<github_token from that .env>@github.com/haleysknapp/eavesidemktg-automation.git`.
   If the device is offline: the same full .env (9 lines) is embedded in any of the
   "Roofing Force" scheduled-task prompts — read them via the scheduled-task tools
   (list_triggers) and copy it from there.
2. **Read the source of truth**: `SYSTEM.md` (whole architecture, SOPs, gotchas) and
   `clients.json` (which ad accounts belong to which client, which Discord channel gets
   which reports, all IDs). Put the .env at `gads-report/.env`; `pip install google-ads
   requests --break-system-packages`.
3. Now you know everything. Act on what Haley asked.

## The common asks

- **"run the queue"** → read `tasks/queue.json`; execute every task you can (chrome
  tasks need her Chrome open via claude-in-chrome — check it's available); move
  completed entries to `tasks/done.json` with a result + timestamp; commit and push
  (`bash push.sh`); post one line per completed task to the client's Discord channel
  via `gads-report/discord_post.py` `dp.say()`.
- **"check the bot"** → read `mktg-bot/logs/listener.log` and `.err` on her Mac via the
  device bridge. "logged in as MKTG Bot" = alive. Crash loops: see SYSTEM.md §6 gotchas
  (SSL certifi, Message Content Intent). Update procedure = the install one-liner in
  SYSTEM.md §6.
- **Discord anything** → the reaction protocol is law: 👀 = seen/working, ✅ = done,
  ⚠️ = failed; never process a human message that already has one of these from the
  bot; always react before and after acting. Reports post as embeds only.
- **"onboard new client X"** → follow SYSTEM.md §10 step by step; update clients.json
  FIRST; never fork the codebase per client.
- **Monthly/weekly report work** → use the `monthly-client-report` skill (Haley's
  judgment rules) + `gads-report/email-voice.md` for any client email. Emails are
  always Gmail DRAFTS, never sent.
- **"log: <something>"** → append a dated bullet to that client's work log file
  (`rf-work-log.md` for Roofing Force), push.

## Standing rules

- Push every change to GitHub (`bash push.sh`) — scheduled runs and the Mac bot restore
  from it; an unpushed change doesn't exist.
- Never change budgets, bids, campaign status, or ads without Haley in the loop.
- apply_negative.py guardrails are law; relay BLOCKs, don't --force unless she insists.
- Discord posts: brief, plain, no corporate tone. No HTML attachments.
