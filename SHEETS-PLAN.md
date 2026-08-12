# SHEETS-PLAN — the Roofing Force workbook rebuild

**Goal:** the client tracking sheets are clean, accurate, automated, and repeatable for every future
client. Roofing Force is the prototype; Copper Ridge gets the clean version from day one.

Written 2026-08-10. Reflects Haley's decisions of the same date (marked **[Haley 8/10]**).
Companion to SOURCE-MAP.md, which documents where every number comes from.

---

## 0. The four workbooks — what each one is for

**[Haley 8/10]** Internal Master is **ops only**. Marketing Metrics stays the metrics engine. This is
the right call: the `RF Webhooks` Apps Script project is hard-bound to Marketing Metrics and writes
eleven tabs into it on seven daily triggers. Moving the raw data would mean rewriting ten `.gs` files
and risking the daily syncs, for no gain.

| Workbook | ID | Audience | Role |
|---|---|---|---|
| **Marketing Metrics** | `1Eguf8HwR0wU9Q-DO_JF5ctDCebparkw3BgyvDMiYoLc` | internal | The engine. Raw ingestion + the 5 canonical views. Apps Script writes here. |
| **Roofing Force (Internal Master)** | `14AWd_L3XQJehp-Grx0_-Tu9U0OpF8qHUlnY1GKYkpNE` | internal | Ops. Source map, change log, weekly cadence, access, decisions. **Where Haley plans her week.** |
| **Roofing Force Marketing Playbook** | `1Y7Y-phDWz_cPGmKy0MQkJERTaUX7L9v4d6_HfKk0Wrk` | **client-facing** | The Agency OS master structure, fully built for RF. Work Scope is the spine. |
| **Roofing Force Content Library** | `10b0rzM1F0Nde8gHMa7CJK2hykGC9pzfxz3tE4uieO_c` | **client-facing** | Copper Ridge structure, catered to RF's business. |

All three new sheets were created 2026-08-10 within ~70 seconds of each other, own `Sheet1` only, and
contain **zero cells**. Pure greenfield — nothing to preserve, nothing to break.

**Retiring:** Daily Lead Audit (`19-hZ_E17…`, 19 tabs) folds into Marketing Metrics. It cannot be
deleted until `MM!_SpendLive`'s `IMPORTRANGE` is repointed — five views read it. **Roofing Force GADS**
(`16JYQWW…`, 6 tabs) is the current home of the Change Log; that tab migrates to Internal Master.

---

## 1. Current state — the honest inventory

**86 tabs across three workbooks.** Full tab-by-tab detail with headers, row counts, date ranges and
formula notes is in `findings/sheets-inventory.md`; this is the disposition summary.

### 1a. Marketing Metrics — 61 tabs

| Disposition | Count | Tabs |
|---|---|---|
| **KEEP — raw feed** (Apps Script writes these; do not touch) | 8 | `Leads` (48-col spine) · `Web Leads (auto)` · `LSA Leads (auto)` · `AccuLynx Jobs (auto)` · `AccuLynx Native` · `AccuLynx Native Raw` · `Call Grades` · `Health Log` |
| **KEEP — canonical view** | 5 | becomes the 5 views in §2 |
| **KEEP — config** | 3 | `Instructions` · `Conversion Config` · `Source Map` |
| **MERGE into a view** | 12 | `Overview` → Exec Dashboard (duplicate) · `Daily`, `Monthly`, `Economics` → Paid Performance · `Paid Lead Tracker`, `St. Louis Leads`, `Lead Detail` → Lead Detail (become filters) · `Revenue Sources`, `ROI`, `Attribution Jan26+` → ROI & Revenue · `Performance`, `Exec Summary` → Exec Dashboard |
| **FIX THEN KEEP** | 3 | `_SpendLive` (rename **Spend Feed**; 3 defects, SOURCE-MAP §6) · `_ClosedLoop` (9% match rate) · `8-Week Cohorts` |
| **RETIRE — paste zones** (automation confirmed live) | 3 | `Paste-CTM` · `Paste-LSA` · `Paste-Forms` |
| **RETIRE — superseded** | 8 | `Source Funnel (RETIRED)` · `Lead Outcomes` · `Call Intelligence Findings` (point-in-time; archive) · `GAds Tag Preview` · `LSA Tag Log` · `LSA Name Recovery` · `July Backfill (temp)` · `AccuLynx Jobs (manual)` |
| **DELETE — dead weight** | 11 | `Lead Notes` (empty) · `Sheet2`–`Sheet6` (5 empty Call Grades clones) · `GAds Recovered` (header only) · `GeoTmp2` · 2× `Leads BACKUP` (archive off-sheet first) · `_Audit` (live `#REF!`) |
| **MOVE to Internal Master** | 2 | `Change Log` · `Conversion Change Log` (absorb into one) |
| Support / import plumbing | 6 | `_PerfImport`, `_MarketImport`, `Chatbot (auto)`, `Initiatives`, `Dashboard`, `KPI Scorecard` — resolve during build |

**Net: 61 → ~19.** Nothing deleted before it is archived; see §5.

### 1b. Daily Lead Audit — 19 tabs → fold in and retire

`Overall` (current to 8/9, the `_SpendLive` source) · `AccuLynx Geo Export` (**7,047 clean rows**,
keep — move to MM) · `Daily Process` · five market tabs (`Olathe` `Joplin` `Fort Smith` `Wichita`
`St. Louis`, all current) · `Mena` (**6 rows, dead since June 1**) · `Sheet7` (repurposed — and six
market tabs still `COUNTIFS` against its old shape, returning permanent 0) · `_LeadsLive` ·
`_YoYraw` (stale 7/12) · `YoY Monthly` (wrong) · **`YoY Daily` (366 rows, all $0 — broken)** ·
`_PerfRaw` · `Ad Performance` (live, YoY column zeros) · `Keyword Plan` + `Landing Page Map`
(**every cell `TBD`, never populated — delete**) · `GeoTmp`.

### 1c. Roofing Force GADS — 6 tabs

`Change Log` (**healthiest artifact in the estate** — ~40 entries, 6/03 → 8/10, move to Internal
Master) · `Negatives Log` (21 entries, idle since 8/3) · `August Scale Tracker` (**Actuals empty in all
20 rows**) · `Campaign Tracker` (as-of 7/25, ~2 weeks stale) · `St. Louis Build` (statuses contradict
what shipped) · `Reference` (timeless, fine).

---

## 2. Target design

### 2a. Marketing Metrics — 5 views over the raw feed

Carried forward from the `rf-reporting-plan` artifact, revised against what the live data actually
supports.

| View | Contents | Sources |
|---|---|---|
| **Executive Dashboard** | Leads, paid leads, spend, CPL, won jobs, revenue, ROAS — daily · 7d · monthly · YoY · pacing | Spend Feed, Leads, `_ClosedLoop` |
| **Lead Detail** | One row per lead: grade, AccuLynx/EaveSide status, why stuck, next step. Market is a **filter, not a tab.** | Leads, Call Grades, CRM sync |
| **Paid Performance** | Channel × market, with the date window in every header | Spend Feed, LSA, Google Ads |
| **ROI & Revenue** | Won jobs, contract $, the leak report, match-rate health | AccuLynx `salesAmount` via `_ClosedLoop` |
| **Pacing / Targets** | Plan vs actual, weekly and monthly | Business Model targets |

**Three hard rules, each earned the hard way:**

1. **Revenue uses AccuLynx contract `salesAmount` via attribution — never `Leads.job_value`.** That
   undercount is why `Source Funnel` was retired.
2. **Every figure carries its date window in the header.** The entire Aug 7 escalation was two correct
   reports with invisible windows.
3. **Every LSA figure states its definition** — all-leads or charged. They differ by ~25%.

**Rename for honesty:** `KPI Scorecard` currently shows $179 and $328 CPL under one label. Split into
**CPL (Ads-counted)** and **CPL (CRM-matched)**.

### 2b. Roofing Force (Internal Master) — ops only

**[Haley 8/10]** Her stated goal: *"help us stay on task and figure out what we're doing which week…
so I'm not manually figuring out what did I do this last week."*

| Tab | Purpose | Fed by |
|---|---|---|
| **Source Map** | The lineage table from SOURCE-MAP.md, live | maintained on change; mirrors the repo doc |
| **Change Log** | Absorbs `GADS!Change Log` + `MM!Conversion Change Log`. Columns stay `Date \| Campaign \| Change Type \| Detail \| Reason \| Owner \| Result` | **same-day rule**, by hand or by bot |
| **Weekly Log** | `Week of \| Done this week \| Focus next week \| Waiting on client \| Notes` — matching the Agency OS master template | **auto-drafted** (§3) |
| **Work Scope Mirror** | Read-only mirror of the client Playbook's Work Scope, so internal status and client-facing status can never drift | `IMPORTRANGE` from the Playbook |
| **Open Items & Decisions** | The blocked-on-client register with chase dates — five RF decisions have been blocked since May with no chase date ever recorded | manual |
| **Access & Assets** | Accounts, IDs, who owns what, where credentials live | manual |
| **Defects** | The open-defects register from SOURCE-MAP §13, with owner and status | manual |
| **Automation Health** | Trigger-by-trigger: last run, error rate, expected next run | ideally auto |

### 2c. Roofing Force Marketing Playbook — client-facing

**[Haley 8/10]** Built on the **Agency OS master template** structure, with George's 287 scored items
remapped onto it.

Tabs, mirroring the master template `1zBNQHATwzECJgHvpoOE_2geIoYvvvzOSuAkBA7iaEcA`:

| Tab | Notes for the RF build |
|---|---|
| **Overview** | Who we are, what we're doing, how to read this book |
| **Audit** | Frozen baseline. Source: George's `Executive Summary` (readiness ~60/100) + `Revenue Leak Audit` |
| **Business Model** | The targets calculator. RF business mix: $90.8M / 5,623 jobs |
| **Work Scope** | **The spine.** Master structure: col A glyph status (`☐ ✅ 🔁 🔄 ⏸ —`), then `Deliverable \| What this is \| Latest result / next action \| Last done \| Type \| Cadence \| Owner`. Three phase rows (FIRST — THE FOUNDATION · THEN — DEMAND, ALWAYS ON · ALWAYS — MORE FROM EVERY LEAD & EVERY JOB), 18 section rows, then deliverables. Row 2 keeps the live COUNTIFS rollup. |
| **KPI Tracker** | `Metric \| Baseline — day one \| Latest \| Aug 2026 … Jul 2027 \| MoM Δ \| Notes`. `Latest` = per-row `INDEX/MATCH(1E+99)`. Five target rows pull from Business Model. Eight sections. |
| **Weekly Log** | Client-facing twin of the internal one |
| **Access & Assets** | ⚠️ **scrub the template's inherited dirt** — `jack groehnmim` in the LSA cell and a webflow/companycam/jobnimbus note on the Website row will propagate into every clone |

**The remap.** George's `Roofing Force Playbook Review` (`15UOO-MR-jvHo12_jo92PQXdhsX7OvYc2Yx4MBd40Tyk`,
owned by george@eaveside.com) holds **287 items scored 45 done / 137 partial / 105 to-do** in a
Step 1–8 × Work Category × boolean-checkbox format. The master uses phase → section → deliverable with
glyph statuses. Mapping rules:

- Step 1–8 → the 8-step spine already underlies the master's phases; map Step → phase → section.
- `done` → `✅` · `partial` → `🔄` · `to-do` → `☐` · items that don't apply to RF → `—`.
- Carry George's notes into `Latest result / next action` so his assessment survives verbatim.
- **Every remapped row keeps a `Source: George PR <row>` note** so nothing looks invented.
- Items with no master equivalent go to a `Unmapped (from Playbook Review)` staging tab for Haley to
  place — never silently dropped.

### 2d. Roofing Force Content Library — client-facing

Copper Ridge (`1UmiCLxnsTMILpNrT_sray9mazJjAQJ9jNcf4s4PzUfs`) is the structural model. Its convention,
which RF should keep: **row 1 = banner, row 2 = instruction paragraph, row 3 = real header, row 4+ =
data.** Field-facing tabs first.

| Tab | Header (from Copper Ridge, adapt wording to RF) |
|---|---|
| **This Week's Shoots** | `Date \| Job / Neighborhood \| Job Type \| Stage \| What to film (auto) \| Hooks to use (auto) \| CTA (auto) \| Status \| CompanyCam link` |
| **Job Shoot Briefs** | `Job Type \| Film This (min 3 pieces per job) \| Hook Angles That Fit \| CTA + Landing Page \| Gear / Notes` |
| **Playbook** | 2-column narrative, ALL-CAPS section rows |
| **Client Intake & Angles** | 2-column narrative |
| **Hooks** | `Hook \| Motivation \| Journey stage \| Service \| Hook type \| Funnel \| First frame (visual hook)` |
| **Concepts & Scripts** | `Concept \| Format · length \| Motivation \| Fits hook types \| Example hook (0–3s) \| Body (what he says) \| CTA \| First frame` |
| **Ads** | `Ad / offer \| Audience \| Headline (on the creative) \| Caption (post text above it) \| CTA button \| Visual / first frame` |
| **Swipe File** | `Advertiser \| Ad Library ID / link \| Running since \| Format \| Their hook / copy \| Why it works \| Steal this for us` |

**Automation to replicate:** `This Week's Shoots` E/F/G auto-fill from `Job Shoot Briefs` keyed on Job
Type. **Do not replicate** Copper Ridge's two malformed orphan rows (62–63) or the hand-typed-over
formulas in rows 5–7. Build the `INDEX/MATCH` range to cover RF's full job-type list, not a hardcoded
6 rows.

**RF already has content assets to seed this with:** the 20-ad static set in
`Meta Creative Engine/output/roofing-force/2026-08-07-matrix/` (with `RF-ads-copy.csv`), a 7-competitor
Ad Library swipe file, 464 Google reviews at 4.8 stars, and 34 photos in `Photos (RF)/`.

⚠️ **Open before building — C29 in CONTRADICTIONS.md.** Haley: *"we still have questions to answer as
to their content system."* RF differs from Copper Ridge: multi-market, storm-driven, a static ad set
already built. **Is RF's content program for organic social, paid creative supply, or both?** That
answer changes which tabs get built. Recommend building the paid-creative-supply tabs first (Hooks,
Concepts & Scripts, Ads, Swipe File — all seedable today) and holding the field-facing shoot tabs until
the question is answered.

---

## 3. The weekly cadence — closing Haley's actual loop

Her stated goal: weekly reports that say *"this is what we did this week, this is what we're doing next
week,"* matching the Work Scope tab, without her reconstructing her own week by hand.

**The mechanism:**

1. Every Work Scope row already carries `Last done` and `Latest result / next action`. Any SOP that
   executes a row updates them — Agency OS's own rule: *"an SOP that doesn't update the tracker didn't
   happen."*
2. A **Friday job** reads Work Scope rows whose `Last done` falls in the last 7 days → drafts
   `Done this week`. Rows with `Target week` = next week → drafts `Focus next week`. Rows at `⏸` →
   `Waiting on client`.
3. It writes that draft into **Internal Master → Weekly Log**, and mirrors the client-safe version into
   the Playbook's Weekly Log.
4. Same job fills **`August Scale Tracker` Actuals** — the fix for the tab nobody fills. Plan vs actual,
   weekly, from the API (Wk1 Aug 4–10: plan $8,500 / 55 leads, actual ~$4,047 / 20 leads).
5. It runs **before** the existing Friday 13:30 report task so the numbers agree.

This is the piece that makes the whole structure pay for itself. Build it after the workbooks exist.

---

## 4. Automated vs manual — who owns every column

The rule for every tab built: **each column is labelled either with the script + schedule that writes
it, or with the human who owns it.** No unlabelled columns. Today's ambiguity is why `August Scale
Tracker` Actuals sat empty for a week and why `Pacing!B6` disagrees with the API.

| Layer | Written by | Schedule |
|---|---|---|
| Leads spine, Web Leads, LSA Leads, AccuLynx tabs, Call Grades, Health Log | `RF Webhooks` Apps Script (**gmail account**) | 7 daily triggers |
| Call Grades enrichment | `Call Tracking` Apps Script (**eaveside account**) | daily |
| Spend Feed | `RF-ads-spend-sync.js` Google Ads Script | daily 8–9am |
| The 5 views | formulas only | live |
| Change Log | **Haley, same-day, no exceptions** | on change |
| Weekly Log, Scale Tracker Actuals | Friday job (§3) | weekly, once built |
| Work Scope statuses | whoever runs the SOP | on execution |
| Content Library | Haley / the creative engine | per batch |

---

## 5. Migration — non-destructive, in order

**Never delete data. Build new alongside old, verify parity, then retire.**

- **Phase 0 — safety net.** Snapshot every tab that has no other copy: `Call Grades`, `Lead Command`,
  `Leads` AN–AS, `AccuLynx Jobs (auto)`, `Source Map`, and both `Leads BACKUP` tabs → export to a dated
  archive file outside the workbook. Nothing else starts until this is done.
- **Phase 1 — fix the three proven defects first**, because every downstream view inherits them:
  `_SpendLive` col C relabel + the $79.15 and $86.08 cells; the LSA charged-vs-total definition;
  `Leads!B` blank dates (which currently zero out every Organic/LSA formula on `DLA!Overall`).
- **Phase 2 — build the 5 views alongside the existing tabs.** Old tabs stay live. Run both for two
  weeks and reconcile weekly against the API.
- **Phase 3 — repoint `_SpendLive`'s `IMPORTRANGE`** off the Daily Lead Audit sheet. This is the gate
  on retiring DLA; five views break if it's done in the wrong order.
- **Phase 4 — retire.** Hide before deleting. Delete only what has been archived. Move `Change Log` to
  Internal Master **last**, and leave a pointer row in the old location.
- **Phase 5 — build the Playbook and Content Library** (greenfield, no migration risk — can run in
  parallel with any phase).
- **Phase 6 — build the Friday cadence job** (§3).
- **Phase 7 — templatize.** Everything above becomes the Eaveside client template.

**Each phase updates SOURCE-MAP.md, the affected Apps Script, and the scheduled-task prompts in the
same commit.** The docs and the automation move together or they drift apart again — that drift is
what this whole consolidation exists to undo.

---

## 6. New-client instantiation checklist

So Copper Ridge gets the clean version from day one.

1. **`clients.json` entry first** — it drives everything else. (Note: today `clients.json` is read by
   **zero** Python; wiring the registry into the code is a prerequisite for real multi-client support.
   See §7.)
2. Link the Google Ads account under MCC `968-076-3943`; collect customer ID, LSA accounts, site URL,
   logo, brand colors, GSC access.
3. Create the **four workbooks** from templates: Metrics (engine), Internal Master (ops), Marketing
   Playbook (client), Content Library (client). **Scrub the master template's inherited dirt** before
   cloning (§2c).
4. Create the Discord channel + webhook; extend `listener.py` to a channel→client map.
5. Clone the four scheduled-task prompts with the new client's values; extend the hourly worker to loop
   all channels in `clients.json`.
6. Stand up ingestion: CTM numbers, web-form receiver, CRM sync, LSA accounts.
7. Fill Work Scope from the Agency OS master, mark what's in scope, set `Owner` and `Target week` on
   every row (the master ships with `Owner` empty everywhere — fill it).
8. Set Business Model targets → KPI Tracker target rows pull from them automatically.
9. **Verify:** fire each trigger once manually; confirm embeds land in the right channel; round-trip a
   test approval with 👀/✅; confirm the monthly renders with the client's logo.
10. Open the hub file and the Change Log on day one. Both stay current from then on.

---

## 7. Known blockers on making this repeatable

These are real, and they mean "repeatable for every future client" is not yet true:

1. **`clients.json` is inert.** Zero Python opens it. `config.py` hardcodes
   `CUSTOMER_ID = "3298488566"` and `ACCOUNT_NAME = "Roofing Force"`; `lsa.py` hardcodes four LSA IDs;
   `render_html.py` hardcodes `MARKET_ALIASES` and a footer reading "for Roofing Force leadership";
   `monthly_exec.py` embeds an RF-specific YoY paragraph as a literal; `classify.py` embeds RF's
   geography in a 250-word token list; `listener.py` watches one channel ID.
2. **`out/` and `state/` are flat** — two clients collide on `report-YYYY-MM-DD.html` and
   `pending_negatives.json`.
3. **The Apps Script is bound to one spreadsheet** and hardcodes `1Eguf8HwR0wU9Q-DO_JF5ctDCebparkw3BgyvDMiYoLc`
   plus eleven tab names.
4. **Two Google accounts own different halves of the automation**, with the live secrets sitting in the
   personal one.

Parameterizing the repo is the single highest-leverage engineering task behind this plan. It does not
block building the workbooks — it blocks automating them for client #2.

---

## 8. Approval

**Status: awaiting Haley's approval.** Decisions already locked in above: Internal Master = ops only ·
Marketing Metrics stays the engine · Playbook uses the Agency OS master structure with George's 287
items remapped · Content Library follows Copper Ridge.

**Still open before execution:** the RF content-system question (§2d / C29), and whether to execute in
this session or hand this file to a follow-up session as its prompt.
