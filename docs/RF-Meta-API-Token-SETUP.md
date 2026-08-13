# Meta Marketing API token — the one step only Haley can do

**Written 2026-08-13.** Everything else for Meta reporting is built, tested and
committed. This token is the last thing standing between the code and working Meta
numbers in the Friday and monthly reports.

Until it exists, the reports still run — they just leave Meta out and print a loud
warning saying the blended cost per lead excludes Meta spend.

---

## What you are generating

A **read-only** Meta Marketing API access token with `ads_read` on ad account
`1779635922176764`.

This is **not** the same as the `META_ACCESS_TOKEN` already sitting in the
ctm-capi-bridge Cloudflare Worker. That one *writes* conversion events to the pixel.
This one *reads* spend and results. Keep them separate — different jobs, different
blast radius if one leaks.

---

## Steps

There are two ways to get a token. **Use route A.** Route B is documented at the bottom
only because it is what most Meta tutorials show, and it is the wrong choice here.

### Route A — System User token (never expires) ← DO THIS

**Part 1: create the app (developers.facebook.com/apps).** The app is just a name the
token gets attached to. You configure almost nothing in it.

1. **Create app** → name `Eaveside Reporting`, your contact email.
2. Use case: **Create & manage ads with Marketing API**. Despite the "manage" in the
   name, this only decides which API the app may talk to — what the token can actually
   DO is set by the permissions in Part 2, and you only grant `ads_read`.
3. Business portfolio: the Roofing Force one (`23844115792860155`).
4. Publishing requirements will say **"No requirements identified"** — correct. App
   Review only applies to apps touching other people's data.
5. Finish. **Then stop.** You are done on developers.facebook.com.

   Specifically, IGNORE: "Add product", the Graph API Explorer, "Test use cases",
   the "Unpublished" badge, and "Become a Tech Provider". None apply.

**Part 2: the token (business.facebook.com/settings).** Different site. Left sidebar →
**Users → System users**. If that item is missing you are not a business admin on this
portfolio, or the portfolio switcher (top left) is on the wrong one.

6. **Add** → name `Eaveside Reporting` → role **Employee access** (not Admin; it never
   changes anything).
7. **Assign assets** → **Apps** → `Eaveside Reporting` → **Manage app** → Save.
8. **Assign assets** again → **Ad accounts** → `1779635922176764` → **View performance**
   → Save. Two separate assignments; the picker shows one asset type at a time.
9. **Generate new token** →
   - App: `Eaveside Reporting`
   - **Token expiration: Never**
   - Permissions: tick **`ads_read`** only (use the search box, the list is long)
   - Generate

   Gotchas: the Generate button stays greyed out until at least one permission is
   ticked, and if `ads_read` is not in the list then step 7 did not save.

10. Meta shows the token **once**. Copy it straight into the .env (below). If you lose
    it, just Generate again — that invalidates the previous one.

### Adding another client later

Same system user, no new app and no new token: **Assign assets → Ad accounts →
<the new account> → View performance**. Then add a `meta` block to that client in
`clients.json` mirroring roofing-force's. No code change.

---

## Put it in the .env

One new line at the end:

```
meta_access_token=PASTE_IT_HERE
```

File:
```
Roofing Agency/03 Eaveside Product/automation/eavesidemktg-automation/mktg-bot/gads-report/.env
```
That is the .env the bot actually loads. The top-level `gads-report/` has none and
needs none.

## Confirm it works

```bash
cd "Roofing Agency/03 Eaveside Product/automation/eavesidemktg-automation/mktg-bot/gads-report"
python3 -c "
import meta, datetime as d
r = meta.fetch_meta(d.date.today()-d.timedelta(days=7), d.date.today())
print('available:', r['available'], r.get('reason',''))
print('spend/results:', meta.window(r, d.date.today()-d.timedelta(days=7), d.date.today()))
"
```

`available: True` → done; Meta appears in the next Friday report the moment the campaign
has spend. `available: False` prints Meta's own error, which is usually precise
(expired token, missing `ads_read`, wrong ad account).

Then `bash push.sh`. The .env is gitignored, so the token is not committed.

---

## Route B — Graph API Explorer token (~60 days) — NOT RECOMMENDED

Tools → Graph API Explorer → pick the app → tick `ads_read` → Generate Access Token,
then Access Token Debugger → Extend Access Token.

Only use this if System users is unavailable to you. It expires in about 60 days, and
when it does the reports do not crash — they quietly drop Meta and print the
"blended cost per lead EXCLUDES Meta spend" warning. That is a silent-ish failure on a
weekly client report, which is the whole class of problem this work existed to remove.

---

## Rules that apply to this token

- **Never** paste it into a spreadsheet, a Discord message, or any committed file. The
  Change Log row for this names the file and the variable only.
- If it leaks, revoke it at **Business Settings → Users → System Users → the user →
  Generate new token**, which invalidates the old one.
- `.env` already holds eight other live credentials. It is not backed up anywhere
  except the scheduled-task prompts, which is its own problem worth fixing separately.

---

## What you'll see once it's live

- **Friday leadership report** — a `Facebook ads` row in the By channel table, a
  `Facebook` column in the By market table folded into Kansas City, and a blended cost
  per lead that includes Meta spend.
- **Monthly executive report** — the same, plus Meta in the 13-month trend.
- **Discord daily pulse** — a `Facebook (Meta)` field, on days with Meta spend only.
- **Client PDF** — renders it all without layout breakage; verified at 4 pages.

Every Meta figure is labelled **"Facebook-attributed results from Ads Manager"** —
never the pixel's raw `Lead` total, which also counts form fills from search and direct
traffic.
