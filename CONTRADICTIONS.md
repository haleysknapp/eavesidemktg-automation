# CONTRADICTIONS — conflicts found during the 2026-08-10 consolidation

Every place the inputs disagreed. Each entry gives the two claims, the evidence, a best guess, and —
where intent is genuinely unknowable — a question for Haley.

Inputs reconciled: 8 session dumps · 6 Cowork artifacts · the legacy `_device-transfer` memory folder ·
this repo's code · both Apps Script accounts · 86 spreadsheet tabs · the Google Ads + Local Services
APIs · 11 scheduled tasks · Gmail.

**Legend:** ✅ RESOLVED (evidence settled it) · 🟡 BEST GUESS (acting on it, flag if wrong) ·
❓ NEEDS HALEY (not guessable — asked, or queued to ask)

---

## ✅ Resolved by live verification

### C1. "The two weekly reports disagree — one must be wrong"
**Claim A:** the Aug 7 client PDF says LSA 94 leads / $48,664, Google Ads 149 leads.
**Claim B:** the live sheet says LSA 44 / $35,244, Google Ads 118 / $2,500.
**Evidence:** live Google Ads + Local Services API pulls. The PDF covers **Jun 8 – Aug 2**; the
`8-Week Cohorts` tab covers **Jun 22 – Aug 9**. The window rolled two weeks between send and now.
**Resolution: BOTH ARE CORRECT for their own windows.** The LSA gap of 50 decomposes exactly:
−33 window, −13 all-leads-vs-charged, −4 a genuine bug (the sheet drops `DECLINED` leads Google still
billed for). Google Ads: 149 − 21 − 21 + 12 = 119 ≈ 118. ✅
**Also corrected:** $48,664 / $35,244 / $2,500 are **revenue**, not spend. LSA spend was $5,911 /
$4,293; Google Ads spend in the sheet's window was $18,749.
**Action taken:** every figure must now carry its date window and its lead definition. In SOURCE-MAP §3.

### C2. Who owns the "RF Webhooks" Apps Script project?
**Claim A** (one dump): `haley@eaveside.com`. **Claim B** (another dump): `haleysknapp@gmail.com`.
**Evidence:** opened both accounts in Haley's Chrome. `/u/0/` = eaveside, `/u/1/` = gmail. Project
`1ZfOUmV4…Gi3lO_` shows Owner = "Me" under `/u/1`. Both accounts display the name "Haley Knapp", which
is exactly why sessions kept guessing wrong.
**Resolution: the gmail account owns it**, along with all 7 of its time-based triggers. ✅
**Consequence worth noting:** five live secrets (`ACCULYNX_API_KEY`, `GADS_*`, `WEBHOOK_KEY`) sit in
Script Properties on Haley's **personal** account rather than the agency one.

### C3. Is there a duplicate "Call Tracking" project?
**Resolution:** yes — one under each account, both created 2026-07-31. The **gmail one is an empty
shell (0 files, 0 triggers, never shared)**. The eaveside one (`1J57bcvG…`) is live: 6 files, 37
executions in 7 days. The gmail copy is safe to delete. ✅

### C4. Does `exportJobsGeo()` have a trigger?
**Resolution:** no, and by design. No trigger runs it and `GeoExport.gs` contains zero `newTrigger`
calls; its header documents a manual loop. ✅

### C5. "23,475 AccuLynx records were exported"
**Resolution:** that number is **the bug, not a dataset.** The old code used `&recordStartIndex=`,
which AccuLynx silently ignores, writing the same 25 records 939 times. Fixed 2026-08-10 to
`&pageStartIndex=` + `job.locationAddress`. The tab now holds **7,047 real rows** (2025-01-01 →
2026-08-08). The SESSION-HANDOFF-2026-08-03 line about 23,475 records is wrong and is superseded. ✅

### C6. Was the 2026-07-31 `Calls from ads` demotion a mistake?
**Claim A:** two separate sessions flagged it as a possible error and re-investigated.
**Claim B:** it was a deliberate, correct call.
**Evidence:** the May–July zeros in `Call Tracking Lead` are the 2026-05-20 → 07-19 Direct Connect
outage, not evidence against duplication. The reason sessions keep re-opening it: **there is no
2026-07-31 row in the `Conversion Change Log` tab.**
**Resolution: the demotion was correct. Do not reverse, do not re-investigate.** A retro-logged
Change Log row now closes it permanently. ✅

### C7. "The deployed spend script mislabels every daily row (timezone off-by-one)"
**Resolution: half true, and the half matters.** Day-by-day API comparison over 64 days shows the
**Google Ads column matches to the cent** — no timezone error there. The off-by-one is **confined to
the LSA column** (proven by the 2026-07-11/12 $86.08 double-count). Stop repeating the broad version. ✅

### C8. Does the repo read or write the spreadsheets?
**Claim (widely assumed across dumps):** the reports are built from the sheets.
**Evidence:** no Python in the repo imports `gspread`, `googleapiclient`, `google.oauth2`, or touches
`sheets.googleapis`. The three sheet IDs appear exactly once each, as inert strings in `clients.json`.
`weekly_terms.py`'s "paste into the GADS tracker" line is a human instruction rendered into HTML.
**Resolution: the repo and the sheets are two completely separate systems.** This is the single
biggest structural misunderstanding in the input set. ✅

### C9. Does a `_LSALive` tab exist?
**Resolution: no.** Searched all three workbooks. Nearest are `DLA!_LeadsLive` and `MM!_SpendLive`.
The consolidation prompt's mention of `_LSALive` is an error inherited from an earlier session. ✅

### C10. Which tab is the primary lead view — "Lead Command" or "Lead Detail"?
**Claim A** (`rf-reporting-plan`): Lead Command becomes "Lead Detail". **Claim B** (`rf-system-map`):
Lead Detail is retired, superseded by Lead Command. The two plans invert each other's naming.
**Evidence:** `MM!Lead Command` is timestamped Aug 10 08:58 — the freshest tab in the estate, with 42
graded calls and a live `Next step` queue. `MM!Lead Detail` is comparatively inert.
**Resolution: Lead Command is the primary lead view; Lead Detail retires.** Carried into SHEETS-PLAN. ✅

### C11. Are the geo radii wrong, and should Joplin / Fort Smith be cut?
**Claim A** (`rf-call-intelligence-diagnosis`, earlier): cut the Joplin and Fort Smith radii.
**Claim B** (`rf-served-footprint-map`, Aug 9, 24 months of data): every current radius sits inside the
p90–p95 of won jobs. Roland OK is an 11-job core zip; Springfield is a real market.
**Resolution: B supersedes A.** The 24-month dataset reversed two recommendations that had been made
on n≈2 samples (Mount Ida circle, Stilwell OK). **"Geo was not the constraint. Rank is"** — 0.0% lost
to budget on all five enabled campaigns, 66–86% lost to rank, zero keywords at Quality Score 7+. ✅
**Corollary:** Topeka (43.6mi p90, 52 jobs, $809K) and Springfield (24.9mi, 36 jobs, $532K) are
markets RF wins work in and **is not bidding on at all**.

### C12. Did the 2026-08-09/10 geo-targeting flip change anything?
**Evidence:** two dumps describe the same episode on different clocks, which risks double-counting.
The flip to `PRESENCE` on four campaigns was applied and **fully reverted the same day**.
**Resolution: net account change is zero.** Final state: KC `22284561281` and St. Louis `14592215201`
= `PRESENCE`; Fort Smith, Joplin, Mena, Wichita = `PRESENCE_OR_INTEREST`. One event, not two. ✅

### C13. Who owns the "Paid 8Week / Weekly Lead Report" format?
**Resolution: nobody.** It is produced by no scheduled task, no repo code, and no Apps Script — it was
built ad hoc by Python living only in a cloud container's `/tmp`. It reads the Marketing Metrics sheet
(its own footer says "Live detail: Lead Command tab"). A Thursday auto-send is spec'd but not built. ✅

---

## 🟡 Best guess — acting on this, flag if wrong

### C14. Is the corrected call grader actually live?
**Conflict:** one dump says the fixes were written; another says Haley chose to bundle them into
"one paste" later. The file exists (`Eaveside-Call-Grader.gs.gs`, 199 lines, modified 2026-08-09) but
**the Chrome bridge dropped before the grade prompt could be read.**
**Best guess: the paste did NOT happen** — the project shows a 5.41% error rate over 37 executions
with the errors on 2026-08-10, consistent with old logic hitting new data.
**Why it matters:** if so, the grader is still auto-filing "geographic area not served" LSA disputes
against towns RF demonstrably serves. **First thing a follow-up session should check.** 🟡

### C15. Does `8-Week Cohorts` revenue need wiring?
**Claim A** (a session that read the tabs): the Google Ads revenue column reads $0 and needs a phone
match built. **Claim B** (the session that built the tab): revenue already comes from `_ClosedLoop`,
which *is* that phone match; thin GA revenue is a timing artifact that "resolves itself."
**Best guess: B is closer** — B's author built it, A's only read it. **But B is too optimistic.**
It is not purely timing: the methods disagree *inside overlapping weeks* ($10,000 vs $35,244 for
Jun 22 – Aug 2), and `_ClosedLoop` matches only 9% of won-job value. 🟡
**Do not promise Haley a quick fix here.**

### C16. When did Google Ads tracking actually go live?
**Claim A** (client report): "the week of July 20." **Claim B** (ledger data): the first dated GA leads
appear ~Aug 3; Jun 22 – Jul 27 shows 0 ledger vs 8–31 platform.
**Best guess: both are true at different layers** — the platform-side conversion action went live
July 20, the ledger's classification only started producing dated GA rows in early August. The
canonical docs should say exactly that rather than picking one. 🟡

### C17. Gross margin — 30% or 27%?
Legacy notes assert both within two days ("30%, locked, stop questioning it" vs a 27% P&L actual).
**Best guess: use 27% for internal modelling, 30% for the agreed planning figure**, and label which is
which. Flagged rather than silently picked. 🟡

### C18. LSA average job value — $3,040, $8,005, or $10,028?
The legacy notes walk this figure upward three times, which flips LSA from "underwater" to "scale
hard." **Best guess: all three are stale and none should be used.** Recompute from
`AccuLynx Jobs (auto)` `salesAmount` once `_ClosedLoop`'s match rate is fixed. 🟡

### C19. `mktg-bot/gads-report/` — intentional or accidental?
A committed duplicate of `gads-report/` differing only by a missing `dp.react()`. `install.sh` can
never refresh it (it copies only `if [ ! -d gads-report ]`), so `git reset --hard` reinstates a stale
copy on Haley's Mac.
**Best guess: accidental.** Recommend deleting the duplicate and symlinking or fixing `install.sh`. 🟡

---

## ❓ Needs Haley — asked this session

### C20. What lives in the new "Roofing Force (Internal Master)" sheet?
**ANSWERED 2026-08-10: ops only.** Marketing Metrics remains the metrics sheet. The Apps Script stays
untouched. Carried into SHEETS-PLAN.md. ✅

### C21. Which weekly report is canon?
**ANSWERED 2026-08-10: neither — verify first.** Done; see C1. Both were correct. Recommendation now
on the table: **build client-facing numbers from the platform APIs**, use the sheet for presentation
and history, never as the source of a figure.

### C22. Which Work Scope taxonomy wins?
**ANSWERED 2026-08-10: the Agency OS master template**, with George's 287 scored items remapped onto
it so no assessment work is lost. Carried into SHEETS-PLAN.md. ✅

### C23. Rick's two open asks (Aug 7)
**ANSWERED 2026-08-10: not this session.** Left open deliberately. Both remain unanswered as of today:
the PDF resend, and "what can we do to get leads going in Wichita?" (a repeat — he also asked Jul 13).

---

## ❓ Needs Haley — still open, queued for the next round

### C24. The EaveSide-CRM migration — is it still happening?
Decided 2026-06-26 (EaveSide CRM fully replaces AccuLynx, one-way ingestion). Deferred 2026-07-12
("spreadsheet-only lead capture for now"). **Not one of the eight session dumps from 2026-08-10
mentions it.** Meanwhile every new build — `_ClosedLoop`, the grader's `in_acculynx` logic, the geo
export — deepens the AccuLynx dependency.
**Question:** is the migration still on, and roughly when? Everything being built now either has to be
built twice or has to be built migration-aware. Also unresolved: did **PR #2454** (prod web-form dedup)
ever merge? It was the gate on the form webhook going live.

### C25. Wichita — revive, exit, or park?
Paused 7/23 for zero leads at spend. The client has now asked about it **twice** (Jul 13 and Aug 7).
Evidence is genuinely mixed: only 9 won jobs in 24 months at a 6.0mi p90 radius, no CTM number exists
for the market, the LSA account is verified but produced 0 leads, and 3 competitor negatives are
parked waiting on the decision. Legacy notes list "Wichita invest-or-exit" as a client decision
blocked since May.

### C26. Topeka and Springfield — start bidding?
The 24-month footprint shows RF has won 52 jobs / $809K in Topeka and 36 jobs / $532K in Springfield
with **no ad spend at all** in either. This is the largest unexploited finding in the input set.

### C27. Should the five plaintext credential copies in the scheduled-task prompts be rotated?
Nine live secrets sit in five trigger prompts, one with the GitHub PAT inline in a clone URL. Rotating
means editing five prompts plus `.env` on the Mac. Worth it, but it is a decision with a chore attached.

### C28. The P5 playbook twins disagree on targets
Speed-to-lead <5 vs <15 min · contact 75% vs 78% · attempts over 10 vs 7 days · appointment 60% vs 66%
· no-show <15% vs <10%. A workbook built today bakes in whichever twin it reads. **Which numbers are
the real targets?**

### C29. The Content Library's open questions for RF
Haley's note: "we still have questions to answer as to their content system." The Copper Ridge library
is the structural model, but RF's business differs (multi-market, storm-driven, 464 Google reviews, a
20-ad static set already built). **What is RF's content program actually meant to do** — organic
social, paid creative supply, or both? That answer changes which tabs the RF Content Library gets.
