#!/usr/bin/env python3
"""
DNI cross-check — read-only diagnostic. Changes nothing in Google Ads.

Question it answers: were the St. Louis and Mena campaigns actually sending
traffic during the window in which their DNI numbers were live? If they were,
and no calls on those DNI numbers reached the Leads spine, the number swap is
not firing and the problem is landing-page / CTM config, not the Source Map.

Two windows, on purpose:
  A  2026-07-23 .. 2026-08-03   DNI live, but Leads has no call rows at all.
                                Platform side only. Tells us whether these
                                markets were live at all.
  B  2026-08-04 .. 2026-08-12   Both sides have data. This is the comparison
                                that settles it.

Note on conversions: the aggregate Conversions column is NOT used for calls.
The 2026-07-31 "Calls from ads" Primary -> Secondary demotion falls inside
window A, so calls drop out of that column on 07-31 and a market would look
like it went dark on a day nothing happened to it. This reads
all_conversions segmented by conversion action name instead, which the
primary/secondary setting does not affect.

Usage:  python3 dni_check.py
"""
import os, sys, csv
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from config import google_ads_client, CUSTOMER_ID, ACCOUNT_NAME, BASE_DIR

WINDOWS = [
    ("A  07-23..08-03  (DNI live, no Leads call rows)", "2026-07-23", "2026-08-03"),
    ("B  08-04..08-12  (both sides have data)",         "2026-08-04", "2026-08-12"),
]

OUT_DIR = os.path.join(BASE_DIR, "out")


def run(svc, query):
    rows = []
    for batch in svc.search_stream(customer_id=CUSTOMER_ID, query=query):
        for r in batch.results:
            rows.append(r)
    return rows


def traffic(svc, start, end):
    # Explicit BETWEEN. DURING LAST_90_DAYS is invalid in this API version.
    q = f"""
      SELECT campaign.name, campaign.status, segments.date,
             metrics.impressions, metrics.clicks, metrics.cost_micros
      FROM campaign
      WHERE segments.date BETWEEN '{start}' AND '{end}'
        AND campaign.status != 'REMOVED'
    """
    agg = defaultdict(lambda: {"impr": 0, "clicks": 0, "cost": 0.0, "days": set()})
    for r in run(svc, q):
        a = agg[r.campaign.name]
        a["impr"] += r.metrics.impressions
        a["clicks"] += r.metrics.clicks
        a["cost"] += r.metrics.cost_micros / 1_000_000
        if r.metrics.impressions:
            a["days"].add(r.segments.date)
    return agg


def conversions(svc, start, end):
    q = f"""
      SELECT campaign.name, segments.conversion_action_name,
             metrics.all_conversions
      FROM campaign
      WHERE segments.date BETWEEN '{start}' AND '{end}'
        AND campaign.status != 'REMOVED'
    """
    agg = defaultdict(float)
    for r in run(svc, q):
        if r.metrics.all_conversions:
            agg[(r.campaign.name, r.segments.conversion_action_name)] += r.metrics.all_conversions
    return agg


def main():
    client = google_ads_client()
    svc = client.get_service("GoogleAdsService")

    os.makedirs(OUT_DIR, exist_ok=True)
    csv_path = os.path.join(OUT_DIR, "dni-check.csv")
    out_rows = []

    print(f"\n{ACCOUNT_NAME} — DNI cross-check (read-only)")
    print(f"customer {CUSTOMER_ID}\n")

    for label, start, end in WINDOWS:
        print("=" * 78)
        print(label)
        print("=" * 78)

        tr = traffic(svc, start, end)
        cv = conversions(svc, start, end)

        if not tr:
            print("  no campaign rows returned for this window\n")
            continue

        print(f"\n  {'campaign':<44} {'impr':>8} {'clicks':>7} {'cost':>10} {'active':>7}")
        print(f"  {'-'*44} {'-'*8} {'-'*7} {'-'*10} {'-'*7}")
        for name in sorted(tr, key=lambda n: -tr[n]["clicks"]):
            a = tr[name]
            print(f"  {name[:44]:<44} {a['impr']:>8,} {a['clicks']:>7,} "
                  f"${a['cost']:>9,.2f} {len(a['days']):>5}d")
            out_rows.append({
                "window": label.split()[0], "start": start, "end": end,
                "campaign": name, "impressions": a["impr"], "clicks": a["clicks"],
                "cost": round(a["cost"], 2), "active_days": len(a["days"]),
                "conversion_action": "", "all_conversions": "",
            })

        # conversion actions, so call actions are visible by name rather than
        # collapsed into a Conversions column the 07-31 demotion changed
        if cv:
            print(f"\n  conversion actions (all_conversions, demotion-proof)")
            print(f"  {'campaign':<34} {'action':<30} {'conv':>7}")
            print(f"  {'-'*34} {'-'*30} {'-'*7}")
            for (name, action) in sorted(cv, key=lambda k: -cv[k]):
                print(f"  {name[:34]:<34} {action[:30]:<30} {cv[(name, action)]:>7.1f}")
                out_rows.append({
                    "window": label.split()[0], "start": start, "end": end,
                    "campaign": name, "impressions": "", "clicks": "",
                    "cost": "", "active_days": "",
                    "conversion_action": action,
                    "all_conversions": round(cv[(name, action)], 2),
                })
        else:
            print("\n  no conversions recorded in this window")
        print()

    if out_rows:
        with open(csv_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
            w.writeheader()
            w.writerows(out_rows)
        print(f"csv written: {csv_path}\n")


if __name__ == "__main__":
    main()
