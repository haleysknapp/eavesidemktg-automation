# docs/

Working documents that describe how the automation is set up and what is coming next.
Mirrored from Haley's Mac at
`Roofing Agency/01 Clients/Roofing Force/11 Tracking & Attribution/`, so they survive a
disk failure and carry a diff history.

| File | What it is |
|---|---|
| `RF-Meta-API-Token-SETUP.md` | How to generate and replace the Meta **reporting** token (`meta_access_token` in `mktg-bot/gads-report/.env`). Read this before touching that credential. Contains no secret values. |
| `PROMPT-meta-lead-ingestion.md` | Handoff prompt for the next piece of Meta work: getting Facebook leads ingested, attributed and call-graded in Marketing Metrics the way Google Ads and LSA leads already are. Scoped 2026-08-13, not started. |

Related docs that live next to the code they describe rather than here:

- `ctm-capi-bridge/META-CONVERSION-TRACKING-REFERENCE.md` — how Meta conversions actually
  work. Verified by live test, not inferred.
- `ctm-capi-bridge/README.md` — the CTM → CAPI worker: token, deploy, secrets, re-test.
- `SYSTEM.md`, `SOURCE-MAP.md`, `SHEETS-PLAN.md`, `CONTRADICTIONS.md` at the repo root.

**If you edit one of these, update the copy on Haley's Mac too** — she reads them from the
client folder, not from here.
