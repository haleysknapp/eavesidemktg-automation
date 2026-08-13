# PROMPT — Ingest, attribute and grade Facebook leads in Marketing Metrics

Paste this whole file as the first message of a new session.

---

You are picking up a scoped piece of work for Haley Knapp (Eaveside, a marketing
automation agency) for her client **Roofing Force**, a roofing contractor operating in
Kansas, Missouri and Arkansas.

**Start by invoking the `eaveside-ops` skill** — it bootstraps you into the whole system
(repo, credentials, Discord bot, scheduled reports). Do not ask Haley to re-explain any
of the setup; it is all discoverable.

## The job

Facebook leads need to land in the **Marketing Metrics** workbook, attributed to
Facebook and call-graded, **exactly the way Google Ads and LSA leads already do**. Today
none of that exists. Meta lead data lives only in Ads Manager as an aggregate count.

The deliverable is a working pipeline, not a document — but **scope and report findings
before building** (see "First deliverable" below).

## What was done on 2026-08-13 (do not redo, do not re-litigate)

A prior session wired Meta into the **aggregate reporting** pipeline. That is finished,
tested, pushed as commit `abc3f5b`, and is a different thing from this job:

- `gads-report/meta.py` reads Ads Manager insights (`/act_1779635922176764/insights`)
  and returns daily **spend** and **Facebook-attributed result counts**.
- `weekly_exec.py` / `monthly_exec.py` build totals from a **channel list**, so blended
  cost per lead includes Meta spend. `daily_report.py` mentions Meta in the Discord
  pulse on days with Meta spend.
- `clients.json` is now **partially load-bearing** — `clients.roofing-force.meta` holds
  the Meta IDs and `meta.py` reads it at runtime. It is the model to follow if you add
  more Meta config.
- A never-expiring Meta **System User** token (`eaveside reporting-api`, ID
  `61592889615948`, `ads_read` only) is live in `mktg-bot/gads-report/.env` as
  `meta_access_token`. **It is read-only and scoped to the ad account.** If this job
  needs to read anything beyond ad-account insights, that is a new permission and a
  conversation with Haley — do not silently widen it.
- Internal Master Change Log rows **81–84** describe all of the above. Read them.

**Critically: that work is aggregate only.** It counts leads. It does not know what any
individual lead *was*, who it came from, or whether the call was any good. That is this
job.

## What already exists for Google Ads and LSA — the pattern to copy

The Marketing Metrics workbook (`1Eguf8HwR0wU9Q-DO_JF5ctDCebparkw3BgyvDMiYoLc`, 38+ tabs)
already has the shape you need. Relevant tabs, from a live listing on 2026-08-13:

| Tab | Apparent role |
|---|---|
| `Leads` | the main ledger |
| `Lead Detail` | per-lead breakout |
| `Web Leads (auto)` | web-form ingest — **currently EMPTY, see landmines** |
| `LSA Leads (auto)` | LSA ingest — the working example of a `(auto)` feeder |
| `Chatbot (auto)` | chatbot ingest |
| `Call Grades` | call grading output |
| `Call Intelligence Findings` | grader analysis |
| `Attribution Ledger` | current attribution answer (supersedes `_ClosedLoop`) |
| `Conversion Config` | probably where source/conversion mapping is defined |
| `Source Map` | in-sheet lineage |
| `Feed Health`, `Health Log` | feed monitoring |

**There is no `Meta Leads (auto)` or equivalent.** The naming convention suggests that
is roughly the shape of the answer, but confirm rather than assume.

> ⚠️ **`SOURCE-MAP.md` in the repo has a TAB REGISTER** — one row per tab across all four
> workbooks, stating what each tab answers, what it rests on, whether each number is
> MEASURED or ASSUMED, its `n`, and whether it is client-safe. **Read that register before
> re-deriving anything.** It will save you hours and it supersedes older notes in the same
> file about `_ClosedLoop`'s ~9% match rate.

### The Apps Script side

Ingest and grading run in Apps Script, not in the Python repo. Per `clients.json`, the
projects are split across two Google accounts that **both display the name "Haley Knapp"**
— always check both:

- **haley@eaveside.com** (`/u/0/`) — `Call Tracking` (the call grader), `Site Leads`,
  `LSA Lead Tracker`
- **haleysknapp@gmail.com** (`/u/1/`) — `RF Webhooks` (7 daily triggers, all AccuLynx /
  LSA / webhook sync), `RF Chat Leads`

> 🔴 **Only `RF Webhooks` is in the repo** (`apps-script/RF-Webhooks/RF-webhook-receiver.gs`
> and `GeoExport.gs`). The **call grader source is NOT version controlled** — it exists
> only live in Apps Script. Getting it into the repo is arguably part of this job; raise
> it with Haley.

> 🔴 **There are TWO Apps Script projects named "Call Tracking" and two call graders.**
> The `eaveside-ops` skill warns about this explicitly. Only `Owner = "Me"` is reliable in
> the Apps Script UI. **Never assert system state from whichever copy you opened first.**

## 📌 How CTM already sources and identifies Facebook leads — READ THIS FIRST

**The hardest part of "is this lead from Facebook?" is already solved, tested and running
in production.** Do not reinvent it. It lives in the `ctm-capi-bridge` Cloudflare Worker,
whose source is committed in the repo at `ctm-capi-bridge/`.

### The files, and what each one gives you

| File | Why you care |
|---|---|
| **`ctm-capi-bridge/META-CONVERSION-TRACKING-REFERENCE.md`** | **Start here.** The whole conversion model, proven by live test 2026-08-13 — what fires a `Lead`, the `fbclid` → `_fbc` → ad/adset/campaign chain, why firing ≠ attributing, and a table of known issues. Also mirrored on Haley's Mac at `01 Clients/Roofing Force/11 Tracking & Attribution/RF-Meta-Conversion-Tracking-REFERENCE.md`. |
| **`ctm-capi-bridge/src/worker.js`** | The actual logic. **`shouldSend()` (~line 269) is the production definition of "this is a Facebook call."** `normalizeCall()` (~line 115) shows exactly which CTM payload fields exist and what they are called. |
| **`ctm-capi-bridge/wrangler.toml`** | All the tunable config, heavily commented — `FB_NUMBERS`, `FB_SOURCE_REGEX`, the talk-time bars and the reasoning behind them, business hours, voicemail rules. |
| **`ctm-capi-bridge/README.md`** | Token, deploy, secrets, CTM webhook setup, DEBUG mode, how to re-test. **Read before touching the worker.** |
| **`ctm-capi-bridge/test/run-tests.mjs`** | Existing test cases — the fixtures double as documented example CTM payloads. |

### The attribution rule you can lift directly

`shouldSend()` treats a call as Facebook-attributed if **any one** of four independent
signals matches:

1. **Dialed number** is in `FB_NUMBERS` — currently `913-565-4470` (normalized, so format
   doesn't matter).
2. CTM `source` matches `/facebook|meta|fb/i` — e.g. `"Facebook Ads Website"`
3. CTM `web_source` matches — the channel, e.g. `"facebook"`
4. CTM `paid.source` matches — CTM's own paid-traffic attribution, which it nests under
   `paid: { source: "facebook", ... }`

That four-signal test is what the sheet's attribution should agree with. **If the ledger
and the worker disagree about whether a call was Facebook, that is a bug, not a judgement
call** — and the worker is the one that has been verified live.

### Quality bars already encoded (relevant to grading)

The worker also decides whether a call is *qualified*, which overlaps with what the Call
Grades tab does:

- **Talk-time floor splits on business hours** — 20s during 8am–5pm Central Mon–Fri, 40s
  outside. Not arbitrary: the CTM number forwards to Roofing Force's own line, so their
  voicemail sits *downstream* of CTM and a machine answering is byte-identical to a human
  answering in the payload. The outgoing greeting runs ~27s, so a beep-and-hangup reads as
  28–30s while a real 13s message reads as 40s. A single threshold cannot separate them —
  hence the clock split. **If the greeting changes, `MIN_DURATION_SEC_CLOSED` = greeting + 13.**
- **Voicemails count as leads** when the message itself (duration minus ring time) is
  ≥ 10s.
- Holidays are **not** modelled — those days get judged as if staffed.

Worth deciding with Haley: should the sheet's grading reuse these same bars, or is the
grader's own standard different on purpose? Two different definitions of "qualified call"
in one system is precisely the ambiguity that caused the 2026-08-07 escalation.

### Other useful facts from the worker

- **`event_id` = `ctm-<CTM call id>`** — calls DO have a dedupe key. It is only the
  browser-side form `Lead` that has none.
- Events are sent with `action_source: "phone_call"`, `lead_event_source:
  "CallTrackingMetrics"`, and `lead_source` set to the CTM source.
- The CTM webhook fires at **end of call**, to
  `https://ctm-capi-bridge.eaveside.workers.dev/hook/<WEBHOOK_SECRET>`.
- Deploy is **manual Wrangler CLI**, not Git-connected. Committing the source did not make
  it auto-deploy — if you change the worker you must `npx wrangler deploy` and tell Haley.
- CTM's own Meta integration is **dead** — it posts to the Offline Conversions API, removed
  at v17, returning HTTP 400 `(#21018)` on every send. The worker replaced it. The offline
  event set `1070553458860276` still shows AUTO-checked on the ads; harmless, nothing writes
  to it. **Do not try to revive that path.**

## What is NOT verified — check, do not trust

The session that wrote this prompt did **not** read the Apps Script projects or the
Marketing Metrics tab internals. Everything in the previous section is from
`clients.json`, `SOURCE-MAP.md`'s header, and a live tab listing. Specifically unknown:

- Whether the `Call Tracking` grader already picks up **(913) 565-4470** (the Facebook
  number) or filters to an explicit list of the Google/market numbers.
- How a row in `Leads` gets its source attributed today, and whether "Facebook" is even a
  value that column can hold.
- Whether `Conversion Config` is the right place to register a new source.
- What writes `Attribution Ledger`, and on what schedule.

## The three sub-problems (they are in different states)

**1. Facebook calls — closest to working.**
(913) 565-4470 is a CTM tracking number, so those calls are already in
CallTrackingMetrics like any other, and the four-signal attribution rule above is already
proven in production. The identification problem is **solved**; the open question is
purely whether the Apps Script grader and the `Attribution Ledger` see those calls and tag
them Facebook, or whether they filter to an explicit list of the Google/market numbers
that predates 565-4470. Check that first — it may be a one-line fix.

**2. Facebook form leads — blocked by a pre-existing break.**
`Web Leads (auto)` is **empty** and the Formidable reconciler is **inert**
(`FR_FIELD_MAP` is all null). The ledger showed **9** web leads for a window where Meta
recorded **74**. Facebook form fills go through the same website forms as everything
else, so they fall in the same hole. **You will likely have to fix the web-lead pipeline
before Facebook form leads can work at all** — that is a bigger job than "add Meta", and
Haley should be told that explicitly and early rather than discovering it mid-build.

**3. Source attribution — may not exist.**
Even once rows exist, something has to mark them Facebook vs Google vs LSA vs direct.
For Facebook the honest signal is the `fbclid` → `_fbc` cookie (see the reference doc),
which is what Meta itself uses. Whether any of that reaches the sheet today is unknown.

## Known landmines

- **Firing ≠ attributing.** The Meta pixel's raw `Lead` total mixes all-source website
  form fills with Facebook-only calls. Never report it as Facebook performance. Read
  `ctm-capi-bridge/META-CONVERSION-TRACKING-REFERENCE.md` first — everything in it was
  proven by live test on 2026-08-13, not inferred.
- **Meta `Lead` events carry no `event_id`**, so no deduplication is possible today. If
  you add a server-side copy of the form Lead, it **must** carry a shared `event_id` or
  every lead double-counts.
- **Ambiguous lead definitions have burned this estate before.** The 2026-08-07
  escalation came from LSA "charged" vs "total" leads differing by ~25% under one
  heading. Every figure must state its definition.
- **Do not reverse the Calls-from-ads demotion (2026-07-31)** — marked CLOSED, it was
  correct. See `gads-report/basis_notes.py` for why.
- **The hardcoded phone numbers on the noindex market landing pages are intentional** —
  do not re-flag.
- **`14AWd...` Internal Master is the primary Change Log.** The GADS sheet's Change Log
  tab is **frozen history and takes no new rows.**

## First deliverable — findings, not code

Haley asked for scoping before building. Produce a short findings memo covering:

1. What the Google Ads / LSA lead path actually is, end to end: origin → transport →
   destination tab → what reads it. (`SOURCE-MAP.md`'s format is exactly this — reuse it.)
2. Which parts of that path are source-agnostic and would take Facebook leads with only
   config, versus which are hardcoded to Google/LSA.
3. Whether the call grader already sees (913) 565-4470.
4. An honest assessment of whether the `Web Leads (auto)` / `FR_FIELD_MAP` break has to
   be fixed first, and how big that is.
5. A recommended approach with the tradeoff stated, for Haley to choose from.

**Put the approach to Haley with a recommendation before building.** She will have a
view, she dislikes forked per-client code, and she prefers being told the expensive truth
early over a surprise later.

## IDs you will need

| Thing | Value |
|---|---|
| Marketing Metrics workbook (MM, the engine) | `1Eguf8HwR0wU9Q-DO_JF5ctDCebparkw3BgyvDMiYoLc` |
| Internal Master (Change Log, Fix Queue) | `14AWd_L3XQJehp-Grx0_-Tu9U0OpF8qHUlnY1GKYkpNE` |
| Daily Lead Audit (DLA) | `19-hZ_E17SXPdbrDVrRy4-vKrNQdt1xiZVGgwKx-H23Y` |
| Roofing Force GADS (Negatives Log live, Change Log FROZEN) | `16JYQWW_M9gD9VZqtdaJ1DROXVXnrAMIanbWaG3OAI0I` |
| CallTrackingMetrics account | `425821` |
| CTM number — **Facebook ads** | **(913) 565-4470** |
| CTM number — organic FB page only | (913) 298-6116 |
| CTM number — non-Facebook header/footer | (913) 270-5440 |
| CTM master forward | (913) 393-3008 |
| Google Ads conversion action | `6481109006` Call Tracking Lead |
| Meta ad account | `1779635922176764` |
| Meta pixel / dataset | `1110006736001318` |
| Meta campaign | `RF \| Leads \| 2026-08 Launch 01` |
| Google Ads MCC / RF account | `968-076-3943` / `329-848-8566` |
| Discord channel | `#roofing-force`, id `1532909401525059727` |
| Cloudflare account (worker) | Haleysknapp@gmail.com, `a8cda316b210cae5c6051ad6051ccc44` |

## Standing rules (these are law)

- **Never change budgets, bids, campaign status, or ads without Haley in the loop.**
- **Push every change to GitHub** (`bash push.sh`). An unpushed change does not exist.
  `push.sh` now has a guard that fails if `gads-report/` and `mktg-bot/gads-report/`
  diverge — `bash push.sh --sync` fixes it. **`mktg-bot/gads-report/` is the tree the Mac
  bot actually executes.**
- **Client emails are always Gmail DRAFTS, never sent.**
- **Discord reaction protocol is law:** 👀 seen/working · ✅ done · ⚠️ failed (with a reply
  saying why). Never process a human message that already carries one of these.
- **Never write a secret value into any spreadsheet.** Credential rows name the file and
  its location only.
- **Log your work** in the Change Log tab of the Internal Master. Columns: Date |
  Campaign | Change Type | Detail | Reason | Owner | Result. Newest at the bottom. Be
  exhaustive and literal — future sessions rely on it.
- Rows marked **"CLOSED — do not re-open"** or **"Do NOT re-flag"** are exactly that.

## Practical notes on the environment

- `device_bash` on Haley's Mac **has no network** and **cannot delete files**. Every git
  command it runs leaves a `.git/*.lock` that blocks the next one; rename them into a
  subfolder rather than trying to delete. Do network work in the cloud container, or hand
  Haley the commands.
- The repo is at
  `Roofing Agency/03 Eaveside Product/automation/eavesidemktg-automation/`. **Find it,
  don't hardcode it** — `CLAUDE.md` at the Roofing Agency root is the authoritative
  folder map and Haley reorganizes the tree.
- Reading Apps Script projects requires the browser (claude-in-chrome) — they are not on
  disk. Check Chrome is available before planning around it.
