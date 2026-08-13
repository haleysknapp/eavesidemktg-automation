# Roofing Force — How Conversions Land in Meta

Reference doc. **Last verified 2026-08-13** by live Test Events run, not by inference.
Everything below feeds **one** pixel dataset: **1110006736001318**.
Ad set for `RF | Leads | 2026-08 Launch 01` optimizes on **Lead** in that dataset.

---

## The short version

**One conversion = one `Lead` event.** Two things produce it:

| | What counts | Action source | Filtered to Facebook? |
|---|---|---|---|
| **Form** | A completed form submission on roofingforce.com | `website` | **No** — every submit sitewide fires |
| **Call** | A qualified call to the Facebook number | `phone_call` | **Yes** — number + source filtered |

Both land in the same dataset on purpose, so the optimizer learns from one combined
signal instead of two fragmented ones.

**Firing ≠ attributing.** The pixel records every conversion from every source. Meta
only *credits* the ones it can tie to an ad click via the `fbclid` → `_fbc` cookie
inside the attribution window. Ads Manager's Results column shows Facebook-attributed
leads only. Do not read the pixel's raw `Lead` total as "Facebook leads" — it's a mix
of all-source form fills and Facebook-only calls.

---

## The thread that ties it together: the click ID

1. Someone clicks the ad → lands with `fbclid=xxxx` appended by Meta.
2. The pixel reads it and stores it in a first-party `_fbc` cookie.
3. Every event afterward — browser or server — carries `_fbc`.
4. Meta maps `_fbc` → the original click → **ad → ad set → campaign**.

This is why UTMs/fbclid on the ad URLs matter for everything, calls included. No click
ID and no matched personal data = an event Meta records but cannot attribute.

---

## Lane 1 — Form Lead (browser pixel)

**VERIFIED 2026-08-13 by live test.** Test code `TEST20276`, submitted on
`/kansas-city-roofing/?fbclid=capitest813&utm_source=facebook&utm_medium=paid`.

What actually fired:

| Time | Event | From | Setup method |
|---|---|---|---|
| 10:07:25 | PageView | Browser | Partner integration |
| 10:17:25 | Form | Browser | Partner integration |
| 10:17:25 | SubscribedButtonClick | Browser | *(automatic)* |
| **10:17:25** | **Lead** | **Browser** | **Partner integration** |
| 10:17:47 | PageView (`/thank-you/`) | Browser | Partner integration |

The `Lead` carried:

- **Action source:** website
- **Advanced matching:** Email, First name, Last name, Phone, ZIP code, IP address, User agent
- **Parameter:** `cs_est: true`
- **Event ID:** *(blank)*

**Why the definition is sound:** nothing fired on page load, and nothing fired while
the form sat there. `Lead` appeared at the exact second the submit went through —
after Turnstile passed, before the thank-you redirect. It counts completed
submissions, not attempts.

**What fires it:** "Partner integration" — the WordPress plugin PixelYourSite
(v11.2.0.7), on form success. Not GTM. Neither GTM container holds a Meta tag:

| Container | Live version | Contents |
|---|---|---|
| GTM-MP6JL7CF (on the site) | v2, 06/17/2026, haley@eaveside.com | 2 tags: CTM Call Tracking, Google Tag GA4+Ads |
| GTM-TMLXVWP (old, Lemonhead) | v24, 07/26/2024 | 12 tags — UET, Bing, CallRail, GA4, phone clicks. No Meta tag. |

**`tel:` clicks are NOT counted as Lead** — so no double-count against the call lane.

---

## Lane 2 — Conversions API (server-side)

Events POSTed server-to-server to `graph.facebook.com/{pixel_id}/events` with an
access token, carrying hashed identifiers. Survives ad blockers and Safari/ITP.

**Current state:** the only server-side lane in operation is the call bridge below.
**Form Leads are browser-only — there is no server-side copy of them.**

---

## Lane 3 — Call Lead (CTM → Cloudflare Worker → CAPI)

Built 2026-08-11. **Verified running 2026-08-13**: Cloudflare metrics, last 24h —
13 invocations, 0 errors, active deployment `03829c1c` at 100% traffic, median CPU
1.93ms, and an outbound subrequest to `graph.facebook.com` returning **2xx in 230ms**.
That outbound 200 is Meta accepting a conversion.

Low volume is expected and correct: it filters to Facebook-attributed calls only, and
the campaign hasn't launched.

**Flow:** call to **(913) 565-4470** → clears the talk-time floor → CTM webhooks the
Worker → Worker POSTs `Lead` with `action_source: phone_call`, SHA-256 hashed caller
phone, plus click data when CTM captured it. Deduped on the CTM call id.

**Why CTM's own integration isn't used:** it posts to Meta's Offline Conversions API,
removed at v17, and returns HTTP 400 `(#21018)` on every send. The Worker replaced it.
The offline event set (1070553458860276) still shows AUTO-checked on the ads —
harmless, nothing writes to it.

### Where Lane 3 lives

| Thing | Where |
|---|---|
| Running worker | Cloudflare account **Haleysknapp@gmail.com** (id `a8cda316b210cae5c6051ad6051ccc44`) → Workers & Pages → **ctm-capi-bridge** → `ctm-capi-bridge.eaveside.workers.dev` |
| Deploy method | **Wrangler CLI, manual.** Not Git-connected, not auto-deployed. |
| Source (canonical) | `ctm-capi-bridge/` in `github.com/haleysknapp/eavesidemktg-automation` — committed 2026-08-13 as `19ae38c` |
| Source (original) | Mac: `Roofing Agency/Meta Creative Engine/output/roofing-force/ctm-capi/` + a `ctm-capi-bridge.zip` backup alongside |
| README | `ctm-capi-bridge/README.md` — 5.4KB, covers token, deploy, secrets, CTM setup, DEBUG mode, re-test. **Read this before touching the worker.** |
| Config | `wrangler.toml` — `PIXEL_ID`, `FB_NUMBERS`, `FB_SOURCE_REGEX`, talk-time bars, business hours, voicemail rules, `DEBUG` |
| Secrets | `META_ACCESS_TOKEN`, `WEBHOOK_SECRET` — set via `wrangler secret put`. In no file. |
| Webhook | `https://ctm-capi-bridge.eaveside.workers.dev/hook/<WEBHOOK_SECRET>` — CTM → Settings → Integrations → Webhooks, trigger = end of call |
| Dedupe key | `event_id = ctm-<CTM call id>` |

**Talk-time bars:** 20s in business hours, 40s outside. Two bars because the tracking
number forwards to RF's own line, so voicemail sits downstream of CTM and a machine
answering is byte-identical to a human answering. RF's greeting runs ~27s, so a
beep-and-hangup reads as 28–30s while a real 13s message reads as 40s. If the greeting
length changes: `MIN_DURATION_SEC_CLOSED = greeting + 13`.

**Numbers:** (913) 565-4470 = Facebook ads · (913) 298-6116 = organic FB page only ·
(913) 270-5440 = raw header/footer for non-Facebook traffic.

---

## Known issues (none block launch)

| Issue | Detail | Fix |
|---|---|---|
| **Event coverage 0%** | No browser Lead has a matching CAPI copy. Forms are browser-only. Meta diagnostic raised Aug 11. | Send a server-side copy of the form Lead |
| **Event ID blank on Lead** | Confirmed in the live test. No dedupe key exists. | Any server-side copy **must** carry a shared `event_id` or every lead double-counts |
| **Event match quality 3.4/10** | Low. Weakens attribution and optimization. | Improves with server-side coverage |
| **Lead URL is the bare domain** | Reports `https://roofingforce.com/`, not the page. | Page-scoped custom conversions can't be built off the Lead URL |
| **Second website on the pixel** | `wordpress-1634150-6537777.cloud…` (Cloudways) — 72 events in 28 days vs roofingforce.com's 2.5K | Confirm what it is; a non-production domain writing into the production pixel |
| **Old GTM container still published** | GTM-TMLXVWP holds a CallRail tag and its own CTM tracking code. If it still loads, CTM is injected twice. | Confirm which containers load, retire the old one |
| **"Phone Leads (CTM)" custom conversion** | Created 8/11, 0 events, and it was unclear whether its filter matches `phone_call` events at all | Re-check now that calls are flowing |
| **Ledger undercounts web leads** | Marketing Metrics showed 9 Web leads vs Meta's 74 for the same window. `Web Leads (auto)` is empty; the Formidable reconciler is inert (`FR_FIELD_MAP` all null). | Reporting problem, not a tracking problem |

---

## Reading the numbers correctly

- **Ads Manager → Results** = Facebook-attributed leads. This is the number that
  answers "did Facebook work."
- **Events Manager → Lead total** = all-source form fills + Facebook-only calls. Never
  read this as Facebook performance.
- **"Phone Leads (CTM)" custom conversion** = the call split, once verified.

---

## How to re-run this test later

1. Events Manager → pixel 1110006736001318 → **Test events** → channel **Website**.
2. Expand "Confirm your website's events are set up correctly", paste the lander URL
   with `?fbclid=test123&utm_source=facebook&utm_medium=paid`, click **Test Events**.
3. Submit the form in the tab it opens (a human has to do the Turnstile captcha).
4. Watch for `Lead` — check action source, advanced matching parameters, and Event ID.
5. **Delete the test entry** from Formidable and anywhere it syncs.
