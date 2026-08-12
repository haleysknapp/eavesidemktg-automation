# SOURCE-MAP — Roofing Force data lineage

**The answer to "where does this number come from?" for every number in the system.**

Written 2026-08-10 by the context-consolidation session, from ten input sources (eight session
dumps, six Cowork artifacts, the legacy `_device-transfer` memory folder, this repo's code, the
live Apps Script projects, all 86 spreadsheet tabs, the Google Ads + Local Services APIs, the
scheduled-task list, and Gmail).

Canon rule: **this repo (SYSTEM.md, clients.json, SOURCE-MAP.md) and the RF GADS sheet's
Change Log tab are the only authoritative sources.** Session dumps are archived input.
*(Change Log primary moved to `IM!Change Log` on 2026-08-10; the GADS tab is frozen history.)*

> **START HERE → [TAB REGISTER](#tab-register--what-every-tab-is-and-what-it-rests-on).** One row per
> tab across all four workbooks: what it answers, what it is built on, whether each number is
> **MEASURED or ASSUMED**, its `n`, and whether it is safe to put in front of the client today.
> Read it before re-deriving anything. Where §7a and §13 below still describe `_ClosedLoop`'s
> ~9% match rate, the register supersedes them — `Attribution Ledger` is the current answer.

## How to read a row

| Field | Meaning |
|---|---|
| ORIGIN | Where the data is actually born — a platform, an API, or a human typing |
| TRANSPORT | What moves it, whether it is automated, on what schedule, and run by what |
| DESTINATION | Exact spreadsheet ID + tab (+ columns where it matters) |
| CONSUMERS | Which reports, formulas, or bots read it downstream |
| RECIPIENTS | Who ultimately sees it |
| VERIFIED | ✅ checked live this session (method stated) · ⚠️ partly · ❌ not checked |
| STATUS | healthy · stale · broken · being replaced |

**Spreadsheet shorthand used throughout:**

- **MM** = Marketing Metrics — `1Eguf8HwR0wU9Q-DO_JF5ctDCebparkw3BgyvDMiYoLc` (61 tabs, the engine)
- **DLA** = Daily Lead Audit — `19-hZ_E17SXPdbrDVrRy4-vKrNQdt1xiZVGgwKx-H23Y` (19 tabs)
- **GADS** = Roofing Force GADS — `16JYQWW_M9gD9VZqtdaJ1DROXVXnrAMIanbWaG3OAI0I` (6 tabs, Change Log lives here)
- **IM** = Roofing Force (Internal Master) — `14AWd_L3XQJehp-Grx0_-Tu9U0OpF8qHUlnY1GKYkpNE` (new, empty, ops-only — see SHEETS-PLAN.md)

---

## 1. The system in one paragraph

Six platforms produce Roofing Force data: Google Ads, Google Local Services (LSA), CallTrackingMetrics,
the roofingforce.com website, AccuLynx, and Google Search Console. **Two Apps Script projects** — split
across two different Google accounts — move most of it into the Marketing Metrics sheet on daily timers.
**One Python repo** (this one) never touches a spreadsheet at all: it pulls the ad APIs directly and
posts to Discord and Gmail. **Four cloud scheduled tasks** run that Python on a calendar. Everything
else — LSA lead pastes, the Change Log, the August Scale Tracker actuals, GSC, the geo export — is a
human with a keyboard.

The single most important structural fact, and the one that has caused the most confusion across
sessions: **the repo's Python and the sheets' Apps Script are two entirely separate systems that share
no data.** The reports Haley emails and the numbers in the sheet are computed independently from the
same platforms. When they disagree it is almost always a date-window or definitional difference, not a
bug — see §6.

---

## TAB REGISTER — what every tab is, and what it rests on

**Read this before re-deriving anything.** One row per tab that matters, across all four live
workbooks plus the two being retired. Built 2026-08-11.

The column that does the work is **MEASURED or ASSUMED**. *MEASURED* = observed from a platform API,
a CRM feed, or a logged event. *ASSUMED* = a number a human typed. Where a figure is assumed the row
gives `n` and the date it was set. A tab can be structurally perfect and still be un-quotable because
one assumption is buried in it — `Pacing!C11` is the whole reason this column exists.

A live mirror of this register is the **`Source Map`** tab of Internal Master
`14AWd_L3XQJehp-Grx0_-Tu9U0OpF8qHUlnY1GKYkpNE`. Update both in the same sitting or they drift.

Legend — **Refresh:** `auto` = formula or script, no human in the loop · `human` = someone must act
or the number is wrong. **Confidence** describes *the numbers the tab prints*, not the quality of its
plumbing. **Trust for client-facing** is the only column that answers "can I put this in front of
Chad, Rick or George today."

### A. Marketing Metrics — `1Eguf8HwR0wU9Q-DO_JF5ctDCebparkw3BgyvDMiYoLc` (the engine)

| Tab | What it answers | Built on (exact source tabs/APIs) | MEASURED or ASSUMED | Sample size / window | Confidence | Refresh | Trust for client-facing? | Known caveat |
|---|---|---|---|---|---|---|---|---|
| **`Leads`** | Every lead the system captured, one row each. The spine everything joins to. | CTM webhook (`RF-webhook-receiver.gs`) · `RF-LSA-sync.gs` · `RF-web-lead-receiver.gs` · RF Chat Leads. Key cols: `B` date · `AE` `channel_rollup` ladder · `AF` phone key (last 10) · `T` job_value | **MEASURED** — logged events. But incomplete, and the incompleteness is invisible in every count built on it. | 1,427 rows all-time. **232 rows carry no date at all.** `AE = Google Ads` = 70 rows all-time, min date 2026-08-04 | HIGH per row · **LOW as a total** | auto (event + daily) | **NO** as a paid-lead count. Ledger intake is ~10–20% of platform reality — a FLOOR, never a total | 232 blank dates = a legacy `WEB-001`–`WEB-230` import with no date column (**unrecoverable — exclude from every windowed count**) plus a live CTM drip on `CALL-`/`CHAT-` rows. `T` job_value is written by **nothing** (55 of 919 rows) |
| **`Attribution Ledger`** (NEW) | Where each lead came from, what it became, what it was worth — the current best answer to attribution. | `Leads` (1,427 rows) + `Call Grades` orphans (372 calls whose phone is absent from `Leads`, deduped to earliest per phone) + `AccuLynx Jobs (auto)` for revenue. 100% formulas, no Apps Script | **MEASURED.** Every rung of the D0–D7 cascade is an observed signal — gclid/gbraid, utm, CTM tracking number, LSA charged flag, `Call Grades` CTM source, web sub_source. **No typed rate anywhere in it.** | 1,799-row spine. **76 jobs / $1,097,355 credited** vs `_ClosedLoop`'s 72 / $1,018,659. Revenue **FROZEN at 2026-08-08** | HIGH on mechanism · MED overall until the two open items below clear | auto | Yes for match-rate and channel-mix statements **with the window stated**. **Not yet for Organic revenue** | Match rate **23.1% count / 16.7% dollars** on a fair denominator (9.9% / 7.0% naive). Revenue is frozen because AccuLynx is dry — **repoint the `jsrc` LET binding in `A25` at EaveSide to revive it.** ⚠️ **TWO ITEMS NOT VERIFIED — treat as LOW confidence:** (1) Organic shows **95 of 104 leads matched (91%)**, implausibly high against GA 49% / LSA 24%, and **$443,622 rides on it**; (2) **`DROP - LSA not charged` carries $62,795 of credit despite its own DROP label** |
| **`_ClosedLoop`** | The legacy answer to "which won jobs came from which channel?" | Three spilled array formulas: `AccuLynx Jobs (auto)` phone_norm → `Leads!AF` XLOOKUP → `Leads!AE` | MEASURED mechanism — **coverage is the defect, not the method** | 72 jobs / $1,018,659 matched | **LOW** | auto (live formulas) | **NO** | **A single exact-phone XLOOKUP with no fallback of any kind** — it never consults `Call Grades` or `LSA Leads (auto)`. **Superseded by `Attribution Ledger`**, which credits 76 / $1,097,355 off the same raw data. Retire only on Haley's say-so |
| **`Pacing`** | Unit economics per channel → the CPL ceilings and tCPA targets bids are actually set from. | `B10` = VLOOKUP `AccuLynx Native` · `B12` = VLOOKUP `Attribution Jan26+` · `B11`/`C10`/`C11`/`C12`/`B6` typed · `B4` 2025 P&L · `B5` Eaveside spend policy | **MIXED — and this is the tab where it matters most.** `B11` GA avg job $13,162 = MEASURED · `C10` LSA close 9.35% = MEASURED · **`C11` GA close 8.9% = ASSUMED** · `B4` 27% margin and `B5` 50% ceiling = **ASSUMED (decisions, typed on purpose)** | `B11` **n=1,212** won Google/Organic jobs (EaveSide, all-time) · `C10` **n=353** · **`C11` n=0** · `B10` n=25 · `B12` n=17 · `B4` set **2026-01-31** · `B5` set **2026-06-01** | MED on `B11`/`C10` · **none on `C11`** | human for the typed cells · auto for `B10`/`B12` | Only with the basis stated per figure. **Never quote GA close % as measured** | `B11` was a **TYPED PLACEHOLDER with n=0** until 2026-08-11; it is now $13,162 but that is a **paid+organic BLEND** (Google Ads alone is n=1, and that one record is almost certainly not RF). **`C11` is STILL an assumption and is not estimable** — 411 platform conversions YTD against 1 matched won job. `B10`/`B12` are **live formulas mis-coloured yellow**, the colour this tab reserves for typed inputs; anyone following the fill and typing over them destroys a feed. Robust fallback for any channel figure too thin to quote: **company-wide avg job $16,158, n=5,678, 95% CI $15,436–$16,881** |
| **`Economics`** | Last-30-days CPL, cost per close and modelled ROAS by channel. | `_SpendLive` K (GA spend) / L (GA leads) / G (LSA spend) · `LSA Leads (auto)` · `Leads` · **cols E and G are live references to `Pacing`**: E4=`Pacing!C11`, G4=`Pacing!B11`, E5=`Pacing!C10`, G5=`Pacing!B10`, E6=`Pacing!C12`, G6=`Pacing!B12` | Cols B/C/D/I = **MEASURED**, platform ÷ platform. Cols F/H/J (Est. Closes, Est. Revenue, ROAS) = **MODELED — they inherit every `Pacing` assumption, including the n=0 GA close rate.** Cols K/L read $0 and are **NOT a fact** | rolling `TODAY()-30` → end of the spend feed | HIGH on CPL · **LOW on modelled ROAS** | auto | CPL yes, with the window. **Modelled ROAS no** | **Checked cell-by-cell 2026-08-11: `E4:G6` contain NO hardcoded duplicate — they were already `Pacing` references, so the Pacing corrections flowed through and the two tabs agree.** Backup `Economics BACKUP 2026-08-11b`; a dependency note now sits in `A11`. Col C's SUMIFS has no upper bound and `_SpendLive` lags a day, so the newest ~2 weeks of CPL are provisional |
| **`ROI`** | Modelled return on ad spend on a gross-margin basis. | `leads × close-rate × avg job value × 27% margin`. Leads/spend from `_SpendLive`; close %, avg job, margin all from `Pacing` | **ASSUMED at its core.** It is arithmetic on `Pacing`'s typed rates — **it is NOT attribution** | inherits `Pacing`: n=0 on the GA close rate | **LOW** | auto | **NO. Never quote as measured** | **It prints a ROAS regardless of match quality** — the number exists whether or not a single job was ever matched to a lead. This is the tab most likely to be mistaken for a result |
| **`ROI & Revenue`** | Contract $ against spend over monthly / 90d trends. | `_ClosedLoop` matched revenue + `_SpendLive` | MEASURED but on `_ClosedLoop`'s coverage | 90d and monthly windows | LOW | auto | **NO** while it reads `_ClosedLoop` | Its own instruction is right — read the monthly trend and 90d, never 30d in isolation, because roofing closes over 30–90+ days. Repoint at `Attribution Ledger` |
| **`Overview`** | The ledger-basis pulse: L7 / MTD leads, CPL, contract $. | `Leads` (`AE` channel_rollup, `B` date) + `_SpendLive` | MEASURED, **[L] ledger basis** | L7 / L30 / MTD | MED on lead counts · **broken on Contract $** | auto | Only if labelled ledger-basis. It will **not** agree with `Exec Summary`/`Daily`/`Performance` and that is expected | **Contract $ reads `Leads!T` job_value, which NOTHING writes (55 of 919 rows) — that is why it shows $0.** Its "Last 7 days" is an **8-day window** while `Exec Summary` and `Daily` use 7. Two tabs, same label, different arithmetic |
| **`Exec Summary`** | Live current-period pulse — the fastest read in the book. | `_SpendLive` col L (GA API conversions) + `LSA Leads (auto)` charged, DECLINED excluded | **MEASURED**, [P] platform-counted throughout | L7 = `TODAY()-6`→today · L14 · MTD | HIGH | auto | Yes, **with the window and the basis on the figure** | **The $199 CPL is BLENDED GA+LSA, not Google Ads.** Quoting it as a Google Ads CPL is the Aug 7 escalation repeating |
| **`Daily`** | One row per day for 45 days, platform basis. | `_SpendLive` K/L + `LSA Leads (auto)` excl. DECLINED | **MEASURED**, [P] | last 45 days, `A4` = today | HIGH | auto | Yes | `_SpendLive` writes a day in arrears so today's row reads 0; Google Ads restates conversions upward for ~14 days while `_SpendLive` stores a one-time snapshot, so **the newest ~2 weeks read LOW** |
| **`Performance`** | Whole-calendar-month paid performance. **The reconciliation anchor.** | `_SpendLive` K/L + `LSA Leads (auto)` excl. DECLINED | **MEASURED**, [P] | whole calendar months; last row is MTD | HIGH | auto | **Yes — this is the tab that matches the client report** | Current month understates (feed lag + conversion restatement). `Exec Summary` and `Daily` must agree with this tab; `Overview` and `KPI Scorecard` are ledger-basis and will not — expected, not an error |
| **`Monthly`** | 2026 vs 2025 by month. | ledger (Jul onward) + maintained totals (Jan–Jun) + a fixed 2025 baseline | **MIXED** — Jul+ measured, Jan–Jun are maintained totals, 2025 is frozen history | monthly, 13 months | MED | part auto, part human | With the basis stated per period | Jan–Jun 2026 are **maintained totals**, not live counts. Do not treat the whole series as one basis |
| **`Paid Performance`** | Paid by channel and market over a rolling window. | `_SpendLive` + `LSA Leads (auto)` + market split | MEASURED | rolling 30 days (cell-driven) | MED | auto | Yes for leads and spend; **no market-level revenue exists anywhere** | There is **no campaign-level or market-level P&L in the estate** — this is the closest thing and it carries no revenue |
| **`KPI Scorecard`** | Ledger-basis scorecard, last 7 / 30 days. | `Leads` spine, `AE` channel_rollup | MEASURED, **[L] ledger basis** | `TODAY()-N` → today | MED | auto | Only if labelled ledger-basis | Same floor problem as `Leads`. Will not reconcile to `Performance` by design |
| **`Weekly Cohorts`** | Leads, spend, CPL and revenue per acquisition week, newest first. | `_SpendLive` K/L · `LSA Leads (auto)` · `_ClosedLoop` for revenue · `Pacing!B4` for the 27% margin | Spend/leads/CPL = **MEASURED [P]**. Revenue/ROAS = MEASURED but on `_ClosedLoop` coverage. Gross profit = **ASSUMED 27%** | weekly from June 2026; a new row appears every Monday | HIGH on the left half · LOW on revenue | auto | Leads/spend/CPL yes. **Revenue no** | **Cohort revenue is filed to the week the LEAD arrived, not the week the job closed — so later cohorts filling in over time is CORRECT AND EXPECTED, not a defect. Do not re-open this.** A `$0` in cols E/J means "no revenue we can attribute", never "no revenue". **Col R shows unattributed closed dollars only** — read cols Q and R before quoting any $0 |
| **`Dashboard`** | Attribution summary: leads / new / repeat / won / revenue by channel. | `Leads!AE` live + `Attribution Jan26+` for won and revenue | MEASURED, on `Attribution Jan26+` coverage | all-time | LOW–MED | part auto, part human | **NO** | Only ~$626K of $3.97M won is marketing-matched; the rest is referral / repeat / organic. Organic row = Organic+Direct combined |
| **`Lead Command`** | The paid-lead working queue with call grades and next steps. | `Leads` + `Call Grades`, written by the daily job | MEASURED | L7 / L30 snapshot | MED | **human-triggered snapshot** | Internal only | **STATIC SNAPSHOT, NOT LIVE** — rows 3–7 are typed values written Aug 10 08:58; they do not move when you open the sheet. The per-row `Next step` column is **blank on essentially every row**, so it gives a count, not a worklist |
| **`All Leads`** | Every lead, all channels, newest first. | `Leads` ledger | MEASURED | all-time | MED | auto | Internal only | Inherits every `Leads` gap, including the 232 undated rows |
| **`Call Grades`** | Every graded call: transcript-derived grade, CTM source, next step. | CTM recordings → Deepgram → Claude, `Eaveside-Call-Grader.gs` (eaveside account, daily 06:10) | **MEASURED** | **542 rows, 538 with a blank `leads_row`** | HIGH on the grades | auto (12 calls per run) | Internal + LSA dispute filings | **The richest untapped source in the estate — now consumed by `Attribution Ledger`** as the 372-call orphan block. Only 4 of 542 rows ever linked back to `Leads` on their own. Grader throughput caps at 12 calls per run so it lags a backlog |
| **`Call Intelligence Findings`** | The written diagnosis from the call corpus. | `Call Grades` | analysis, not a feed | as at its write date | MED | human | Internal | A point-in-time document. It does not update when the grades do |
| **`AccuLynx Jobs (auto)`** | Won jobs and their `salesAmount`. **The only source of contract dollars.** | `RF_masterDaily` in `RF-acculynx-master.gs.gs`, daily ~05:30 | **MEASURED** | **3,252 rows · max createdDate 2026-08-08 · DRY** | HIGH on what is in it | auto (daily) | Revenue yes, **once it is flowing again** | **DRY.** The sync upserts by ModifiedDate so **old jobs DO refresh** — but `salesAmount` is only re-read when the milestone string changes, so **change orders are missed**, and **a failed API call returns 0 indistinguishably from a real $0**. Migration-bound: rebuild against EaveSide |
| **`AccuLynx Native`** | Won-job rollup by AccuLynx's own source tag. | `alnSyncNativeDaily`, `GET /jobs/{id}/payments/overview`, daily ~07:00 | MEASURED, but on a **self-reported CRM dropdown** | 875 won jobs / $18.99M | MED | auto | With the caveat stated | Its own header warns: **"Google/Web Search mixes organic + Google Ads + GBP"** — $3.03M of won revenue sits in that undifferentiated bucket. This is why Google Ads avg job is not estimable |
| **`AccuLynx Native Raw`** | Raw payload behind the rollup. | same sync | MEASURED | `lastSynced` **2026-06-18** | LOW | auto (but not landing) | **NO** | **54 days stale** |
| **`_SpendLive`** | Daily spend and Google Ads conversions. **The most-read tab in the estate.** | `DLA!Overall` cols K/L → one spilled `IMPORTRANGE`, fed by `RF-ads-spend-sync.js` (a Google Ads **Script** in the MCC UI, daily 8–9am) | **MEASURED** — matches the Google Ads API **to the cent on the GA column across 64 days** | daily, last row a day in arrears | HIGH | auto (daily) | Yes | **Column C is TOTAL (GA + LSA). Column K = Google Ads. Column G = LSA. Column L = GA leads.** The tab has **no header row** (A1 is the spilling IMPORTRANGE), so the column key sits off to the right at `N1:O12` — a careless read of col C is still easy. Known bad cells: $79.15 phantom on 2026-07-27 (already in a client PDF), $86.08 LSA double-count on 07-11/12. Total drift $165 on $22.7k = 0.7%, **all of it in the LSA column** |
| **`LSA Leads (auto)`** | Every LSA lead, charged flag included. | LSA Lead Inbox → `RF-LSA-puller.gs` / `RF-LSA-sync.gs` | **MEASURED** | 4,734 rows, max date 2026-08-09 | HIGH on rows · MED on the count definition | auto (daily) | Yes — **but state ALL vs CHARGED every time** | The feed silently drops `DECLINED` leads Google still billed for (a real 4-lead undercount Jun 8 – Aug 2). `RF-LSA-sync.gs` lines 50–54 do `created.slice(0,10)` on a JS Date string and lose the year — **the date bug is FIXED and VERIFIED as of 2026-08-10** (`IM!Fix Queue`) |
| **`Web Leads (auto)`** | Website form submissions. | Bricks native form → `rf-lead-router.php` → `RF-web-lead-receiver.gs` | MEASURED | live | MED | auto (event) | Internal | **Double-count risk with the legacy Formidable path** — both can be live and there is no dedup. No test submission has ever been pushed through either path |
| **`Chatbot (auto)`** | Roofers Guide chat leads. | `RF Chat Leads` Apps Script — **0 triggers** | MEASURED, but dormant | 13 rows | LOW | **dead** | **NO** | Effectively frozen. Decide: wire it up or retire it |
| **`Feed Health`** (NEW) | "Did every feed actually land?" — freshness and STALE flags per feed. | live formulas over `AccuLynx Jobs (auto)`, `_SpendLive`, `LSA Leads (auto)`, `Leads`, `Call Grades`. No script | **MEASURED** | recomputes on open | HIGH | auto | Internal | **Exists because nothing else in the workbook throws an error when a feed stops — revenue and ROAS silently go to $0 and read like a business result.** "Days since" uses the latest DATA date, not the last script run, so a script that runs clean but writes nothing still shows STALE. That is the point |
| **`Attribution Jan26+`** | Won jobs attributed to their best tracked touchpoint, Jan 2026 onward. | `AccuLynx Jobs` cols AO–AT, matched on name/phone/email/address — not the AccuLynx manual tag | MEASURED | Jan 2026+ | MED | **human** — re-run the match script, re-paste, re-write AO:AT | Internal | Refresh is a manual three-step. It goes stale silently and feeds `Dashboard` and `Pacing!B12` while it does |
| **`Revenue Sources`** | Real revenue mix across every channel, last 90 days. | closed jobs matched to the person + line called | MEASURED | last 90 days | MED | auto | Internal | "If it is not a Google Ads DNI and has no gclid, it is organic/GBP/direct" — a heuristic, not a signal |
| **`Health Log`** | Sync-state heartbeat. | `RF_healthCheck`, every 3h | MEASURED | rolling | HIGH | auto | Internal | **Watches lead and call flow only — nothing watches the AccuLynx job feed.** That gap is what `Feed Health` was built to close |
| **`Lead Outcomes`** | (nothing — frozen rollup) | `RF_dailyPostCache`, daily 06:00 | — | frozen, "514 graded leads" | — | auto, pointlessly | **NO** | Frozen tab with **zero consumers**, still burning a daily trigger. Retire |
| **`_Audit`** | Live diagnostics on the `Leads` spine. | live formulas over `Leads` | MEASURED | live | MED | auto | Internal | **Contains live `#REF!` in C1, E1 and N1.** Its "future dates remaining = 0" check does **not** detect the 61 rows bumped into past dates |
| **`Source Map`** (MM) | Older per-flow lineage inside the engine workbook. | hand-written | — | as written | — | human | Internal | **Superseded by `IM!Source Map` + this register.** Leave a pointer; do not maintain two |
| **`Instructions`** | How to operate the workbook. | hand-written | — | as written | — | human | Internal | Predates the basis-key convention |
| **`Change Log`** (MM) | Change history inside the engine. | hand-written | — | — | — | human | Internal | **`IM!Change Log` is the primary copy since 2026-08-10.** Do not type new entries here |
| **`Conversion Config`**, **`Conversion Change Log`** | Which conversion actions count, and what changed. | hand-maintained | — | — | MED | human | Internal | **There is no 2026-07-31 row** — which is exactly why the demotion got re-investigated twice. A retro row now exists in the GADS Change Log. **Settled: do not re-open** |
| **`LSA Tag Log`**, **`LSA Name Recovery`** | Audit trail for LSA→CRM tagging and name repair. | `tagLsaSourceInAccuLynxScheduled()` | MEASURED | rolling | MED | auto (every 2 days) | Internal | This is the **only** automation in the estate that writes into the client's live CRM. Kill it first at cutover |
| **`GAds Recovered`**, **`GAds Tag Preview`**, **`Paid Lead Tracker`** | Working scratch for recovering Google Ads calls into the ledger. | `Call Grades` / CTM exports | MEASURED, partial | ad hoc | LOW | human | **NO** | Investigation artifacts, not feeds. Their job is now done properly by `Attribution Ledger` |
| **`St. Louis Leads`**, **`Lead Detail`**, **`Lead Notes`**, **`Initiatives`** | Per-market and per-lead working views; the initiative list. | `Leads` | MEASURED / hand-written | ad hoc | LOW–MED | human | Internal | Hand-maintained side views. None is a source |
| **`Paste-CTM`**, **`Paste-LSA`**, **`Paste-Forms`** | Legacy manual landing zones. | a human pasting a CSV | **human input** | — | — | human | **NO** | Superseded by the auto feeds and **still typeable-into**. Archive, then retire |
| **`_PerfImport`**, **`_MarketImport`** | IMPORTRANGE staging. | DLA | MEASURED | — | — | auto | n/a | Plumbing. Both must be repointed before DLA can be retired |
| **`AccuLynx Jobs`** (manual) | Frozen manual job export. | a human | — | frozen | — | human | **NO** | Retire at cutover |
| **`Source Funnel (RETIRED)`**, **`July Backfill (temp)`**, **`Sheet2`–`Sheet6`**, **`GeoTmp2`**, all `BACKUP` tabs | nothing | — | — | — | — | — | **NO** | `Source Funnel` was retired because it read `Leads!T` job_value and undercounted. The rest is cleanup. **Never delete a backup before it is archived** |

### B. Internal Master — `14AWd_L3XQJehp-Grx0_-Tu9U0OpF8qHUlnY1GKYkpNE` (Haley's ops book — INTERNAL ONLY)

| Tab | What it answers | Built on (exact source tabs/APIs) | MEASURED or ASSUMED | Sample size / window | Confidence | Refresh | Trust for client-facing? | Known caveat |
|---|---|---|---|---|---|---|---|---|
| **`Start Here`** | What this book is, the canon rule, the going-forward rule, the tab guide. | hand-written from the canon repo docs | — | built 2026-08-10 | HIGH | human | **Never — this book is internal** | Update it whenever a tab is added or a rule changes |
| **`Source Map`** | **The index.** Every tab and every data flow: what it is, what it rests on, whether it is measured or assumed. | mirrors repo `SOURCE-MAP.md` including this register | — | rebuilt 2026-08-11 | HIGH | human | Never | **Check it before re-deriving anything; update it when you change a tab.** If it and the repo doc disagree, fix both in the same sitting |
| **`Change Log`** | Every account, site or tracking change, newest last. | Haley, hand-typed, same-day rule | **human record** | ~50 entries, 2026-06-03 → 2026-08-10 | **HIGH — the healthiest artifact in the estate** | human | Never | **Primary copy since 2026-08-10**, held as STATIC values; the GADS tab is frozen history with a MOVED pointer row |
| **`Weekly Log`** | What we did for RF each week, in two lanes: internal truth vs client framing. | Haley, hand-written | human record | 5 real weeks, 7/13 → 8/10; rows pre-created to 2026-10-26 | HIGH for what is filled | **human** | The client-framing lane feeds client comms | Entirely hand-written. The Friday auto-draft (SHEETS-PLAN §3) was **never built**, so 8/17 onward will stay empty until it is |
| **`Open Items & Decisions`** | Everything waiting on a decision, with an owner and a chase date. | hand-written | human record | 16 rows | MED | human | Never | **Chase date reads "TBD — never recorded" on all 16 rows** — the one column the tab exists for. Twilio A2P blocked 76 days, GBP addresses 65, Wichita 54 |
| **`Fix Queue`** | The burn-down: what is broken, who owns it, and the evidence that closed it. | hand-written; row-2 counters are live `COUNTIF` | human record + live counters | 27+ numbered rows | HIGH | human (counter auto) | Never | Correct by construction — a row only moves to FIXED when the evidence column says how it was verified. **The LSA date bug is FIXED and VERIFIED as of 2026-08-10** |
| **`Automation Health`** | Every trigger, script and bot: owner, schedule, last run, error rate. | read from both Apps Script trigger panels + the scheduled-task list | **human snapshot** | 18 automations, verified 2026-08-10 | MED | **human — re-verify weekly** | Never | **"Last known run" is a TYPED SNAPSHOT, not a live read. It will say 2026-08-10 forever.** This tab goes stale silently |
| **`Access & Assets`** | Accounts, IDs, tracking numbers, script IDs, where credentials live. | hand-written | — | — | MED | human | Never | **Credential file names and locations only — never a secret value.** (Five scheduled-task prompts still embed nine live secrets in plaintext; that is a separate open item) |
| *(missing)* **`Work Scope Mirror`** | — | — | — | — | — | — | — | **Specified in SHEETS-PLAN §2b and never built.** Without it, internal and client-facing Work Scope status can drift silently |

### C. Marketing Playbook — `1Y7Y-phDWz_cPGmKy0MQkJERTaUX7L9v4d6_HfKk0Wrk` (CLIENT-FACING)

| Tab | What it answers | Built on (exact source tabs/APIs) | MEASURED or ASSUMED | Sample size / window | Confidence | Refresh | Trust for client-facing? | Known caveat |
|---|---|---|---|---|---|---|---|---|
| **`Overview`** | Who EaveSide is, what we run, who reads this. | hand-written | — | — | HIGH | human | **Yes** | Written to be read straight through by Chad, Rick and George |
| **`Audit`** | The day-one baseline, scored July 2026 — progress is measured against it. | RF's CRM + production database + public data | **MEASURED**, frozen on purpose | overall readiness 59.6/100, scored July 2026 | HIGH | **frozen — never update** | **Yes** | It is a baseline. If someone "refreshes" it, the whole progress narrative loses its zero point |
| **`Business Model`** | The client's goals, economics and funnel — which become our targets. | client inputs + RF's own job data | **MIXED, and it says so per row.** Year-one revenue target $8,064,000 is **MODELLED** — 41.6 jobs/mo × $16,154 benchmark, **not RF's own stated goal** | RF's 5,623 jobs / $90.8M | MED | human | **Yes, but every MODELLED / TBD row must stay labelled** | **Needs RF to confirm true gross margin, close rate and lead volume.** Until then the targets are our estimate of their business, presented to them |
| **`Work Scope`** | Every deliverable, its status, and the latest result. | hand-maintained; row-2 rollup is a live `COUNTIFS` over `$A$3:$A$187` | human record + live rollup | 287 scored items → 244 placed here. Setup 13 of 99 done · Recurring 5 of 49 · In progress 61 · Blocked 0 | HIGH | human | **Yes** | `Last done` is empty on every row read; `Cadence` and `Owner` partly blank |
| **`KPI Tracker`** | Month-by-month movement on the metrics RF cares about. | `Business Model` targets + hand-entered monthly actuals | would be MEASURED — **but there is nothing in it** | baselines only (LSA 94, Google Ads 150, Meta 0) | **LOW — empty** | **human, monthly** | **NO — it is blank** | **A correctly-wired shell with no data.** The `Latest` INDEX/MATCH formulas are right and return `""` because columns D:O (Aug 2026 → Jul 2027) are entirely empty. Aug 2026 was never filled |
| **`Weekly Log`** | What we did for RF this week, client-facing framing. | hand-mirrored from `IM!Weekly Log` | human record | **one row (2026-08-10)** | MED | human | **Yes** | No history and no automation. Mirrored by hand, so it drifts from the internal log |
| **`Access & Assets`** | Accounts and assets RF owns. | hand-written | — | 25 rows | LOW | human | **Not as-is** | **14 rows read "☐ To verify" and 7 read "TBD" in a client-facing document.** The CRM row still says **"AccuLynx"**, which the migration makes wrong |
| **`Unmapped (from Playbook Review)`** | The 43 scored items with no Work Scope home yet. | July Playbook Review, George's scores | human record | 43 of 287; 244 placed, nothing dropped | HIGH | human | Yes — it shows nothing was lost | Awaiting Haley. Mostly the in-person sales process and cash forecasting, which the standard scope carries no row for |

### D. Content Library — `10b0rzM1F0Nde8gHMa7CJK2hykGC9pzfxz3tE4uieO_c` (CLIENT-FACING)

| Tab | What it answers | Built on (exact source tabs/APIs) | MEASURED or ASSUMED | Sample size / window | Confidence | Refresh | Trust for client-facing? | Known caveat |
|---|---|---|---|---|---|---|---|---|
| **`This Week's Shoots`** | What the crew films this week, and where it is in the pipeline. | office logs each job; cols E/F/G `INDEX/MATCH` into `Job Shoot Briefs!$B$4:$B$50` | human input + live lookup | **zero job rows today** | HIGH on the mechanism | **human (by design)** | **Yes** | **Intentionally empty** — built, working, and switches on the week RF decides to start filming. Ranges are correct (the Copper Ridge hardcoded-6-rows mistake was avoided) — **do not type over E/F/G** |
| **`Job Shoot Briefs`** | For each job type, exactly what to film. | RF-specific, built from the job mix | — | 5 job types, BEFORE/DURING/AFTER shot lists | HIGH | human | **Yes** | Carries the hard compliance rules: no claim-outcome promises, no deductible talk, no financing numbers, no AI imagery, homeowner consent before a face or address is on camera |
| **`Playbook`** | The creative principles — what a cold ad has to do. | EaveSide method | — | — | HIGH | human | **Yes** | **OPEN QUESTION at the top: Haley has not decided whether RF's content program is organic social, paid creative supply, or both.** Nothing in the principles changes with that decision; only cadence and where finished pieces publish |
| **`Client Intake & Angles`** | What RF actually says about itself, and the angles that fall out of it. | Part 1 live with George/Chad + inspectors · Part 2 from the website, CTM audit and review profile · Part 3 derived | Part 1 = **client-stated** · Part 2 = **MEASURED from public sources** · Part 3 = derived | as of August 2026 | MED | human | **Yes** | Anything marked `[ASK]` or `[CONFIRM]` is still open. Every hook, script and ad downstream is only as sharp as Part 1 |
| **`Hooks`** | The hook bank, filterable by motivation / journey stage / funnel. | derived from Intake & Angles | — | populated | HIGH | human | **Yes** | Statements only, no question openers. Nothing promises a claim outcome, quotes a price, or mentions a deductible |
| **`Concepts & Scripts`** | Each video concept written out: hook, body, CTA. | `Hooks` + Intake | — | populated | HIGH | human | **Yes** | Body copy written the way an inspector talks. Swap hooks to version a winner |
| **`Ads`** | Twenty finished static ads, ready to run. | batch `2026-08-07-matrix`, rendered 4x5 / 1x1 / 9x16 | — | 20 ads, 6 starred as launch 01 | HIGH | human | **Yes** | All land on `roofingforce.com/no-obligation-roof-estimate/` with UTMs. No discounts, financing terms, claim promises or AI imagery anywhere in the set |
| **`Swipe File`** | What competitors are actually spending against RF's homeowners. | Meta Ad Library, real Ad Library IDs | **MEASURED from public data** | 3 competitors, with running-since dates and version counts | MED | **human, refresh monthly** | **Yes** | Version count is the closest public proxy for a competitor's results. **RF's own Ad Library page is empty** |

### E. Being retired — do not build anything new on these

| Tab | What it answers | Built on (exact source tabs/APIs) | MEASURED or ASSUMED | Sample size / window | Confidence | Refresh | Trust for client-facing? | Known caveat |
|---|---|---|---|---|---|---|---|---|
| **GADS `Change Log`** — `16JYQWW_M9gD9VZqtdaJ1DROXVXnrAMIanbWaG3OAI0I` | Historical change record. | Haley, hand-typed | human record | 2026-06-03 → 2026-08-10 | HIGH | **frozen** | Never | **RETIRING.** Frozen history with a MOVED pointer row at the bottom; `IM!Change Log` is primary. A retro row for the 2026-07-31 conversion demotion was added here so it stops being re-investigated |
| **GADS `Negatives Log`** | Which negative keywords were applied and when. | was written by the approval flow | human record | last entry **2026-08-03** | LOW | **nothing writes it any more** | Never | **RETIRING.** Drifting since 2026-08-07. Negatives *are* being applied — verified to the second against Google Ads `change_event` — they just are not logged here |
| **GADS `Campaign Tracker`** | Campaign-level cost and cost/conv snapshot. | hand-refreshed on each pull | MEASURED at pull time | as-of **2026-07-25** | LOW | human | **NO** | **RETIRING · 16+ days stale.** Carries no revenue, so it cannot answer "which campaigns make money" |
| **GADS `August Scale Tracker`** | Plan vs actual for the August scale-up. | plan typed; actuals were to come from `_SpendLive` + `LSA Leads (auto)` | plan = **ASSUMED** · actual = **absent** | **20 of 20 rows have empty actuals — 60 empty cells** | **LOW** | human, never done | **NO** | **RETIRING.** Wk1 (Aug 4–10) closed unreconciled: plan $8,500 / 55 leads, actual ~$4,047 / 20. The actuals are computable today; nothing joins the two workbooks |
| **GADS `St. Louis Build`**, **`Reference`** | Build notes and reference lists. | hand-written | — | — | — | human | Never | **RETIRING.** Migrate anything still true into Internal Master |
| **DLA `Overall`** — `19-hZ_E17SXPdbrDVrRy4-vKrNQdt1xiZVGgwKx-H23Y` | Daily spend and lead rollup. **Still load-bearing.** | `RF-ads-spend-sync.js` writes cols K/L | **MEASURED** | last row 8/9/2026 | HIGH | auto (daily) | Indirectly, via `_SpendLive` | **RETIRING — but `MM!_SpendLive` IMPORTRANGEs it, so DLA cannot be switched off until that is repointed.** This is the gate on the whole retirement |
| **DLA `Olathe`, `Joplin`, `Mena`, `Fort Smith`, `Wichita`, `St. Louis`** | Per-market daily spend and leads. | Ads Script + `COUNTIFS(Sheet7!$D:$D,"LSA",…)` | MEASURED for spend, **broken for LSA** | daily | LOW on the LSA columns | auto | **NO** | **RETIRING.** `Sheet7` was repurposed, so the two LSA columns return **permanent 0** on every August row |
| **DLA `AccuLynx Geo Export`** | The served footprint — 24+ months of won work by location. | `exportJobsGeo()` in `GeoExport.gs`, **no trigger, manual by design** | **MEASURED** | **7,047 real rows, 2025-01-01 → 2026-08-08** | HIGH | **human, on demand** | Feeds the geo recommendations the client sees | **RETIRING but genuinely valuable — rebuild at cutover.** Fixed 2026-08-10 and NOT reverted: old code used `&recordStartIndex=` (silently ignored → the same 25 records written 939 times = 23,475 junk rows) and read the empty `c.mailingAddress`. **Any doc still citing "23,475 AccuLynx records" is describing the bug, not a dataset** |
| **DLA `YoY Daily`, `YoY Monthly`, `Ad Performance`** | Year-over-year comparison. | Ads Script `YOY_BACKFILL` | **absent** | `YoY Daily`: 366 rows, **all $0** | **LOW** | auto, but writing nothing | **NO** | **RETIRING.** The `YOY_BACKFILL` addition was never re-pasted into the deployed Ads Script |
| **DLA `Sheet7`, `_LeadsLive`, `_YoYraw`, `_PerfRaw`, `Daily Process`, `Keyword Plan`, `Landing Page Map`, `GeoTmp`, backups** | staging and working tabs | — | — | — | — | mixed | **NO** | **RETIRING.** Note `_LSALive` **does not exist** in any workbook — the name appears in old prompts and is wrong; the nearest real tabs are `DLA!_LeadsLive` and `MM!_SpendLive` |

### Rules for any session reading this

1. **Measured or assumed, every time.** No figure leaves this system without saying which it is. If it
   is assumed, say `n` and the date it was set. "Google Ads close rate 8.9%" is not a fact; "Google Ads
   close rate 8.9%, ASSUMED, n=0, not estimable" is.
2. **Every figure carries its date window.** The entire 2026-08-07 client escalation was two *correct*
   reports with invisible windows. Also state ALL vs CHARGED on every LSA figure — they differ ~25%.
3. **Never divide platform spend by ledger leads.** `[P] ÷ [L]` is a basis mismatch, not a CPL. It is
   what printed $665 against a true platform CPL of ~$156. `[P] ÷ [P]` or `[L] ÷ [L]`, never crossed.
4. **One tie-break rule: earliest job wins, and multi-matches get flagged.** When a lead matches more
   than one job, credit the earliest and flag the row. Do not silently pick the largest.
5. **Do not re-open the settled.** These have each cost a session an hour or more already:
   - the **2026-07-31 demotion** of `Calls from ads` Primary → Secondary was **correct**;
   - the **hardcoded LP phone numbers** are **intentional**;
   - **pre-tracking attribution gaps** (before 2026-07-23) are unattributable **by design** — no Google
     Ads DNI numbers existed. Never re-investigate them;
   - **cohort maturation** on `Weekly Cohorts` — later cohorts filling in over time is **correct and
     expected**, not a defect.
6. **Attribution eras — stamp every attribution question with one:**
   | Era | Window | What it means |
   |---|---|---|
   | **PRE-TRACKING** | before 2026-07-23 | No Google Ads DNI numbers existed. **Unattributable BY DESIGN. Never re-investigate.** |
   | **PARTIAL** | 2026-07-23 → 2026-08-02 | DNI numbers live, CTM labelling not yet reliable. Directional only |
   | **TRACKED** | 2026-08-03 onward | CTM labels Google Ads reliably. The only era attribution questions are fair game in |
7. **When you change a tab, update this register and its live mirror in `IM!Source Map` in the same
   sitting.** That is the whole point of it existing.

---

## 2. Google Ads

| | |
|---|---|
| **ORIGIN** | Google Ads API, customer `329-848-8566` (`3298488566`) under MCC `968-076-3943` |
| **TRANSPORT** | `gads-report/config.py` builds the client from `.env`; `daily_report.py`, `weekly_terms.py`, `weekly_exec.py`, `monthly_exec.py` each run their own GAQL. **Automated** via four cloud scheduled tasks (§8). Separately, a Google Ads **Script** (`RF-ads-spend-sync.js`, installed in the MCC UI, daily 8–9am) writes spend to the sheets — this is *not* in the repo. |
| **DESTINATION** | Repo path: nothing persisted — reports render straight to `out/*.html` and Discord. Sheet path: `DLA!Overall` cols K/L + per-market tabs col F → `MM!_SpendLive` via a single spilled `IMPORTRANGE(…,"Overall!A2:L1000")` |
| **CONSUMERS** | `MM` Dashboard, KPI Scorecard, Paid Performance, Economics, Daily, Monthly, ROI, 8-Week Cohorts all read `_SpendLive`. Repo reports consume nothing downstream. |
| **RECIPIENTS** | Discord `#roofing-force` (channel `1532909401525059727`); Chad Burnett, Rick Davis, George Davis via Gmail draft; Haley |
| **VERIFIED** | ✅ **Live API pull this session.** Queried `segments.date BETWEEN '2026-06-08' AND '2026-08-09'` for cost/conversions/clicks by campaign and compared day-by-day against `_SpendLive`. The Google Ads portion of every daily row matches the API **to the cent** across 64 days. |
| **STATUS** | **healthy** on the API side. `_SpendLive` has two confirmed defects (§6). |

**Gotcha for any future session:** `DURING LAST_90_DAYS` is **not valid** in the API version in use.
Use explicit `segments.date BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'` ranges.

**Enabled campaigns** (verified via API this session): Kansas City `22284561281`, St. Louis
`14592215201`, Fort Smith `22307503910`, Joplin `22311207505`, Mena `22311255805`.
Paused: Wichita `23799169822`.

### 2a. Conversion actions

| | |
|---|---|
| **ORIGIN** | CTM Direct Connect → Google Ads conversion action `6481109006 Call Tracking Lead`; plus Google-native `Calls from ads` |
| **TRANSPORT** | Platform-to-platform integration, no code of ours |
| **VERIFIED** | ✅ pulled by conversion action from the API |
| **STATUS** | ⚠️ **needs an audit.** `Call Tracking Lead` ramped 2026-07-20 while native `Calls from ads` was still firing 10–11/week; `Calls from ads` only drops to 0.0 from 2026-08-03. **If the call-extension number forwards to the tracked number, Jul 20 – Aug 2 double-counts the same calls** — and those are the weeks the client-facing ROAS rests on. Open item. |

**Settled, do not re-litigate:** the 2026-07-31 demotion of `Calls from ads` from Primary to
Secondary was **correct**. Two separate sessions re-investigated it because there is no 2026-07-31
row in the `Conversion Change Log` tab. The May–July zeros in `Call Tracking Lead` are the
2026-05-20 → 07-19 Direct Connect outage, not evidence against duplication. A retro row has been
added to the GADS Change Log so this stops recurring.

---

## 3. Local Services Ads (LSA)

Four accounts: Fort Smith `2344723790`, Joplin `7020216103`, Olathe `2664128737` (rolls up under
Kansas City in reports), Wichita `1830697125`.

| Path | ORIGIN → TRANSPORT → DESTINATION | Automated? | VERIFIED | STATUS |
|---|---|---|---|---|
| **Report path** | Local Services API → `gads-report/lsa.py` `window()` → in-memory only, rendered into the Friday/monthly report | ✅ automated, on the report schedule | ✅ live API pull this session; week-by-week counts reproduced exactly | healthy |
| **Sheet path** | LSA Lead Inbox → `RF-LSA-puller.gs` / `RF-LSA-sync.gs` (RF Webhooks project) → `MM!LSA Leads (auto)`, `MM!Leads` | ✅ automated daily | ⚠️ trigger exists and runs clean; the count definition is wrong (below) | **broken (minor)** |
| **Legacy path** | Four Lead Inbox CSVs downloaded and **pasted by hand daily** → `MM!Paste-LSA` | ❌ human | — | superseded by the auto path; retire the paste tab |
| **CRM tagging** | `tagLsaSourceInAccuLynxScheduled()` writes the lead source back **into the live AccuLynx CRM**, every 2 days 6am America/Denver, two-layer match (phone, then name+date) | ✅ automated | ✅ trigger confirmed live | healthy — but **migration-bound** (§9) |

**CONSUMERS:** `MM` Lead Command, Performance, KPI Scorecard, 8-Week Cohorts; `weekly_exec.py`;
`monthly_exec.py`. **RECIPIENTS:** Discord, client email, Haley.

**Definitional bug, now proven.** `lsa.py:window()` returns charged and total leads separately.
`weekly_exec.py` picks **charged**; the Aug 7 client PDF picked **total**. On top of that the sheet's
feed silently drops `DECLINED` leads that Google still billed for — a genuine 4-lead undercount.
For Jun 8 – Aug 2 the true numbers are **94 all-leads (63 phone + 31 message), 70 charged**.
Every LSA figure must state which definition it uses.

---

## 4. Calls — CallTrackingMetrics + the grader

| | |
|---|---|
| **ORIGIN** | CTM account `425821`. Per-market numbers: KC (913) 270-5440 · Joplin (417) 222-3565 · Fort Smith (479) 437-0171 · St. Louis (314) 207-6227 · Mena (479) 437-0111 · Meta (913) 298-6116 · new Meta swap (913) 565-4470. **Wichita has no CTM number.** Master forward: (913) 393-3008. |
| **TRANSPORT** | CTM webhook → `RF-webhook-receiver.gs` `doPost()` (`normalizeCtm_` lifts gclid onto the call row). **Event-driven**, no schedule. |
| **DESTINATION** | `MM!Leads` (the 48-column spine); `MM!Paste-CTM` is the legacy manual zone |
| **CONSUMERS** | `Leads!AE` `channel_rollup` ARRAYFORMULA → Lead Command, Dashboard, Pacing, Performance |
| **VERIFIED** | ⚠️ webhook receiver code confirmed present; **no live test call pushed through this session** |
| **STATUS** | healthy, unproven end-to-end since the Meta number was added |

### 4a. The call grader

| | |
|---|---|
| **ORIGIN** | CTM call recordings |
| **TRANSPORT** | Deepgram transcription → Claude grading. **Two implementations exist:** `Eaveside-Call-Grader.gs` in the **Call Tracking** Apps Script project (account `haley@eaveside.com`, project `1J57bcvG0OPFnAs5juG-nLx8N4whwI4-cN-87prggzn4FSO_D54yB59xX`, daily trigger) and a Python twin `rf_lsa_grader.py` on Haley's Mac. |
| **DESTINATION** | `MM!Call Grades` (516 calls graded), surfaced in `MM!Lead Command` |
| **CONSUMERS** | Lead Command's `Grade` and `Next step` columns; the call-intelligence diagnosis; LSA refund disputes |
| **RECIPIENTS** | Haley (working queue); LSA dispute filings |
| **VERIFIED** | ⚠️ project and file confirmed live via Chrome (`Eaveside-Call-Grader.gs.gs`, 199 lines, modified 2026-08-09). **The Chrome bridge dropped before the grade prompt could be read** — whether the corrected logic is actually pasted in is UNVERIFIED. |
| **STATUS** | ⚠️ **suspect.** The project reports a **5.41% error rate over 37 executions in 7 days, with the errors landing on 2026-08-10.** Two known-needed fixes (booked-before-`out_of_area` ordering, and the 9-market / 222-served-town list injected into `GRADE_PROMPT`) were bundled for "one paste" and there is no evidence the paste happened. **Consequence: the grader may still be auto-filing "geographic area not served" disputes against towns RF demonstrably serves.** |

**Note the filename defects:** `Eaveside-Call-Grader.gs.gs`, `RF-acculynx-master.gs.gs`,
`RF-lead-outcomes-cache.gs.gs` all carry doubled extensions.

---

## 5. Web forms

| Path | Detail | STATUS |
|---|---|---|
| **Current** | Bricks native form + mu-plugin `rf-lead-router.php` (live 2026-07-11) → `RF-web-lead-receiver.gs` → `MM!Web Leads (auto)` | healthy |
| **Legacy** | Formidable form 5 → `RF-webhook-receiver.gs` → `MM!Leads`; manual zone `MM!Paste-Forms` | superseded |
| **Chatbot** | Roofers Guide chat leads → `RF Chat Leads` Apps Script (gmail account, `Code.gs`, **0 triggers**) → `MM!Chatbot (auto)`; chat leads also forward to tneal@roofingforce.com | stale — tab frozen |

⚠️ **Double-count risk, unresolved.** Both ingestion paths can be live simultaneously and there is no
dedup between them. `rf-reporting-plan` flagged this in early August; it has not been reconciled.
**VERIFIED:** ❌ — needs a test submission through each path.

---

## 6. Spend feed — the two confirmed defects

`_SpendLive` is the single most-read tab in the estate and it has three problems, two of them proven
to the cent against the API this session:

1. **Column C is TOTAL spend (Google Ads + LSA), not Google Ads.** Verified on 62 of 64 days.
   Mislabelled, and a standing misread hazard — several downstream tabs treat it as Ads-only.
2. **2026-07-27: $79.15 of phantom spend.** Week Jul 27 – Aug 2 reads `$3,955.28` vs platform
   `$3,876.13`, a difference of exactly $79.15. **This figure is in the PDF already sent to the client.**
3. **2026-07-11 / 07-12: $86.08 LSA double-count.** 7/12's LSA spend was written onto the 7/11 row
   (the known timezone off-by-one in the deployed `RF-ads-spend-sync.js`), then a correct 7/12 row was
   appended out of sequence at the bottom without clearing the bad one.

Total drift: **$165 across 64 days on $22.7k — 0.7%.** Importantly, **the Google Ads column has no
timezone error**; the off-by-one is confined to the LSA column. The long-standing note that "the
deployed spend script mislabels every daily row" is therefore **half true and should stop being
repeated as-is**.

**VERIFIED:** ✅ day-by-day API comparison, 64 days.

---

## 7. AccuLynx — jobs, revenue, and the geo export

| Flow | TRANSPORT | Schedule | DESTINATION | STATUS |
|---|---|---|---|---|
| Master daily sync | `RF_masterDaily` in `RF-acculynx-master.gs.gs` | daily ~05:30 | `MM!AccuLynx Jobs (auto)` — **the only source carrying `salesAmount`** | healthy · migration-bound |
| Native rollup | `alnSyncNativeDaily` (`RF-acculynx-native-rollup.gs`), `GET /jobs/{id}/payments/overview` | daily ~07:00 | `MM!AccuLynx Native`, `MM!AccuLynx Native Raw` | healthy · migration-bound |
| Outcomes cache | `RF_dailyPostCache` (`RF-lead-outcomes-cache.gs.gs`) | daily 06:00 | `MM!Lead Outcomes` | stale (tab frozen) |
| Health check | `RF_healthCheck` | every 3h | `MM!Health Log` | healthy |
| **Geo export** | `exportJobsGeo()` in `GeoExport.gs` — **NO TRIGGER, manual by design** (`geoExportTestOne()` → `geoExportReset()` → repeat `exportJobsGeo()` until the log says GEO EXPORT COMPLETE) | human, on demand | `DLA!AccuLynx Geo Export` — **7,047 real rows**, 2025-01-01 → 2026-08-08 | healthy, freshly fixed |

**The geo export was badly broken and is now fixed (2026-08-10).** The old code used
`&recordStartIndex=`, which AccuLynx silently ignores, so it wrote **the same 25 records 939 times =
23,475 junk rows** — and it read `c.mailingAddress`, which is empty. Now uses `&pageStartIndex=` and
`job.locationAddress`. **This fix is permanent and was NOT reverted.** Any doc still claiming "23,475
AccuLynx records exported" is describing the bug, not a dataset.

**VERIFIED:** ✅ trigger list read live in the Apps Script UI (7 triggers on RF Webhooks, all 0% error,
all ran 2026-08-10); ✅ 7,047 rows and the date span confirmed by reading the tab.

### 7a. Revenue / closed loop — the weakest link in the system

| | |
|---|---|
| **ORIGIN** | AccuLynx won-job `salesAmount` |
| **TRANSPORT** | `MM!_ClosedLoop` matches won jobs to leads **by phone number** |
| **DESTINATION** | `MM!8-Week Cohorts` revenue/ROAS columns, `MM!ROI & Revenue`, `MM!Attribution Jan26+` |
| **RECIPIENTS** | **The client** — this is what ROAS claims in the emailed report rest on |
| **VERIFIED** | ✅ examined this session |
| **STATUS** | 🔴 **broken enough to be dangerous.** **$14.72M of $15.7M in won-job value is `unmatched` — 694 of 766 jobs, roughly a 9% match rate.** The tab also contains a corrupted date serial (`46027`). |

🔴 **Specific escalation:** the **$11,001 Christian Nwando job** is the entire basis of the "Google Ads
1.7× ROAS" headline in the report emailed to the client on 2026-08-07 — and `_ClosedLoop` does **not**
match it to Google Ads. The live sheet shows $0 for that week and 0.1× ROAS. **The client has been told
Google Ads is profitable on the strength of a job the live system does not credit to Google Ads.**
Resolve by hand before publishing any further Google Ads ROAS figure.

Standing rule, inherited from `rf-reporting-plan` and reaffirmed: **revenue must come from AccuLynx
contract `salesAmount` via attribution, never from `MM!Leads` `job_value`.** That undercount is why the
`Source Funnel` tab was retired.

---

## 8. The scheduled reports

Verified live via `list_triggers` this session. **Only four are enabled, and all four are Roofing Force.**

| Schedule (UTC) | Trigger | Runs | Reads | Writes / sends |
|---|---|---|---|---|
| Mon+Thu 13:00 | `trig_01BBX7EpSjqoPHKaYyLt6cQM` | `daily_report.py` | Google Ads API | `out/*.html`, Discord `#roofing-force` embed |
| Mon+Thu 13:20 | `trig_019KYPmhdhRRxtKpmtoHqd7j` | `weekly_terms.py` | Google Ads API, 16-week search terms; WebSearch to sort VERIFY terms into `competitors.txt`/`brands.txt` | Discord embed + numbered proposals + `pending_negatives.json` |
| Fri 13:30 | `trig_01B7C8mGpTHtSiK5rJxxmQLK` | `weekly_exec.py` | Google Ads API + 4 LSA accounts, Fri–Thu window + 8-week trend | Discord embed; **Gmail DRAFT** to cburnett@/rdavis@/gdavis@roofingforce.com cc george@eaveside.com |
| 1st 14:00 | `trig_01WP9cCzg11wvR3jXnGMPSX3` | `monthly_exec.py` → `make_pdf.py` | Google Ads + LSA, 13 months; optionally `out/lead_audit.json` + `out/gsc.json` | branded HTML + PDF, SendUserFile |

🔴 **The hourly worker is OFF.** `trig_01EG8mmXAvu894PiJgwSrCNb` (`35 * * * *`) has not run since
**2026-08-07**. That task is what reads `#roofing-force`, applies the 👀/✅/⚠️ reactions, maps
"approve 1, 3" through `pending_negatives.json`, runs `apply_negative.py`, and drains
`tasks/queue.json`. **Meanwhile the Mon/Thu search-terms job keeps proposing negatives.** With the
worker paused, approvals typed in Discord only get applied if the Mac bot happens to be running.
This is the highest-priority operational fix in this document.

⚠️ **A duplicate weekly client email exists.** `trig_01K3bjHq7MAGjXFZMsNnyinJ` (Mon 14:00, disabled)
drafts the identical "Marketing Update — Week of […]" subject line from a Mon–Sun window off the
**sheets**, while the live Friday task uses a Fri–Thu **API** pull. If it were ever re-enabled Haley
would get two drafts with conflicting numbers. It is the superseded ancestor — delete it.

🔴 **Credentials in plaintext, five times over.** Five trigger prompts embed the same nine live
secrets (Google Ads developer token, OAuth client id/secret, refresh token, Discord webhook, MKTG Bot
token, GitHub PAT); one pastes the PAT inline in a clone URL. Anyone who can read the trigger list has
full Ads write access, the bot token, and repo write. **Five copies to rotate** if rotation ever happens.

### 8a. Reports that are NOT scheduled

The **"Paid 8-Week" / "Paid Lead Report" / "Weekly Lead Report"** format emailed to the client on
2026-08-07 is **not produced by any scheduled task, the repo, or Apps Script.** It was built ad hoc by
Python that existed only in a cloud container's `/tmp` (`build_weekly.py`, `rf_paid_performance.py`).
It reads the **Marketing Metrics** sheet — its footer literally says "Live detail: Lead Command tab."

A Thursday auto-send is **spec'd but not built**: Apps Script under haley@eaveside.com, Thursday
4:00pm Mountain, PDF attachments, to the client list. **PDF is mandatory** — Rick Davis could not open
the HTML on 2026-08-07.

---

## 9. Negative keywords — the four-log flow

| Stage | Where |
|---|---|
| Proposal | `weekly_terms.py` (Mon+Thu 13:20) → Discord, numbered, + `pending_negatives.json` |
| Approval | Haley replies in Discord: "approve all" / "approve 1, 3" / "all except 2" |
| Apply | `apply_negative.py`, campaign-level, via the hourly worker or the Mac bot |
| Logged in **four** places | `GADS!Negatives Log` · `GADS!Change Log` · repo `negatives-log.md` · Discord thread |

**`apply_negative.py` guardrails (all `sys.exit(2)` unless `--force`):** own brand (`\broofing\s*force\b`);
any conversions in the last 60 days; "erie" is KC-only (blocks if a target campaign name lacks
`kc|kansas`); core lead intent (roofing stem + service/buy word) unless a junk word is present
(`jobs|hiring|salary|diy|training|supply|wholesale|calculator|erie|qxo`). Non-blocking safety: only
ENABLED SEARCH campaigns are targetable (paused campaigns are invisible to it), exact
`(term, matchtype)` dedup, `--dry-run`.

**STATUS:** ⚠️ the flow is sound but **stalled** — `GADS!Negatives Log` has entries only for 7/31 and
8/3, and the hourly worker that applies approvals has been off since 8/7. Three competitor negatives
(allstate / versacon / roden) remain parked pending the Wichita decision.

---

## 10. Human-maintained inputs

| Input | Owner | Destination | STATUS |
|---|---|---|---|
| `GADS!Change Log` | Haley (hand-typed) | GADS | ✅ **healthy — the single healthiest artifact in the estate.** ~40 entries, 2026-06-03 → 2026-08-10, columns `Date \| Campaign \| Change Type \| Detail \| Reason \| Owner \| Result` |
| `GADS!August Scale Tracker` "Actual" columns | nobody | GADS | 🔴 **empty in all 20 rows.** Wk1 (Aug 4–10) closed and was never reconciled. Plan said $8,500 / 55 leads; actual was ~$4,047 / 20 leads. Fix proposed in SHEETS-PLAN.md |
| `gads-report/rf-work-log.md` | Haley, via "log: …" in Discord | repo | healthy |
| `gads-report/rf-focus.md` | Haley, in her words | repo | healthy |
| GSC organic data | Haley's Chrome, manual at month-end | `out/gsc.json` (nothing writes it) | ⚠️ manual, and `monthly_exec.py` silently skips the section when the file is absent — which is always, on unattended cloud runs |
| LSA service areas | Haley's Chrome (no API) | LSA platform | ⚠️ Joplin / Fort Smith / Wichita service areas are **unread** — cross-origin iframe blocks automation |
| `MM!Pacing` B6 | hand-typed | MM | reads 401 vs API 405.1 |

---

## 11. What breaks when EaveSide CRM replaces AccuLynx

**Status: DECIDED 2026-06-26, NEVER EXECUTED.** EaveSide CRM (`EaveSide/roof-estimate-crm`, prod
eaveside.com, RF companyId `a64c8e61-65a3-473b-91de-1b3a86e6ec13`) is to fully replace AccuLynx with
one-way ingestion. Every file written after that date keeps building on AccuLynx, and on 2026-07-12
Haley explicitly chose "spreadsheet-only lead capture for now, EaveSide webhook deferred." **No session
dump from 2026-08-10 mentions the migration at all** — it has fallen out of everyone's context, which
is exactly the failure this document exists to prevent.

Every flow below must be rebuilt or retired at cutover. **Design new work with this list in hand.**

| Flow | Fate at cutover |
|---|---|
| `RF_masterDaily` / `RF-acculynx-master.gs.gs` | **rebuild** against EaveSide — it is the only `salesAmount` source |
| `alnSyncNativeDaily` / native rollup | **rebuild** |
| `RF_dailyPostCache` / lead-outcomes-cache | **retire** — EaveSide holds outcomes natively |
| `tagLsaSourceInAccuLynxScheduled()` | **rebuild** — currently writes lead source into the live AccuLynx CRM |
| `exportJobsGeo()` / `DLA!AccuLynx Geo Export` | **rebuild** — the served-footprint analysis depends on it |
| `MM!_ClosedLoop` phone-match | **rebuild** — and this is the chance to fix the 9% match rate properly |
| Call grader's `in_acculynx` logic | **rebuild** |
| `DLA` audit-sheet lookups against AccuLynx | **rebuild** |
| `MM!AccuLynx Jobs (manual)`, `AccuLynx Native Raw` | **retire** |

Unresolved gate from the legacy notes: **PR #2454** (prod web-form dedup) had to merge before the form
webhook could go live on prod. No file confirms it did.

---

## 12. Verification log — what was actually checked, and how

| Claim | Method | Result |
|---|---|---|
| Google Ads spend & conversions | Live API pull, `segments.date BETWEEN '2026-06-08' AND '2026-08-09'`, by campaign and conversion action | ✅ matches `_SpendLive` Ads column to the cent, 64/64 days |
| LSA lead counts | Live Local Services API pull, per account, weekly | ✅ 94 all-leads / 70 charged for Jun 8 – Aug 2, reproduced exactly |
| The 94-vs-44 "conflict" | Decomposed against the API | ✅ resolved: −33 window, −13 charged-vs-total, −4 genuine `DECLINED` bug |
| Apps Script projects, files, triggers | Read live in the Apps Script UI via Haley's Chrome, both accounts | ✅ 7 projects mapped; `/u/0/`=eaveside, `/u/1/`=gmail |
| RF Webhooks ownership | Owner="Me" under `/u/1` | ✅ **gmail account**, not eaveside |
| `exportJobsGeo()` trigger | Trigger panel + code search for `newTrigger` | ✅ **none — manual by design** |
| Duplicate "Call Tracking" project | Opened both | ✅ gmail copy is an **empty shell, 0 files, 0 triggers** — safe to delete |
| Corrected call grader pasted in | Attempted | ❌ **Chrome dropped before the prompt could be read — UNVERIFIED** |
| All 86 spreadsheet tabs | Read live via the Sheets API | ✅ RF GADS 6, DLA 19, MM 61 |
| `_LSALive` tab | Searched all three workbooks | ✅ **does not exist** — the name in the consolidation prompt is wrong; nearest are `DLA!_LeadsLive` and `MM!_SpendLive` |
| Scheduled tasks | `list_triggers`, all 534,596 chars read | ✅ 11 triggers; 4 enabled; hourly worker off since 8/7 |
| Repo touches the sheets? | Searched all Python for `gspread`/`googleapiclient`/`sheets.googleapis` | ✅ **no** — zero sheet access anywhere in the repo |
| Client email cadence | Gmail `in:sent` search, 45 days | ✅ nothing sent to RF since 2026-08-07 05:20 |

**Not verified, and honestly flagged:** no live CTM test call was pushed; no web-form test submission
through either ingestion path; the eaveside "Call Tracking" project's triggers, Script Properties, and
the grader prompt were never opened; the "Site Leads" and "LSA Lead Tracker (_LSALive)" Apps Script
projects under haley@eaveside.com were never opened. These are the four gaps a follow-up session
should close first.

---

## 13. Open defects register

Ordered by what would hurt the client soonest.

| # | Defect | Where | Severity |
|---|---|---|---|
| 1 | `_ClosedLoop` matches 9% of won-job value; the $11,001 job behind the client's "1.7× ROAS" is unmatched | `MM!_ClosedLoop` | 🔴 client-facing |
| 2 | Hourly worker off since 8/7 — negative approvals not being applied | `trig_01EG8mmXAvu894PiJgwSrCNb` | 🔴 operational |
| 3 | Call grader may still file "area not served" disputes against served towns; 5.41% error rate | Call Tracking project | 🔴 client-facing |
| 4 | Possible Jul 20 – Aug 2 call conversion double-count | Google Ads conversion actions | 🔴 client-facing |
| 5 | `_SpendLive` col C mislabelled (total, not Ads); $79.15 and $86.08 bad cells | `MM!_SpendLive` | 🟡 |
| 6 | `Leads!B` date blank at the top of the ledger → every Organic/LSA formula on `DLA!Overall` returns 0 | MM → DLA | 🟡 |
| 7 | `Sheet7` repurposed but six market tabs still `COUNTIFS(Sheet7!$D:$D,"LSA",…)` → permanent 0 | DLA | 🟡 |
| 8 | `Overview` and `Economics` report 483 paid leads / $8 CPL and 196.5× ROAS — both miscounts | MM | 🟡 use `Performance` and `KPI Scorecard` instead |
| 9 | `DLA!YoY Daily` 366 rows all $0; `YoY Monthly` wrong; `Ad Performance` YoY column zeros | DLA | 🟡 the `YOY_BACKFILL` addition was never re-pasted into the deployed Ads Script |
| 10 | `site_health.py` `card()` rebinds `up` to a bool then calls `len(up)` → `TypeError`; swallowed by a try/except, so **the Website section silently vanishes from the client report exactly when a page is down** | repo | 🟡 |
| 11 | `monthly_exec.py` omits the `campaign.status` filter → REMOVED campaigns enter monthly totals | repo | 🟡 |
| 12 | Web-form double-ingestion (Bricks + Formidable) with no dedup | MM | 🟡 unquantified |
| 13 | `mktg-bot/gads-report/` duplicate tree; `install.sh` copies only `if [ ! -d gads-report ]`, so it can never refresh | repo | 🟢 |
| 14 | `tasks/done.json` referenced by README, SYSTEM.md and the ops skill — does not exist | repo | 🟢 |
| 15 | Five trigger prompts embed nine live secrets in plaintext | scheduled tasks | 🟡 security |
| 16 | `_Audit` tab contains live `#REF!`; `MM` has 5 empty `Sheet2`–`Sheet6` clones, 2 `Leads BACKUP` copies, `GeoTmp2` | MM | 🟢 cleanup |

---

## 14. The going-forward rule

1. **Every session ends with a dump** into `_context-consolidation/session-dumps/` — until the next
   consolidation supersedes them.
2. **Every account, site, or tracking change gets a `GADS!Change Log` row the same day.** No exceptions.
   An unlogged change is the thing that costs the next session an hour.
3. **Every new client gets this same folder structure from day one** — repo entry in `clients.json`
   first, then the workbook set in SHEETS-PLAN.md.
4. **Canon is this repo plus the Change Log.** Nothing else is cited as authority.
5. **Every figure carries its date window.** The entire Aug 7 escalation was two correct reports with
   invisible windows.
