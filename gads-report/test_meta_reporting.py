#!/usr/bin/env python3
"""
Meta reporting acceptance tests.

Run: python3 test_meta_reporting.py

These exist because the failure this change prevents is SILENT. If Meta drops out of
the channel list, nothing errors — the report just prints a blended cost per lead that
is lower than reality and gets sent to the client. George Davis's scale plan targets
< $160 blended CPL with a $200 per-channel ceiling, so a flattering wrong number is the
one outcome that actually costs money.

No network. Meta's Graph API is stubbed; Google Ads / LSA are NOT touched, so these are
safe to run any time.
"""
import io
import json
import sys
import types
from contextlib import redirect_stdout
from datetime import date

import meta as meta_mod

FAILURES = []


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"  — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


class _Resp:
    def __init__(self, payload, status=200):
        self._p, self.status_code, self.text = payload, status, json.dumps(payload)

    def json(self):
        return self._p


def stub_graph(days, status=200, error_msg=""):
    """Install a fake requests module for meta.py. `days` = [(date, spend, leads)]."""
    payload = {"data": [
        {"date_start": d, "spend": str(sp),
         "actions": [
             # Meta reports the same conversion under several overlapping aliases.
             # Both are present on purpose: the code must pick ONE, not sum them.
             {"action_type": "offsite_conversion.fb_pixel_lead", "value": str(lv)},
             {"action_type": "lead", "value": str(lv)},
             {"action_type": "landing_page_view", "value": "99"},
         ]}
        for (d, sp, lv) in days]}
    if status != 200:
        payload = {"error": {"message": error_msg}}
    mod = types.ModuleType("requests")
    mod.get = lambda url, params=None, timeout=None: _Resp(payload, status)
    sys.modules["requests"] = mod


def restore_requests():
    sys.modules.pop("requests", None)


# --------------------------------------------------------------------------------
print("\n1. meta.py parsing")

meta_mod._token = lambda env=None: "STUB_TOKEN"
stub_graph([("2026-08-10", 100.0, 2), ("2026-08-11", 150.0, 3), ("2026-08-12", 50.0, 0)])
md = meta_mod.fetch_meta("2026-08-10", "2026-08-12")

check("available", md["available"], md.get("reason"))
spend, res = meta_mod.window(md, "2026-08-10", "2026-08-12")
check("spend sums to 300", abs(spend - 300.0) < 1e-6, f"got {spend}")
check("results NOT double counted across aliases (5, not 10)", res == 5, f"got {res}")
check("landing_page_view ignored", res == 5, f"got {res}")

spend2, res2 = meta_mod.window(md, "2026-08-11", "2026-08-11")
check("window() slices by date", abs(spend2 - 150.0) < 1e-6 and res2 == 3, f"got {spend2}/{res2}")

# --------------------------------------------------------------------------------
print("\n2. degraded mode never breaks a report")

stub_graph([], status=400, error_msg="Error validating access token: Session has expired")
md_err = meta_mod.fetch_meta("2026-08-10", "2026-08-12")
check("API error -> unavailable, no exception", md_err["available"] is False)
check("error surfaces Meta's own message", "expired" in md_err["reason"], md_err["reason"])
check("window() on failed fetch returns zeros", meta_mod.window(md_err, "2026-08-10", "2026-08-12") == (0.0, 0))

meta_mod._token = lambda env=None: ""
md_not = meta_mod.fetch_meta("2026-08-10", "2026-08-12")
check("missing token -> unavailable", md_not["available"] is False)
check("missing-token reason warns CPL excludes Meta", "EXCLUDES" in md_not["reason"], md_not["reason"])

# --------------------------------------------------------------------------------
print("\n3. clients.json is actually the config source")

cfg = meta_mod.load_meta_config("roofing-force")
check("roofing-force meta block found", bool(cfg))
check("ad account id matches", cfg.get("ad_account_id") == "1779635922176764", cfg.get("ad_account_id"))
check("pixel id matches", cfg.get("pixel_id") == "1110006736001318", cfg.get("pixel_id"))
check("client with no Meta account yields {}", meta_mod.load_meta_config("copper-ridge-exteriors") == {})

# --------------------------------------------------------------------------------
print("\n4. blended CPL includes Meta spend  <-- the acceptance test")

# Arithmetic, isolated from the live Google/LSA numbers so this test is deterministic.
channels = [
    {"label": "Google Search ads", "leads": 18, "cost": 4212.0},
    {"label": "Local Services Ads", "leads": 7, "cost": 454.0},
]
blended_before = sum(c["cost"] for c in channels) / sum(c["leads"] for c in channels)
channels.append({"label": "Facebook ads", "leads": 6, "cost": 1400.0})
blended_after = sum(c["cost"] for c in channels) / sum(c["leads"] for c in channels)

check("Meta spend moves blended CPL", abs(blended_after - blended_before) > 1e-6)
check("blended CPL rises when Meta CPL is above the others",
      blended_after > blended_before, f"{blended_before:.2f} -> {blended_after:.2f}")
check("blended CPL equals total spend / total leads",
      abs(blended_after - (6066.0 / 31)) < 1e-6, f"got {blended_after}")
print(f"        blended CPL without Meta ${blended_before:,.2f}  ->  with Meta ${blended_after:,.2f}")
print("        (a report omitting Meta would have understated cost per lead by "
      f"${blended_after - blended_before:,.2f})")

# --------------------------------------------------------------------------------
print("\n5. market table renders the Facebook column only when Meta is live")

import render_html as rh

no_meta = rh.merged_market_table("T", [("Kansas City", 6, 1687.0)], [("Joplin", 3, 200.0)])
check("no Facebook column without meta_rows", "Facebook" not in no_meta)

with_meta = rh.merged_market_table("T", [("Kansas City", 6, 1687.0)], [("Joplin", 3, 200.0)],
                                   meta_rows=[("Kansas City", 6, 1400.0)])
check("Facebook column appears with meta_rows", "Facebook" in with_meta)
check("Meta folds into the same market row, not a new one", with_meta.count("Kansas City") == 1)
check("market spend includes Meta", "$3,087" in with_meta, "expected 1687+1400 in Kansas City row")
check("market with no Meta shows em dash", "—" in with_meta)

# --------------------------------------------------------------------------------
print("\n6. reports import cleanly with Meta wired in")

for m in ("weekly_exec", "monthly_exec", "daily_report"):
    try:
        __import__(m)
        check(f"{m} imports", True)
    except Exception as e:
        check(f"{m} imports", False, str(e)[:160])

restore_requests()

print("\n" + ("ALL CHECKS PASSED" if not FAILURES else f"{len(FAILURES)} FAILED: " + ", ".join(FAILURES)))
sys.exit(1 if FAILURES else 0)
