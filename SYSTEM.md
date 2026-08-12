# EAVESIDE MARKETING AUTOMATION — MASTER SYSTEM DOC

The single source of truth for how Haley's client-marketing automation works.
Any Claude session working on this system reads THIS FILE FIRST. Repo:
`github.com/haleysknapp/eavesidemktg-automation` (private).

Last major update: **2026-08-10 (context consolidation — 8 session dumps, 6 artifacts, legacy memory,
live Apps Script, 86 sheet tabs, and the ad APIs reconciled into one doc set).**

**Companion docs, all canon:**
- **`SOURCE-MAP.md`** — where every number comes from: origin → transport → destination → consumers →
  recipients → verified? → status. Read this before touching any data flow.
- **`SHEETS-PLAN.md`** — the client workbook design and the non-destructive rebuild plan.
- **`CONTRADICTIONS.md`** — every conflict found between sources, resolved or flagged.

---

## 0. Read this before you assume anything

Three structural facts that repeatedly confused past sessions. They are verified:

1. **The Python in this repo and the Apps Script in the sheets are two entirely separate systems that
   share no data.** No script here imports `gspread` or `googleapiclient` or touches
   `sheets.googleapis`. Reports are built from the ad APIs directly. The sheets are populated
   independently by Apps Script. When the two disagree it is nearly always a date-window or
   definitional difference — not a bug.
2. **The automation is split across TWO Google accounts.** `haleysknapp@gmail.com` (`/u/1/`) owns the
   **RF Webhooks** Apps Script project and all 7 of its daily triggers. `haley@eaveside.com` (`/u/0/`)
   owns the **Call Tracking** project (the call grader) and the Google Ads account. Both accounts
   display the name "Haley Knapp", so the Owner column lies — only Owner = "Me" is reliable. **Always
   check both.**
3. **`clients.json` is currently read by zero Python.** It is documentation, not configuration. Every
   client-specific value is hardcoded (see §10).

---

## 1. The architecture in one paragraph

Per client there is: a **Discord channel** where reports land and Haley replies; a set of **cloud
scheduled tasks** (Claude sessions on a calendar) that pull ad platform data and post reports; a **live
bot on Haley's Mac** that answers channel replies in seconds; an **hourly cloud worker** as the safety
net when the Mac is closed; a **task queue** for work that needs Haley present; **two Apps Script
projects** that sync CRM, call, LSA and web-form data into the client's metrics spreadsheet; and **this
GitHub repo** as the master copy everything restores from. Cowork sessions (interactive Claude) are the
hands for anything the automation can't do alone.

## 2. Credentials — where they live

- **Runtime**: `gads-report/.env` (git-ignored, 9 lines: developer_token, client_id, client_secret,
  refresh_token, login_customer_id, discord_webhook, discord_bot_token, discord_channel_id,
  github_token).
- **On Haley's Mac**: the cloned repo lives at
  `~/Documents/Haley Personal Hub/Roofing Agency/automation/eavesidemktg-automation/`.
  ⚠️ **There is no `.env` at `gads-report/.env` on the Mac** — that path in the old docs and in the
  `eaveside-ops` skill is wrong. Bootstrap from `gads-credentials.txt` instead (below).
- **Backups**: **`Roofing Agency/gads-credentials.txt` contains all nine lines including the GitHub
  token** — the old note saying it lacks one is wrong; it is the fastest bootstrap path. Also
  `gads-report-scripts.zip` pinned in the Discord channel as last-resort restore.
- Scheduled-task prompts carry the full .env inline so fresh cloud containers can self-restore.
  ⚠️ **Five trigger prompts embed the same nine live secrets in plaintext**, one with the GitHub PAT
  inline in a clone URL. Anyone who can list triggers has full Ads write, bot, and repo access.
- Apps Script secrets live in **Script Properties on the gmail account**: `ACCULYNX_API_KEY`,
  `GADS_CLIENT_ID`, `GADS_CLIENT_SECRET`, `GADS_DEV_TOKEN`, `GADS_LOGIN_CUSTOMER_ID`,
  `GADS_REFRESH_TOKEN`, `WEBHOOK_KEY`, plus `AUDIT_SPREADSHEET_ID`, `LEADS_SPREADSHEET_ID`,
  `AL_ENRICH_CURSOR`, `RF_HEALTH_STATE`.

## 3. Google Ads structure

- Manager (MCC) account: **968-076-3943** — Haley's. All client accounts link under it; the single
  OAuth refresh token + developer token in .env reach every linked client.
- Roofing Force customer ID: **329-848-8566**. Enabled campaigns: Kansas City `22284561281`,
  St. Louis `14592215201`, Fort Smith `22307503910`, Joplin `22311207505`, Mena `22311255805`.
  Paused: Wichita `23799169822`.
- ⚠️ **`DURING LAST_90_DAYS` is not valid** in the API version in use. Use explicit
  `segments.date BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'`.
- **To onboard a new client's Google account**: Google Ads UI → manager account → Accounts → Link
  existing account → client accepts → note their 10-digit customer ID → add to `clients.json`.

## 4. Scheduled tasks (cloud, all times UTC; run as fresh Claude sessions)

Verified live 2026-08-10. **Only four are enabled.**

| Task | Schedule | What it does |
|---|---|---|
| Google Ads Report | **Mon+Thu 13:00** | `daily_report.py` — yesterday + 7-day performance and budget pacing → Discord embed |
| Search Terms | **Mon+Thu 13:20** | `weekly_terms.py` — 16-week wasted-spend sweep → numbered negative proposals + `pending_negatives.json` |
| Friday Leadership Report + Email | Fri 13:30 | `weekly_exec.py` — Fri–Thu window, Ads + 4 LSA accounts → Discord embed + **Gmail DRAFT** |
| Monthly Executive Report | 1st 14:00 | `monthly_exec.py` + `make_pdf.py` — 13 months, branded HTML + PDF |

🔴 **The hourly worker (`:35`) is OFF — it has not run since 2026-08-07.** That task reads the channel,
applies 👀/✅/⚠️ reactions, maps "approve 1, 3" through `pending_negatives.json`, runs
`apply_negative.py`, and drains `tasks/queue.json`. **Meanwhile the Mon/Thu search-terms job keeps
proposing negatives that nothing applies.** Re-enabling it is the highest-priority operational fix.

Disabled and safe to **delete**: "Weekly Marketing Report (draft)" Monday task — it drafts the same
subject line from a different window off the sheets, so if re-enabled Haley gets two conflicting drafts.
Separate project, do not touch: `roofing-ledger-weekly-seo`.

**Not scheduled anywhere:** the "Paid 8-Week / Weekly Lead Report" PDFs emailed to the client on
2026-08-07. They were built ad hoc from the Marketing Metrics sheet by throwaway container code. A
Thursday auto-send is spec'd but not built. **Rick Davis requires PDF — he cannot open HTML attachments.**

Every scheduled prompt has the same skeleton: SETUP CHECK (restore .env + git clone this repo) → THE
TASK → Discord alert on failure.

## 5. Discord — how the channel works

- Reports are **summary embeds only** — never HTML attachments. Exception: search-terms posts attach
  `pending_negatives.json`.
- **Reaction protocol** (cross-session state; reactions ARE the record): 👀 = seen and working ·
  ✅ = done · ⚠️ = failed (with a reply saying why). Any worker MUST skip human messages already bearing
  one. Haley's rule: no 👀 within an hour → nothing saw it → tell Claude.
- Approvals: "approve all" / "approve 1, 3" / "all except 2". Negatives apply via `apply_negative.py`.
- Posting from code: `discord_post.py` — `dp.say()`, `dp.post()` (embeds), `dp.react()`.

## 6. The live Mac bot

- Code: `mktg-bot/listener.py`; launchd, auto-restart, venv Python. Each human message → 👀 → headless
  `claude -p` session in the gads-report dir → reply via `dp.say` → ✅/⚠️. Backfills on wake.
- Logs: `mktg-bot/logs/listener.log` / `.err`. "logged in as MKTG Bot#5298" = connected.
- Update one-liner: `cd "$HOME/Documents/Haley Personal Hub/Roofing Agency/automation/eavesidemktg-automation" && git fetch origin && git reset --hard origin/main && bash mktg-bot/install.sh`
- Fixed gotchas: macOS SSL certs (certifi shim); Discord **Message Content Intent** must be ON.
- ⚠️ `mktg-bot/gads-report/` is a stale committed duplicate, and `install.sh` can never refresh it
  (it copies only `if [ ! -d gads-report ]`). Fix or delete.
- Bot app: "mktg agent" (app id 1532934859104976907, MKTG Bot#5298).

## 7. The task queue (`tasks/queue.json`)

`needs` routes each entry: `any` → the hourly worker executes it automatically (**currently off**);
`live-session` → waits for "run the queue"; `chrome` → needs Haley's Chrome. Completed entries move to
`tasks/done.json` — ⚠️ **which does not exist yet**; create it on first use.

## 8. Apps Script — the sheet side

| Project | Account | Files | Triggers |
|---|---|---|---|
| **RF Webhooks** `1ZfOUmV4…Gi3lO_` | **gmail** | `Code.gs`, `RF-acculynx-sync.gs`, `RF-lsa-source-tag.gs`, `RF-acculynx-native-rollup.gs`, `RF-acculynx-master.gs.gs`, `RF-lead-outcomes-cache.gs.gs`, `RF-LSA-puller.gs`, `RF-LSA-migrate.gs`, `RF-LSA-sync.gs`, `GeoExport.gs` | **7 time-based, 0% error**: `RF_masterDaily` (~05:30), `RF_dailyPostCache` (06:00), `alnSyncNativeDaily` (~07:00), `RF_healthCheck` (3h), `tagLsaSourceInAccuLynxScheduled` (every 2 days 06:00 Denver), `pullLsaLeads`, `dailyAccuLynxSync` |
| **Call Tracking** `1J57bcvG…` | **eaveside** | 6 incl. `Eaveside-Call-Grader.gs.gs`, `LeadCommand.gs` | daily; ⚠️ **5.41% error rate over 37 executions** |
| **Call Tracking** (duplicate) | gmail | **0 — empty shell** | 0 — safe to delete |
| **RF Chat Leads** | gmail | `Code.gs` | 0 |

`exportJobsGeo()` in `GeoExport.gs` has **no trigger by design** — it is a manual loop
(`geoExportTestOne()` → `geoExportReset()` → repeat `exportJobsGeo()`).

## 9. CLIENT REGISTRY — see `clients.json`

Machine-readable registry of every client. **Update it FIRST when onboarding.** ⚠️ It is currently
documentation only — no code reads it. Wiring it in is the prerequisite for real multi-client support.

## 10. Reports — content & judgment

- Code: `gads-report/*.py`; shared branding in `render_html.py`; PDF via `make_pdf.py`.
- Judgment rules: `skills/monthly-client-report.md` — all of Haley's standing corrections.
- Email voice: `gads-report/email-voice.md`. Always DRAFT, never send.
- Content inputs Haley maintains conversationally: `rf-work-log.md` ("log: …" in Discord appends) and
  `rf-focus.md`.
- **Hardcoded, blocking multi-client:** `config.py` (`CUSTOMER_ID`, `ACCOUNT_NAME`), `lsa.py` (4 LSA
  IDs), `render_html.py` (`MARKET_ALIASES`, RF logo, "for Roofing Force leadership" footer),
  `monthly_exec.py` (RF YoY paragraph), `classify.py` (RF geography token list), `listener.py` (one
  channel ID). `out/` and `state/` are flat — two clients would collide.

## 11. NEW CLIENT ONBOARDING SOP

See **`SHEETS-PLAN.md` §6** for the full instantiation checklist including the four-workbook set.
Summary: `clients.json` entry first → link Google Ads under the MCC → create the four workbooks from
templates → Discord channel + webhook → clone the four trigger prompts → stand up ingestion → fill Work
Scope and Business Model targets → verify by firing each trigger once. **Never fork the codebase per
client.**

## 12. THE GOING-FORWARD RULE

This is how the "every session knows something different" problem stays solved.

1. **Every session ends with a context dump** into
   `Roofing Agency/_context-consolidation/session-dumps/` — until the next consolidation supersedes
   them. Write what you changed, what you read, what you decided, and what you are unsure about.
2. **Every account, site, or tracking change gets a Change Log row the same day.** No exceptions. An
   unlogged change is what costs the next session an hour — and it is exactly why the 2026-07-31
   conversion demotion got re-investigated twice.
3. **Every new client gets this structure from day one** — `clients.json` entry, the four workbooks,
   a hub file, and a Change Log.
4. **Canon is this repo (SYSTEM.md, clients.json, SOURCE-MAP.md, SHEETS-PLAN.md, CONTRADICTIONS.md)
   plus the Change Log tab.** Session dumps and the old `_device-transfer/claude-project/memory/`
   folder are archived input — mine them, never cite them as authority.
5. **Every figure carries its date window**, and every LSA figure states whether it counts all leads or
   charged leads. Two correct reports with invisible windows caused a client-facing escalation on
   2026-08-07.
6. **Verify before you assert.** When you verify something live, say how — SOURCE-MAP.md's verification
   log is the model.

## 13. Fresh-session bootstrap

The saved **eaveside-ops** skill triggers on "run the queue" / "check the bot" / "onboard new client".
Steps: read `gads-credentials.txt` from the Roofing Agency folder via the device bridge (or copy the
.env from a scheduled-task prompt) → `git clone` this repo → put the creds at `gads-report/.env` →
`pip install google-ads requests --break-system-packages` → read SYSTEM.md + clients.json + SOURCE-MAP.md
→ act. Haley never re-explains context.
