#!/usr/bin/env python3
"""
Roofing Force — Google Ads daily report.
Pulls yesterday + last-7-day performance, search terms with junk flagging,
keyword QS, budget pacing, and posts to Discord (summary + HTML attachment).

Usage: python3 daily_report.py [--no-discord]
Outputs: out/report-YYYY-MM-DD.html and out/report-YYYY-MM-DD.txt
"""
import os, re, sys, json, html
from datetime import date, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import google_ads_client, CUSTOMER_ID, ACCOUNT_NAME, DISCORD_WEBHOOK, BASE_DIR

TZ = ZoneInfo("America/Denver")
OUT_DIR = os.path.join(BASE_DIR, "out")

# ---------- junk-term flagging (roofing lead-gen) ----------
# Flag patterns that signal non-customer intent. Kept conservative:
# "free"/"repair" alone are NOT junk (free inspection / roof repair are lead terms).
JUNK_PATTERNS = [
    (r"\b(jobs?|hiring|careers?|salary|salaries|apprentice(ship)?|employment|resume)\b", "job seeker"),
    (r"\b(training|certification|certified course|classes?|school|course|license requirements?)\b", "training/edu"),
    (r"\b(diy|do it yourself|yourself|how to (install|replace|repair|fix|shingle))\b", "DIY"),
    (r"\b(kit|kits|supply|supplies|supplier|wholesale|distributor|for sale|prices? per (square|bundle|sheet)|home depot|lowe'?s|menards)\b", "materials/retail"),
    (r"\b(calculator|software|template|invoice|app)\b", "tools/software"),
    (r"\b(rental|rent a|used|craigslist|facebook marketplace)\b", "marketplace"),
    (r"\b(what is|definition|meaning|wiki|history of)\b", "informational"),
    (r"\b(insurance adjuster (job|training|salary)|become an? adjuster)\b", "adjuster career"),
]
# never flag if these appear (real lead intent)
SAFE_OVERRIDES = r"\b(estimate|quote|inspection|contractor|company|companies|near me|repair service|replace my|my roof|leak)\b"

def junk_reason(term):
    t = term.lower()
    for pat, reason in JUNK_PATTERNS:
        if re.search(pat, t):
            if re.search(SAFE_OVERRIDES, t) and reason in ("informational",):
                continue
            return reason
    return None

# ---------- GAQL ----------
def gaql_rows(client, query):
    svc = client.get_service("GoogleAdsService")
    return list(svc.search(customer_id=CUSTOMER_ID, query=query))

def money(micros):
    return micros / 1_000_000

def fmt_usd(x, dec=0):
    return f"${x:,.{dec}f}"

def pct(x):
    return f"{x*100:.0f}%" if x is not None else "—"

def fetch_all(client, d_yest, d_7_start, d_prev7_start, d_prev7_end):
    data = {}

    # campaign daily rows, last 14 days
    q = f"""
      SELECT campaign.id, campaign.name, campaign.status,
             campaign_budget.amount_micros, campaign.bidding_strategy_type,
             campaign.maximize_conversions.target_cpa_micros,
             campaign.target_impression_share.location_fraction_micros,
             segments.date, metrics.cost_micros, metrics.clicks, metrics.impressions,
             metrics.conversions, metrics.conversions_value
      FROM campaign
      WHERE segments.date BETWEEN '{d_prev7_start}' AND '{d_yest}'
        AND campaign.status IN ('ENABLED','PAUSED')
    """
    data["campaign_daily"] = gaql_rows(client, q)

    # disapproved ads (enabled ads in enabled campaigns)
    q = """
      SELECT campaign.name, ad_group_ad.policy_summary.approval_status
      FROM ad_group_ad
      WHERE ad_group_ad.status = 'ENABLED' AND campaign.status = 'ENABLED'
        AND ad_group.status = 'ENABLED'
    """
    try:
        data["ads_policy"] = gaql_rows(client, q)
    except Exception:
        data["ads_policy"] = []

    # impression share, last 7 days aggregate (enabled only)
    q = f"""
      SELECT campaign.id, campaign.name,
             metrics.search_impression_share,
             metrics.search_rank_lost_impression_share,
             metrics.search_budget_lost_impression_share
      FROM campaign
      WHERE segments.date BETWEEN '{d_7_start}' AND '{d_yest}'
        AND campaign.status = 'ENABLED'
    """
    try:
        data["imp_share"] = gaql_rows(client, q)
    except Exception:
        data["imp_share"] = []

    return data

def aggregate(data, d_yest, d_7_start, d_prev7_start, d_prev7_end):
    camps = {}
    for r in data["campaign_daily"]:
        cid = r.campaign.id
        if cid not in camps:
            btype = r.campaign.bidding_strategy_type.name
            tcpa = money(r.campaign.maximize_conversions.target_cpa_micros)
            tis = r.campaign.target_impression_share.location_fraction_micros
            if btype == "MAXIMIZE_CONVERSIONS":
                bid_label = f"tCPA ${tcpa:,.0f}" if tcpa else "Max Conversions (no target)"
            elif btype == "TARGET_IMPRESSION_SHARE":
                bid_label = f"Target Impr. Share {tis/10000:.0f}%" if tis else "Target Impr. Share"
            else:
                bid_label = btype.replace("_", " ").title()
            camps[cid] = {
                "name": r.campaign.name, "status": r.campaign.status.name,
                "budget": money(r.campaign_budget.amount_micros),
                "bidding": btype, "bid_label": bid_label,
                "yest": defaultdict(float), "last7": defaultdict(float), "prev7": defaultdict(float),
            }
        c = camps[cid]
        d = str(r.segments.date)
        buckets = []
        if d == str(d_yest): buckets.append("yest")
        if str(d_7_start) <= d <= str(d_yest): buckets.append("last7")
        if str(d_prev7_start) <= d <= str(d_prev7_end): buckets.append("prev7")
        for b in buckets:
            c[b]["cost"] += money(r.metrics.cost_micros)
            c[b]["clicks"] += r.metrics.clicks
            c[b]["impr"] += r.metrics.impressions
            c[b]["conv"] += r.metrics.conversions
            c[b]["value"] += r.metrics.conversions_value

    # attach impression share
    is_by_id = {r.campaign.id: r for r in data["imp_share"]}
    for cid, c in camps.items():
        r = is_by_id.get(cid)
        c["is"] = r.metrics.search_impression_share if r else None
        c["lost_rank"] = r.metrics.search_rank_lost_impression_share if r else None
        c["lost_budget"] = r.metrics.search_budget_lost_impression_share if r else None

    # drop campaigns with zero activity in the whole window
    camps = {k: v for k, v in camps.items()
             if v["last7"]["cost"] > 0 or v["prev7"]["cost"] > 0 or v["status"] == "ENABLED"}

    # account-level daily series (all campaigns, last 14 days ascending)
    by_day = defaultdict(lambda: {"cost": 0.0, "conv": 0.0})
    for r in data["campaign_daily"]:
        d = str(r.segments.date)
        by_day[d]["cost"] += money(r.metrics.cost_micros)
        by_day[d]["conv"] += r.metrics.conversions
    daily = [{"date": d, **by_day[d]} for d in sorted(by_day)]

    terms_yest = []

    # disapproved ads count per campaign
    disapproved = defaultdict(int)
    for r in data.get("ads_policy", []):
        if r.ad_group_ad.policy_summary.approval_status.name == "DISAPPROVED":
            disapproved[r.campaign.name] += 1

    return camps, daily, terms_yest, dict(disapproved)

def load_campaign_notes():
    import json
    path = os.path.join(BASE_DIR, "campaign_notes.json")
    try:
        return json.load(open(path))
    except Exception:
        return {}

def build_alerts(camps):
    """Structured alerts: level in critical/serious/warning/good/info."""
    from datetime import datetime as _dt
    notes_cfg = load_campaign_notes()
    today_s = _dt.now(TZ).date().isoformat()
    alerts = []
    def add(level, msg): alerts.append({"level": level, "msg": msg})
    for c in camps.values():
        if c["status"] != "ENABLED":
            continue
        y, l7 = c["yest"], c["last7"]
        name = c["name"]
        cfg = notes_cfg.get(name, {})
        muted = cfg.get("mute_pacing_until", "") >= today_s
        note_suffix = f" — {cfg['note']}" if cfg.get("note") else ""
        if c["budget"] > 0 and y["cost"] == 0 and l7["cost"] > 0:
            add("critical", f"{name}: spent $0 yesterday (budget {fmt_usd(c['budget'])}/day){note_suffix}")
        elif c["budget"] > 0 and y["cost"] < 0.3 * c["budget"] and l7["cost"] > 0:
            add("info" if muted else "serious",
                f"{name}: only {fmt_usd(y['cost'])} of {fmt_usd(c['budget'])}/day yesterday ({y['cost']/c['budget']*100:.0f}% of budget){note_suffix}")
        if y["conv"] > 0 and l7["conv"] > 0:
            cpl_y = y["cost"] / y["conv"]; cpl_7 = l7["cost"] / l7["conv"]
            if cpl_7 > 0 and cpl_y > 1.5 * cpl_7 and y["cost"] > 50:
                add("warning", f"{name}: yesterday CPL {fmt_usd(cpl_y)} vs 7-day avg {fmt_usd(cpl_7)}")
        if y["cost"] > 75 and y["conv"] == 0:
            add("warning", f"{name}: {fmt_usd(y['cost'])} spent yesterday with 0 conversions")
        if c["lost_rank"] and c["lost_rank"] > 0.6:
            add("info", f"{name}: losing {pct(c['lost_rank'])} of impressions to rank (7d) — bids/QS, not budget")
        if c["lost_budget"] and c["lost_budget"] > 0.25:
            add("good", f"{name}: losing {pct(c['lost_budget'])} of impressions to budget (7d) — raise budget to scale")
    order = {"critical": 0, "serious": 1, "warning": 2, "good": 3, "info": 4}
    return sorted(alerts, key=lambda a: order[a["level"]])

ALERT_EMOJI = {"critical": "🔴", "serious": "🟠", "warning": "🟡", "good": "🟢", "info": "ℹ️"}

def delta_str(new, old):
    if old == 0:
        return "new" if new > 0 else "—"
    d = (new - old) / old * 100
    arrow = "▲" if d > 0 else ("▼" if d < 0 else "•")
    return f"{arrow}{abs(d):.0f}%"

# ---------- rendering ----------
def render_text(run_date, camps, alerts):
    L = []
    enabled = [c for c in camps.values() if c["status"] == "ENABLED"]
    tot = {b: {k: sum(c[b][k] for c in enabled) for k in ("cost","clicks","conv","value")} for b in ("yest","last7","prev7")}
    cpl_y = tot['yest']['cost']/tot['yest']['conv'] if tot['yest']['conv'] else 0
    cpl_7 = tot['last7']['cost']/tot['last7']['conv'] if tot['last7']['conv'] else 0
    L.append(f"Yesterday: {fmt_usd(tot['yest']['cost'])} spend · {tot['yest']['conv']:.0f} conv · CPL {fmt_usd(cpl_y)}")
    L.append(f"Last 7d: {fmt_usd(tot['last7']['cost'])} ({delta_str(tot['last7']['cost'], tot['prev7']['cost'])}) · {tot['last7']['conv']:.0f} conv ({delta_str(tot['last7']['conv'], tot['prev7']['conv'])}) · CPL {fmt_usd(cpl_7)}")
    for a in alerts[:6]:
        L.append(f"{ALERT_EMOJI[a['level']]} {a['msg']}")
    return "\n".join(L), tot

# ---------- discord ----------
def post_discord(run_date, camps, alerts, tot, html_path):
    import discord_post as dp
    cpl_y = tot['yest']['cost']/tot['yest']['conv'] if tot['yest']['conv'] else 0
    cpl_7 = tot['last7']['cost']/tot['last7']['conv'] if tot['last7']['conv'] else 0
    worst = alerts[0]['level'] if alerts else 'good'
    color = {'critical': dp.RED, 'serious': dp.ORANGE, 'warning': dp.YELLOW}.get(worst, dp.GREEN)
    alert_lines = "\n".join(f"{ALERT_EMOJI[a['level']]} {a['msg']}" for a in alerts[:5]) or "None — clean day."
    embed = {
        "title": f"{ACCOUNT_NAME} — Daily · {run_date}",
        "color": color,
        "fields": [
            {"name": "Yesterday", "value": f"**{fmt_usd(tot['yest']['cost'])}** · {tot['yest']['conv']:.0f} leads · CPL {fmt_usd(cpl_y)}", "inline": True},
            {"name": "Last 7 days", "value": f"**{fmt_usd(tot['last7']['cost'])}** ({delta_str(tot['last7']['cost'], tot['prev7']['cost'])}) · {tot['last7']['conv']:.0f} leads · CPL {fmt_usd(cpl_7)}", "inline": True},
            {"name": "Alerts", "value": alert_lines[:1024], "inline": False},
        ],
        "footer": {"text": "Full breakdown in the attached report"},
    }
    return dp.post(DISCORD_WEBHOOK, embed=embed)

def main():
    no_discord = "--no-discord" in sys.argv
    from datetime import datetime
    today = datetime.now(TZ).date()  # Denver-local "today"
    d_yest = today - timedelta(days=1)
    d_7_start = today - timedelta(days=7)
    d_prev7_start = today - timedelta(days=14)
    d_prev7_end = today - timedelta(days=8)

    client = google_ads_client()
    data = fetch_all(client, d_yest, d_7_start, d_prev7_start, d_prev7_end)
    camps, daily, terms_yest, disapproved = aggregate(data, d_yest, d_7_start, d_prev7_start, d_prev7_end)
    alerts = build_alerts(camps)
    for cname, n in disapproved.items():
        alerts.insert(0, {"level": "critical", "msg": f"{cname}: {n} disapproved ad(s) — fix in Ads UI"})
    urgent = [a for a in alerts if a["level"] in ("critical", "serious")]
    notes_ = [a for a in alerts if a["level"] not in ("critical", "serious")]

    os.makedirs(OUT_DIR, exist_ok=True)
    run = str(today)
    text, tot = render_text(run, camps, alerts)
    import render_html as rh
    html_out = rh.render(run, ACCOUNT_NAME, "329-848-8566", camps, urgent, notes_, daily, terms_yest)
    txt_path = os.path.join(OUT_DIR, f"report-{run}.txt")
    html_path = os.path.join(OUT_DIR, f"report-{run}.html")
    with open(txt_path, "w") as f: f.write(text)
    with open(html_path, "w") as f: f.write(html_out)
    print(text)
    print(f"\n[saved] {html_path}")
    if not no_discord:
        posted = post_discord(run, camps, alerts, tot, html_path)
        print(f"[discord] {'posted OK' if posted else 'FAILED'}")
    return html_path

if __name__ == "__main__":
    main()
