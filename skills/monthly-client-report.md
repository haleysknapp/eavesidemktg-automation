---
name: monthly-client-report
description: Build Eaveside's branded monthly marketing report + client email for any client. Use when Haley says "run the monthly report", "build the monthly for [client]", "monthly client report", or on the 1st-of-month report cycle. Covers data pull, judgment rules, branding, PDF, email draft, and the review loop with Haley.
---

# Monthly Client Marketing Report — Eaveside SOP

Produce a branded, executive-ready monthly report (HTML + PDF) plus a Gmail draft in
Haley's voice, for any Eaveside client. The July 2026 Roofing Force report is the gold
standard; every rule below came from Haley's corrections while building it.

## Phase 0 — Client config (resolve before anything else)

Find or ask for the client's config. For Roofing Force it lives in the
`eavesidemktg-automation` repo (`gads-report/`); for a new client, gather:

- Client name, logo file (check Haley's client folder, e.g. "Photos (RF)/Logo-01.png"; else pull from the client's website), brand colors.
- Ad accounts: Google Ads customer ID, LSA accounts, Meta when live.
- Website URL + key pages: homepage, every ad landing page, AND the top organic pages by GSC clicks.
- Sheets: daily lead audit / tracker spreadsheet IDs.
- Work-log file (dated initiative bullets) and focus file (next month's priorities).
- Email recipients (client leadership; cc george@eaveside.com), sent as DRAFT only.

## Phase 1 — Data pull (research first, formatting last)

1. **Platform data via API/scripts** — leads, spend, CPL: this month, prior month, same
   month last year, 13-month trend, per-campaign and per-LSA-account. For RF run
   `python3 monthly_exec.py --no-discord` (it builds the whole HTML). For other clients,
   replicate its queries or read their tracker sheets.
2. **GSC via Haley's Chrome** (no API access; use claude-in-chrome): Performance →
   custom compare, report month vs prior month. Pull totals, then **branded vs
   non-branded split** (built-in Query filter), then the **Pages tab** for top pages.
3. **Website health via HTTP checks**: status, load time, tracking-tag presence for
   every key page (`site_health.py` pattern).
4. **Audit sheet** (lead quality): only read it; inclusion rules in Phase 2.
5. **Initiatives**: read the client work log. If thin, sweep Haley's Granola meetings
   and relevant docs/sheets for what shipped this month, and DRAFT candidate bullets.
6. **Next-month focus**: check the focus file and any planning tracker (e.g. George's
   scale tracker tab). Treat aggressive plan numbers skeptically.
7. **If initiatives or focus can't be found anywhere — ASK HALEY.** Specific questions
   ("what shipped in July?", "what are the 3-4 August priorities in your words?"),
   never invented content. Her spoken answers are the source of truth; tighten her
   words, don't replace them.

## Phase 2 — Judgment rules (Haley's corrections; these override defaults)

**Sections to include, in order:** stat tiles (total leads / spend / blended CPL with
MoM deltas + sparklines) → "The month in brief" narrative → "Initiatives — [Month]" →
By channel → Year over year → 13-month lead + spend charts → By market → (Lead quality,
if eligible) → (Organic search, if eligible) → Website status → "Focus & targets — [next month]"
→ branded footer.

**Sections to NOT include** (tried and rejected): impression-share / "search headroom"
tables; calls-vs-forms breakdowns; top-converting-search-term lists; anything bragging
about internal tooling or reporting improvements ("we automated our reports" is not a
client win).

- **Year over year**: never let a raw YoY decline stand alone. Explain the spend
  context in the client's actual story (e.g. "ran at ~4.6× today's budget, then spend
  was throttled and we inherited the account near its low point — now rebuilding").
  Cost per lead is the like-for-like metric; volume rarely is.
- **By market**: ONE row per market. Columns: Total leads | Search | LSA (muted split
  columns, em dash where a channel doesn't run) | Spend | blended Cost/lead. Fold
  sub-markets into their metro (Olathe → Kansas City) via an alias map.
- **Website status**: one sentence when healthy — "All N key pages up (homepage,
  market landing pages + top organic pages) · average load X.Xs · tracking verified" —
  and a table of ONLY problem pages otherwise. Never a full page-by-page table when
  everything is fine.
- **Organic search (GSC)**: diagnose BEFORE publishing. Split branded vs non-branded
  and check page-level movers. If the month is down, find the real cause (brand-demand
  echo of ad spend, seasonality, SERP mix) — then decide WITH HALEY whether it goes in.
  Default: leave it out when the story is negative or muddy; never hand a client
  "organic got worse" without a diagnosis and a plan. Remember ad landing pages are
  often noindexed — they will never appear in GSC and that's intentional.
- **Lead quality (audit sheet)**: include only when the month's audit is COMPLETE
  (no empty channel columns, no long gaps). Partial audit numbers that contradict
  platform totals never go in front of a client.
- **Initiatives**: client-facing outcomes with a theme (e.g. "setting the foundation to
  scale"), one client-friendly sentence each, truthful status ("nearing QA", not
  "close to launch" unless it's true). Small items fold into a related bullet — no
  overkill standalone bullets. 3-5 bullets max, chronological.
- **Focus & targets**: 4-5 tight bullets in Haley's own words. Lead with the goal
  (e.g. "more lead volume — two levers: scale Google spend, get Meta live"). Anything
  already done moves to Initiatives. No invented numeric targets or guardrail bullets
  unless Haley approves the numbers explicitly.

## Phase 3 — Build (format only after content is settled)

- **Branding**: Eaveside masthead system — client logo top-left in a white chip,
  EAVESIDE wordmark top-right, red kicker line, big month title, slate/red accents,
  Inter font EMBEDDED as base64 (PDF renderers lack good fonts), validated chart
  palette (light `#2569a3`/`#d02028`, dark `#4f95d6`/`#e2565e`; validate any new
  client's colors with the dataviz palette validator — chroma floor bit us once).
- **Print/PDF rules**: white background in print (colored page bg makes margins look
  missing), `break-inside: avoid` on every card, footer grouped with the final section
  (never orphaned on its own page), Letter with ~0.75in top margin (`make_pdf.py`).
- Read the dataviz skill before restyling charts.

## Phase 4 — Review loop with Haley (never skip)

1. SendUserFile the HTML + PDF. Iterate on her corrections — rebuild and re-send after
   EVERY change; she reviews visually.
2. When she approves, draft the email in Gmail (DRAFT only, never send): warm, concise,
   her voice, honest about soft spots, PDF referenced as attached, signed
   "Haley Knapp / Eaveside.com". Keep the email's next-month paragraph in sync with the
   report's Focus section.
3. Post a summary embed to the client's Discord channel if one exists — summary only,
   no HTML attachments (nobody downloads them).
4. Push any script/content changes to the automation repo so scheduled runs and the
   Mac bot stay current.

## Failure modes to avoid (each one happened)

- Publishing a negative organic section without diagnosis.
- Partial audit data contradicting platform numbers in the same report.
- Inventing focus/target numbers Haley never said.
- "Beyond paid media" / internal-tooling bullets a client wouldn't care about.
- Full status table of healthy pages; YoY decline with no context; market rows split
  by channel; sections nobody asked for (headroom, lead-arrival); orphaned footer page;
  colored print background; system fonts in PDFs.
