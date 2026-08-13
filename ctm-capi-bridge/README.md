# CTM → Meta Conversions API bridge

Replaces CallTrackingMetrics' built-in Facebook integration, which posts to the
**Offline Conversions API that Meta deprecated at v17**. Every send from CTM
currently fails:

```
(#21018) Offline Conversions API is deprecated from v17 onwards.
Please use Conversions API.
```

CTM offers no Conversions API version of that integration, so calls reach Meta
through this worker instead.

**What changes:** qualified Facebook calls arrive at pixel `1110006736001318` —
the same pixel the ad set optimizes on — as `Lead` events with
`action_source: "phone_call"`. Meta can finally count a phone call as a
conversion, so call-driven ads become optimizable.

---

## What it does and does not send

Two filters, both on purpose.

**Attribution.** Only calls that came in on a Facebook tracking number
(`FB_NUMBERS`) or whose CTM source matches `FB_SOURCE_REGEX`. Sending every
Google and organic call would let Meta claim credit for calls it never caused,
which quietly corrupts the numbers you use to judge the channel.

**Quality.** Calls under `MIN_DURATION_SEC` (default 60) are dropped as wrong
numbers and hangups — unless CTM has already flagged the call a conversion, in
which case that judgment wins. Sending 12-second hangups teaches Meta to find
more people who hang up.

Skipped calls return **200**, not an error, so CTM does not retry them.

**Privacy.** Phone, name, city, state and ZIP are SHA-256 hashed before the
request leaves the worker, per Meta's normalization rules (lowercased, stripped,
phone as digits-only E.164). Raw values are never transmitted. The test suite
asserts this.

**Dedupe.** `event_id` is `ctm-<call id>`. Retries can't double-count, and if a
caller also submits the website form, Meta collapses them.

---

## Setup

### 1. Get a Conversions API token

In Events Manager → the **Roofing Force Pixel** → **Settings** → scroll to
*Conversions API* → **Generate access token**.

Copy it. This is the one step nobody else can do for you — the token grants
write access to the pixel, so treat it like a password. It goes into Cloudflare
as a secret and is never committed.

### 2. Deploy

```bash
cd ctm-capi
npm install
npx wrangler login
npx wrangler deploy
```

Note the deployed URL, e.g. `https://ctm-capi-bridge.<you>.workers.dev`.

### 3. Set the secrets

```bash
npx wrangler secret put META_ACCESS_TOKEN   # paste the token from step 1
npx wrangler secret put WEBHOOK_SECRET      # any long random string
```

Generate a secret with `openssl rand -hex 24`.

Your webhook URL is then:

```
https://ctm-capi-bridge.<you>.workers.dev/hook/<WEBHOOK_SECRET>
```

CTM doesn't sign its webhooks, so that path segment is what stops anyone else
from posting fake conversions into the ad account. Don't paste it anywhere
public.

### 4. Point CTM at it

CTM → **Settings → Integrations → Webhooks** → add a webhook.

| Field | Value |
|---|---|
| URL | your `/hook/<secret>` URL |
| Method | POST |
| Format | JSON |
| Trigger | End of call / *End event with all data ready* |

Use the same trigger point the existing Facebook automation uses, so call
duration and caller data are populated when it fires.

### 5. Confirm the field names

CTM's payload field names vary by account. Before trusting the mapping, run one
call through in debug mode:

```bash
npx wrangler deploy --var DEBUG:1
```

Place a test call, then check `npx wrangler tail` or the CTM webhook log — the
worker echoes the exact payload it received instead of forwarding it. Compare
against the candidate lists in `normalizeCall()` and trim them to what your
account actually sends. Then set `DEBUG = "0"` and redeploy.

### 6. Verify against Meta before it counts

In Events Manager → **Test events**, copy the test code. Add it to
`wrangler.toml`:

```toml
TEST_EVENT_CODE = "TEST12345"
```

Redeploy, place a real call to **(913) 565-4470**, and talk for over a minute.
Within about a minute the event should appear in the Test Events tab as **Lead**,
`phone_call`. Check the match quality Meta reports on it.

Then remove `TEST_EVENT_CODE`, redeploy, and it's live.

### 7. Turn off the broken one

CTM → Settings → Integrations → Facebook → Trigger Setup → **Manage Triggers**,
and disable *Facebook Offline Conversion*. It only generates 400s, and leaving
it on makes the API log useless for spotting real problems.

---

## Checking on it

```bash
npx wrangler tail                          # live logs
curl https://<worker>.workers.dev/health   # config sanity check
```

Every request logs either `CAPI ok <call id>` or `CAPI reject <status>`. A
rejection returns 502 to CTM, so failures also show up in CTM's own API log
rather than disappearing.

Run the tests after any change:

```bash
npm test    # 31 assertions, no network, no deploy
```

---

## Tuning

All in `wrangler.toml`:

| Setting | Default | Notes |
|---|---|---|
| `FB_NUMBERS` | `913-565-4470` | Add the click-to-call number here when call ads launch |
| `FB_SOURCE_REGEX` | `facebook\|meta\|fb` | Fallback when the dialed number isn't listed |
| `MIN_DURATION_SEC` | `60` | Raise if junk still gets through; lower if real leads are being dropped |
| `DEBUG` | `0` | `1` echoes the payload instead of sending |

Watch the skip reasons in the logs for the first week. If real leads are being
filtered out, the reason string tells you which filter did it.
