"""
Meta (Facebook) Ads data — spend + Facebook-attributed results.

WHAT THIS REPORTS, AND WHY IT IS THE ONLY DEFENSIBLE NUMBER
-----------------------------------------------------------
This module reads the **Ads Manager insights API** (`/act_<id>/insights`), which is
the API-side equivalent of the Results column in Ads Manager. That column counts
Facebook-*attributed* conversions only: Meta credits a Lead when it can tie the
event back to an ad click via the `fbclid` -> `_fbc` cookie inside the attribution
window.

It deliberately does NOT read the pixel's raw `Lead` total from the Events Manager /
Conversions API. Verified 2026-08-13 (see
`ctm-capi-bridge/META-CONVERSION-TRACKING-REFERENCE.md`), that raw total is a mix of:

  * **Form Leads** — fired by the PixelYourSite WordPress plugin on EVERY completed
    form submit on roofingforce.com, from every traffic source, not just Facebook.
  * **Call Leads** — posted by the ctm-capi-bridge Cloudflare Worker, already
    pre-filtered to Facebook-attributed calls only.

Adding those together and calling it "Facebook leads" would overstate Facebook by
every organic and Google-sourced form fill on the site. Firing is not attributing.

It also does NOT read lead counts from the Marketing Metrics ledger: `Web Leads
(auto)` is empty and the Formidable reconciler is inert (`FR_FIELD_MAP` all null),
so that ledger undercounts web-form leads badly — it showed 9 for a window where
Meta recorded 74.

DEDUPLICATION
-------------
Meta's `Lead` events carry no `event_id` today, so no browser/server dedupe is
possible. That only matters if a server-side copy of the form Lead is ever added
(see the reference doc's open items). Ads Manager attribution is unaffected.

DEGRADED MODE
-------------
If `meta_access_token` is absent from .env, every function here returns an empty,
unavailable result and the reports render **exactly** as they did before Meta
existed. That is intentional: a missing token must never break the Friday report,
and must never silently produce a blended CPL that looks better than reality — the
callers check `available` and label the report accordingly.

Config comes from `clients.json` (this is that file's first real runtime consumer).
"""
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BASE_DIR)

GRAPH_VERSION = "v21.0"
GRAPH = f"https://graph.facebook.com/{GRAPH_VERSION}"

# Action types that represent a lead result, in priority order. We take the FIRST
# one present on a given day rather than summing them, because Meta reports the same
# conversion under several overlapping action_type aliases and summing double-counts.
DEFAULT_RESULT_ACTIONS = [
    "offsite_conversion.fb_pixel_lead",
    "onsite_conversion.lead_grouped",
    "lead",
]

# The phrase every report must use when labelling these numbers.
DEFINITION = "Facebook-attributed results from Ads Manager"
DEFINITION_LONG = (
    "Meta figures are Facebook-attributed results from Ads Manager — conversions Meta "
    "could tie back to an ad click. They are not the pixel's raw Lead total, which also "
    "counts website form fills from every other traffic source."
)


def _clients_json_path():
    for p in (os.path.join(REPO_ROOT, "clients.json"),
              os.path.join(os.path.dirname(REPO_ROOT), "clients.json"),
              os.path.join(BASE_DIR, "clients.json")):
        if os.path.exists(p):
            return p
    return None


def load_meta_config(client_key="roofing-force"):
    """Meta block for a client from clients.json. Returns {} when absent/unusable."""
    p = _clients_json_path()
    if not p:
        return {}
    try:
        with open(p) as f:
            d = json.load(f)
    except Exception as e:
        print(f"[meta] could not read clients.json: {str(e)[:200]}")
        return {}
    cfg = (d.get("clients", {}).get(client_key, {}) or {}).get("meta", {}) or {}
    if not cfg.get("ad_account_id"):
        return {}
    return cfg


def _token(env=None):
    if env is None:
        try:
            from config import ENV as env
        except Exception:
            env = {}
    return (env or {}).get("meta_access_token", "").strip()


def _empty(reason):
    return {"daily": {}, "results": [], "available": False, "reason": reason,
            "account_id": None, "definition": DEFINITION}


def fetch_meta(d_start, d_end, client_key="roofing-force", env=None):
    """Daily spend + Facebook-attributed results for a date window.

    Returns {"daily": {"YYYY-MM-DD": spend}, "results": [("YYYY-MM-DD", n)],
             "available": bool, "reason": str, "account_id": str}

    Never raises. On any failure it returns an unavailable result so the caller can
    render the report without Meta rather than crashing the Friday send.
    """
    cfg = load_meta_config(client_key)
    if not cfg:
        return _empty("no Meta ad account configured in clients.json")

    tok = _token(env)
    if not tok:
        return _empty("no meta_access_token in .env — Meta figures omitted, "
                      "blended cost per lead below EXCLUDES Meta spend")

    try:
        import requests
    except Exception:
        return _empty("requests not installed")

    acct = str(cfg["ad_account_id"]).replace("act_", "")
    priority = cfg.get("result_action_types") or DEFAULT_RESULT_ACTIONS

    out = {"daily": defaultdict(float), "results": [], "available": True,
           "reason": "", "account_id": acct, "definition": DEFINITION}

    params = {
        "level": "account",
        "time_increment": 1,
        "time_range": json.dumps({"since": str(d_start), "until": str(d_end)}),
        "fields": "date_start,spend,actions",
        "limit": 500,
        "access_token": tok,
    }
    url = f"{GRAPH}/act_{acct}/insights"
    pages = 0
    try:
        while url and pages < 50:
            r = requests.get(url, params=params if pages == 0 else None, timeout=60)
            if r.status_code != 200:
                # Surface Meta's own message; it is usually precise (expired token,
                # missing ads_read, wrong account).
                msg = ""
                try:
                    msg = r.json().get("error", {}).get("message", "")
                except Exception:
                    msg = r.text[:200]
                return _empty(f"Meta API {r.status_code}: {msg[:220]}")
            body = r.json()
            for row in body.get("data", []):
                d = str(row.get("date_start", ""))[:10]
                if not d:
                    continue
                try:
                    out["daily"][d] += float(row.get("spend") or 0)
                except (TypeError, ValueError):
                    pass
                n = 0
                acts = {a.get("action_type"): a.get("value") for a in (row.get("actions") or [])}
                for want in priority:
                    if want in acts:
                        try:
                            n = int(float(acts[want]))
                        except (TypeError, ValueError):
                            n = 0
                        break
                if n:
                    out["results"].append((d, n))
            url = (body.get("paging") or {}).get("next")
            pages += 1
    except Exception as e:
        return _empty(f"Meta API request failed: {str(e)[:220]}")

    out["daily"] = dict(out["daily"])
    return out


def window(acct, d_start, d_end):
    """Totals for a date window: (spend, results). Mirrors lsa.window()."""
    if not acct:
        return 0.0, 0
    spend = sum(v for d, v in (acct.get("daily") or {}).items()
                if str(d_start) <= str(d) <= str(d_end))
    results = sum(n for (d, n) in (acct.get("results") or [])
                  if str(d_start) <= str(d) <= str(d_end))
    return spend, results


def weekly_buckets(acct, d_end, weeks):
    """{week_ending_date_str: {"cost": x, "conv": n}} for a trailing-weeks trend.
    Bucketing matches weekly_exec.py exactly: wk_idx = (d_end - d).days // 7."""
    buckets = defaultdict(lambda: {"cost": 0.0, "conv": 0.0})
    if not acct:
        return buckets
    for dstr, v in (acct.get("daily") or {}).items():
        d = datetime.strptime(dstr, "%Y-%m-%d").date()
        wk_idx = (d_end - d).days // 7
        if 0 <= wk_idx < weeks:
            buckets[str(d_end - timedelta(weeks=wk_idx))]["cost"] += v
    for (dstr, n) in (acct.get("results") or []):
        d = datetime.strptime(dstr, "%Y-%m-%d").date()
        wk_idx = (d_end - d).days // 7
        if 0 <= wk_idx < weeks:
            buckets[str(d_end - timedelta(weeks=wk_idx))]["conv"] += n
    return buckets


def monthly_buckets(acct):
    """{"YYYY-MM": {"cost": x, "leads": n}} — mirrors monthly_exec's LSA rollup."""
    out = defaultdict(lambda: {"cost": 0.0, "leads": 0})
    if not acct:
        return out
    for dstr, v in (acct.get("daily") or {}).items():
        out[str(dstr)[:7]]["cost"] += v
    for (dstr, n) in (acct.get("results") or []):
        out[str(dstr)[:7]]["leads"] += n
    return out
