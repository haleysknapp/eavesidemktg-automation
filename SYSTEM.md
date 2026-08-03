# EAVESIDE MARKETING AUTOMATION — MASTER SYSTEM DOC

The single source of truth for how Haley's client-marketing automation works.
Any Claude session working on this system reads THIS FILE FIRST. Repo:
`github.com/haleysknapp/eavesidemktg-automation` (private).

Last major update: 2026-08-03 (July 2026 RF monthly cycle).

---

## 1. The architecture in one paragraph

Per client there is: a **Discord channel** where reports land and Haley replies; a set of
**cloud scheduled tasks** (Claude sessions on a calendar) that pull ad platform data and
post reports; a **live bot on Haley's Mac** that answers channel replies in seconds; an
**hourly cloud worker** as the safety net when the Mac is closed; a **task queue** for
work that needs Haley present; and **this GitHub repo** as the master copy everything
restores from. Cowork sessions (interactive Claude) are the hands for anything the
automation can't do alone.

## 2. Credentials — where they live

- **Runtime**: `gads-report/.env` (git-ignored, 9 lines: developer_token, client_id,
  client_secret, refresh_token, login_customer_id, discord_webhook, discord_bot_token,
  discord_channel_id, github_token).
- **On Haley's Mac**: the cloned repo at
  `~/Documents/Haley Personal Hub/Roofing Agency/automation/eavesidemktg-automation/gads-report/.env`
  — a fresh Cowork session can stage this via the device bridge to bootstrap.
- **Backups**: `gads-credentials.txt` / `gads-credentials-v2.txt` in the
  "Roofing Agency" folder (Google Ads + Discord webhook; NO github token — that's in .env),
  and a `gads-report-scripts.zip` pinned in the Discord channel as last-resort restore.
- Scheduled-task prompts carry the full .env inline so fresh cloud containers can
  self-restore without any human.

## 3. Google Ads structure

- Manager (MCC) account: **968-076-3943** — Haley's. All client accounts link under it;
  the single OAuth refresh token + developer token in .env reach every linked client.
- **To onboard a new client's Google account**: Google Ads UI → manager account →
  Accounts → Link existing account → client accepts → note their 10-digit customer ID →
  add to the client registry (§8). The same .env then works; scripts just need the new
  customer ID.

## 4. Scheduled tasks (cloud, all times UTC; run as fresh Claude sessions)

| Task | Schedule | What it does |
|---|---|---|
| Daily Pulse | daily 13:00 | Yesterday's leads/spend/CPL vs trailing avg → Discord embed |
| Search Terms | Mon+Thu 13:00 | Wasted-spend sweep → numbered negative proposals + pending_negatives.json attachment |
| Friday Leadership Report + Email | Fri 13:30 | Weekly report (API data) → Discord embed + HTML via SendUserFile + Gmail DRAFT in Haley's voice |
| Monthly Executive Report | 1st 14:00 | Full branded monthly (HTML+PDF), initiatives from work log, focus from rf-focus.md |
| Hourly Worker (inbox + queue) | hourly :35 | Reads channel replies, applies approvals, runs "needs:any" queue tasks, 👀/✅ reactions |
| GBP check-in (one-shot) | 2026-08-04 | Joplin review-test readout |

Disabled: "Weekly Marketing Report (draft)" Monday task — merged into Friday.
Separate project (do not touch): roofing-ledger-weekly-seo (Mondays, Roofing Ledger site).

Every scheduled prompt has the same skeleton: SETUP CHECK (restore .env + git clone this
repo into /home/claude/gads-report) → THE TASK → Discord alert on failure.

## 5. Discord — how the channel works

- Reports are **summary embeds only** — never HTML attachments (Haley won't download
  them). Exception: search-terms posts attach `pending_negatives.json` (machine-readable
  approval map, not for humans).
- **Reaction protocol** (cross-session state; reactions ARE the record):
  👀 = a bot has seen the message and is working · ✅ = done · ⚠️ = failed (with a reply
  saying why). Any worker MUST skip human messages already bearing 👀/✅/⚠️ — that's how
  the Mac bot and cloud worker avoid double-processing. Haley's rule: no 👀 within an
  hour → nothing saw it → tell Claude.
- Approvals: Haley replies "approve all" / "approve 1, 3" / "all except 2" to a
  proposals post. Negatives apply via `apply_negative.py` (SOP guardrails: never own
  brand, never converted-in-60d, never core lead intent; campaign-level; paused
  campaigns skipped and noted).
- Posting from code: `discord_post.py` — `dp.say()`, `dp.post()` (embeds), `dp.react()`.

## 6. The live Mac bot

- Code: `mktg-bot/listener.py`; runs under launchd (auto-start on boot, auto-restart),
  venv Python. Each human message → 👀 reaction → headless `claude -p` session in the
  gads-report dir → reply via dp.say → ✅/⚠️ reaction. Backfills missed messages on wake.
- Logs: `mktg-bot/logs/listener.log` (stdout) and `listener.err`. A Cowork session can
  read these via the device bridge to verify liveness — "logged in as MKTG Bot#5298" =
  connected. The install one-liner (also the update procedure):
  `cd "$HOME/Documents/Haley Personal Hub/Roofing Agency/automation/eavesidemktg-automation" && git fetch origin && git reset --hard origin/main && bash mktg-bot/install.sh`
- Known gotchas already fixed in code: macOS SSL certs (certifi shim), Discord
  **Message Content Intent** must be ON in the developer portal per bot app.
- Bot app: "mktg agent" (application id 1532934859104976907, bot user MKTG Bot#5298),
  owned by Haley's Discord account.

## 7. The task queue (`tasks/queue.json`)

Escalation path for work beyond a headless bot's powers. Entry format is documented in
README.md. The `needs` field routes it:
- `any` — API-safe, already requested by Haley in Discord → the hourly worker executes
  it automatically within the hour.
- `live-session` — budget/bid/status changes → waits for Haley to open Cowork and say
  **"run the queue"** (deliberate human gate).
- `chrome` — needs Haley's Chrome open (GSC, GBP, anything without an API) → same.
Completed entries move to `tasks/done.json` with a `result`; commit + push; one-line
confirmation per task to the client channel.

## 8. CLIENT REGISTRY — see `clients.json`

Machine-readable registry of every client: ad account IDs, LSA accounts, Discord
channel, email recipients, sheets, site pages, logo, folders. **clients.json is the
authority for "which account belongs to which client and which channel gets which
reports."** Roofing Force is the only production client today.

## 9. Reports — content & judgment

- Code: `gads-report/*.py`; shared branding in `render_html.py` (Eaveside masthead +
  client logo, embedded Inter, validated palette); PDF via `make_pdf.py`.
- Judgment rules (what to include/exclude, YoY framing, market merging, GSC diagnosis
  rules, audit-sheet eligibility): `skills/monthly-client-report.md` — ALL of Haley's
  standing corrections live there. Follow it for any client.
- Email voice: `gads-report/email-voice.md` — exemplar + rules. Always DRAFT, never send.
- Content inputs Haley maintains conversationally: `rf-work-log.md` (dated initiative
  bullets; "log: ..." in Discord appends) and `rf-focus.md` (next month's priorities,
  in her words).

## 10. NEW CLIENT ONBOARDING SOP

Current code is single-client (RF). Onboarding client #2 = one Cowork session saying
"onboard new client <name> per SYSTEM.md". That session should:

1. **Access**: link client's Google Ads account under MCC 968-076-3943 (§3); LSA
   accounts too if any. Collect: customer ID(s), site URL, logo, brand colors,
   audit-sheet ID, email recipients, GSC access (via Haley's Chrome).
2. **Discord**: create #<client> channel in the same server; create a channel webhook;
   the existing bot account covers all channels — extend `mktg-bot/listener.py` to a
   channel→client map (currently single-channel).
3. **Code**: parameterize gads-report into per-client config (registry-driven:
   clients.json entry supplies IDs, channel, webhook, pages, logo). Keep ONE codebase —
   never fork per client.
4. **Scheduled tasks**: clone the four RF trigger prompts with the new client's values
   (daily, Mon/Thu terms, Friday, monthly) + extend the hourly worker to loop all
   channels in clients.json.
5. **Registry**: add the complete clients.json entry FIRST — it drives everything else.
6. **Verify**: fire each trigger once manually; confirm embeds in the right channel,
   a test approval round-trips with 👀/✅, and the monthly renders with the client's logo.
7. Work log + focus files per client: `<client>-work-log.md`, `<client>-focus.md`.

## 11. Fresh-session bootstrap (how any Cowork session gets context)

The saved **eaveside-ops** skill triggers on "run the queue" / "check the bot" /
"onboard new client" / Eaveside-Discord-report phrases and contains these exact steps:
stage `.env` from the Mac clone (device bridge) or read the trigger prompts via
list_triggers → clone this repo → read SYSTEM.md + clients.json → act. Haley never
re-explains context.
