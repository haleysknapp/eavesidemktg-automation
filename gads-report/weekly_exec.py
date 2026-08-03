#!/usr/bin/env python3
"""
Roofing Force — weekly leadership report (Fridays).
Combines Google Ads (search) + Local Services Ads into total leads / spend /
blended cost per lead, with channel + market breakouts and a plain-language story.

Usage: python3 weekly_exec.py [--no-discord]
"""
import os, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import google_ads_client, CUSTOMER_ID, ACCOUNT_NAME, DISCORD_WEBHOOK, BASE_DIR
from lsa import fetch_lsa, window as lsa_window
import render_html as rh
import discord_post as dp

TZ = ZoneInfo("America/Denver")
OUT_DIR = os.path.join(BASE_DIR, "out")
TREND_WEEKS = 8

def money(m): return m / 1_000_000

def fetch_ads(client, d_start, d_end):
    svc = client.get_service("GoogleAdsService")
    q = f"""
      SELECT campaign.id, campaign.name, campaign.status, campaign_budget.amount_micros,
             segments.date, metrics.cost_micros, metrics.clicks, metrics.conversions
      FROM campaign
      WHERE segments.date BETWEEN '{d_start}' AND '{d_end}'
        AND campaign.status IN ('ENABLED','PAUSED')
    """
    return list(svc.search(customer_id=CUSTOMER_ID, query=q))

def market(name):
    for suf in (" New Search", " - Search", " Search"):
        if name.endswith(suf):
            return name[: -len(suf)]
    return name

def main():
    no_discord = "--no-discord" in sys.argv
    today = datetime.now(TZ).date()
    d_end = today - timedelta(days=1)
    wk_start = d_end - timedelta(days=6)
    pw_start, pw_end = wk_start - timedelta(days=7), wk_start - timedelta(days=1)
    d_start = d_end - timedelta(weeks=TREND_WEEKS) + timedelta(days=1)

    client = google_ads_client()
    ads_rows = fetch_ads(client, d_start, d_end)
    lsa_data = fetch_lsa(client, d_start, d_end)

    # ---- google ads aggregation ----
    camps, ads_weekly = {}, defaultdict(lambda: {"cost": 0.0, "conv": 0.0})
    for r in ads_rows:
        d = datetime.strptime(str(r.segments.date), "%Y-%m-%d").date()
        cost, conv = money(r.metrics.cost_micros), r.metrics.conversions
        wk_idx = (d_end - d).days // 7
        if wk_idx < TREND_WEEKS:
            ads_weekly[str(d_end - timedelta(weeks=wk_idx))]["cost"] += cost
            ads_weekly[str(d_end - timedelta(weeks=wk_idx))]["conv"] += conv
        c = camps.setdefault(r.campaign.id, {
            "name": r.campaign.name, "status": r.campaign.status.name,
            "wk": defaultdict(float), "pw": defaultdict(float)})
        if wk_start <= d <= d_end:
            c["wk"]["cost"] += cost; c["wk"]["conv"] += conv
        elif pw_start <= d <= pw_end:
            c["pw"]["cost"] += cost; c["pw"]["conv"] += conv

    enabled = sorted([c for c in camps.values() if c["status"] == "ENABLED" and (c["wk"]["cost"] or c["pw"]["cost"])],
                     key=lambda c: -c["wk"]["cost"])
    ads_wk = {k: sum(c["wk"][k] for c in enabled) for k in ("cost", "conv")}
    ads_pw = {k: sum(c["pw"][k] for c in enabled) for k in ("cost", "conv")}

    # ---- lsa aggregation ----
    lsa_wk = {"cost": 0.0, "leads": 0}; lsa_pw = {"cost": 0.0, "leads": 0}
    lsa_rows_out = []
    lsa_weekly = defaultdict(lambda: {"cost": 0.0, "conv": 0.0})
    for name, acct in lsa_data.items():
        s, ch, _tot = lsa_window(acct, wk_start, d_end)
        ps, pch, _ = lsa_window(acct, pw_start, pw_end)
        lsa_wk["cost"] += s; lsa_wk["leads"] += ch
        lsa_pw["cost"] += ps; lsa_pw["leads"] += pch
        lsa_rows_out.append({"name": name, "wk_cost": s, "wk_leads": ch,
                             "pw_cost": ps, "pw_leads": pch})
        for dstr, v in acct["daily"].items():
            d = datetime.strptime(dstr, "%Y-%m-%d").date()
            wk_idx = (d_end - d).days // 7
            if 0 <= wk_idx < TREND_WEEKS:
                lsa_weekly[str(d_end - timedelta(weeks=wk_idx))]["cost"] += v
        for (dstr, charged, _s, _t) in acct["leads"]:
            if not charged: continue
            d = datetime.strptime(dstr, "%Y-%m-%d").date()
            wk_idx = (d_end - d).days // 7
            if 0 <= wk_idx < TREND_WEEKS:
                lsa_weekly[str(d_end - timedelta(weeks=wk_idx))]["conv"] += 1
    lsa_rows_out.sort(key=lambda x: -x["wk_cost"])

    # ---- combined totals ----
    tot_wk = {"leads": ads_wk["conv"] + lsa_wk["leads"], "cost": ads_wk["cost"] + lsa_wk["cost"]}
    tot_pw = {"leads": ads_pw["conv"] + lsa_pw["leads"], "cost": ads_pw["cost"] + lsa_pw["cost"]}
    cpl = tot_wk["cost"] / tot_wk["leads"] if tot_wk["leads"] else 0
    pcpl = tot_pw["cost"] / tot_pw["leads"] if tot_pw["leads"] else 0
    ads_cpl = ads_wk["cost"] / ads_wk["conv"] if ads_wk["conv"] else 0
    lsa_cpl = lsa_wk["cost"] / lsa_wk["leads"] if lsa_wk["leads"] else 0

    weeks_sorted = sorted(set(list(ads_weekly) + list(lsa_weekly)))
    spend_series = [ads_weekly[w]["cost"] + lsa_weekly[w]["cost"] for w in weeks_sorted]
    lead_series = [ads_weekly[w]["conv"] + lsa_weekly[w]["conv"] for w in weeks_sorted]

    # ---- narrative ----
    story = []
    dl = (tot_wk["leads"] - tot_pw["leads"]) / tot_pw["leads"] * 100 if tot_pw["leads"] else 0
    ds = (tot_wk["cost"] - tot_pw["cost"]) / tot_pw["cost"] * 100 if tot_pw["cost"] else 0
    story.append(f"Across Google Search ads and Local Services Ads, the account generated {tot_wk['leads']:.0f} leads "
                 f"this week on {rh.fmt_usd(tot_wk['cost'])} of total ad spend — {rh.fmt_usd(cpl)} per lead"
                 + (f", vs {tot_pw['leads']:.0f} leads at {rh.fmt_usd(pcpl)} last week." if tot_pw["leads"] else "."))
    story.append(f"Search ads drove {ads_wk['conv']:.0f} leads at {rh.fmt_usd(ads_cpl)} each; "
                 f"Local Services Ads added {lsa_wk['leads']:.0f} at {rh.fmt_usd(lsa_cpl)} each.")
    if ds > 15 and dl >= 0:
        story.append(f"Spend is scaling up ({ds:+.0f}% week over week) and lead volume is keeping pace ({dl:+.0f}%) — "
                     "budget increases are converting into real leads, not just higher costs.")
    elif ds > 15 and dl < 0:
        story.append(f"Spend rose {ds:+.0f}% but leads dipped {dl:.0f}% — normal wobble while campaigns re-learn "
                     "after budget changes; we're watching cost per lead closely.")
    best = max((c for c in enabled if c["wk"]["conv"] > 0), key=lambda c: c["wk"]["conv"], default=None)
    if best:
        bcpl = best["wk"]["cost"] / best["wk"]["conv"]
        story.append(f"{market(best['name'])} led search with {best['wk']['conv']:.0f} leads at {rh.fmt_usd(bcpl)} each.")
    zero = [market(c["name"]) for c in enabled if c["wk"]["conv"] == 0 and c["wk"]["cost"] > 50]
    if zero:
        story.append("No search leads this week from " + ", ".join(zero) + " — under review.")
    dead_lsa = [x["name"] for x in lsa_rows_out if x["wk_cost"] == 0 and x["pw_cost"] == 0]
    if dead_lsa:
        story.append("Local Services in " + ", ".join(dead_lsa) + " isn't serving (no spend for 2+ weeks) — profile/verification being checked.")

    # ---- render ----
    E = rh.E
    tiles = f"""
    <div class="tiles">
      <div class="tile"><div class="label">Total leads this week</div>
        <div class="value">{tot_wk['leads']:.0f}</div>
        <div>{rh._delta(tot_wk['leads'], tot_pw['leads'], up_good=True)} <span class="mut">vs last week ({tot_pw['leads']:.0f})</span></div>
        {rh._spark(lead_series)}</div>
      <div class="tile"><div class="label">Total ad spend</div>
        <div class="value">{rh.fmt_usd(tot_wk['cost'])}</div>
        <div>{rh._delta(tot_wk['cost'], tot_pw['cost'])} <span class="mut">vs last week</span></div>
        {rh._spark(spend_series)}</div>
      <div class="tile"><div class="label">Cost per lead (blended)</div>
        <div class="value">{rh.fmt_usd(cpl)}</div>
        <div>{rh._delta(cpl, pcpl, up_good=False) if pcpl else ''} <span class="mut">vs last week ({rh.fmt_usd(pcpl) if pcpl else '—'})</span></div></div>
    </div>"""

    chan = f"""<div class="card"><h2>By channel</h2><table>
      <tr><th>Channel</th><th class="num">Leads</th><th class="num">Spend</th><th class="num">Cost/lead</th></tr>
      <tr><td><b>Google Search ads</b></td><td class="num">{ads_wk['conv']:.0f} <span class="mut">(last wk {ads_pw['conv']:.0f})</span></td>
          <td class="num">{rh.fmt_usd(ads_wk['cost'])} <span class="mut">(last wk {rh.fmt_usd(ads_pw['cost'])})</span></td>
          <td class="num">{rh.fmt_usd(ads_cpl) if ads_cpl else '—'}</td></tr>
      <tr><td><b>Local Services Ads</b></td><td class="num">{lsa_wk['leads']} <span class="mut">(last wk {lsa_pw['leads']})</span></td>
          <td class="num">{rh.fmt_usd(lsa_wk['cost'])} <span class="mut">(last wk {rh.fmt_usd(lsa_pw['cost'])})</span></td>
          <td class="num">{rh.fmt_usd(lsa_cpl) if lsa_cpl else '—'}</td></tr>
    </table></div>"""

    charts = ('<div class="charts">' +
              rh._bar_chart(f"Total weekly leads — last {TREND_WEEKS} weeks", weeks_sorted, lead_series, "var(--s2)",
                            lambda v: f"{v:g}", lambda d, v: f"<b>week ending {d}</b><br>{v:g} leads") +
              rh._bar_chart(f"Total weekly ad spend — last {TREND_WEEKS} weeks", weeks_sorted, spend_series, "var(--s1)",
                            lambda v: f"${v:,.0f}", lambda d, v: f"<b>week ending {d}</b><br>{rh.fmt_usd(v)}") +
              '</div>')

    def crow(label, leads, spend, tag=""):
        ccpl = spend / leads if leads else None
        return f"""<tr><td><b>{E(label)}</b> <span class="mut">{tag}</span></td>
          <td class="num">{leads:.0f}</td>
          <td class="num">{rh.fmt_usd(spend)}</td>
          <td class="num">{rh.fmt_usd(ccpl) if ccpl else '—'}</td></tr>"""
    rows = "".join(crow(market(c["name"]), c["wk"]["conv"], c["wk"]["cost"], "search") for c in enabled)
    rows += "".join(crow(x["name"], x["wk_leads"], x["wk_cost"], "LSA")
                    for x in lsa_rows_out if x["wk_cost"] or x["wk_leads"])
    table = f"""<div class="card"><h2>By market (this week)</h2><table>
      <tr><th>Market</th><th class="num">Leads</th><th class="num">Spend</th><th class="num">Cost/lead</th></tr>
      {rows}</table></div>"""

    narrative = '<div class="card"><h2>What\'s happening</h2>' + \
                "".join(f'<p style="margin:8px 0">{E(s)}</p>' for s in story) + "</div>"

    # Beyond paid media — entries from rf-work-log.md dated within this week
    beyond = ""
    log_path = os.path.join(BASE_DIR, "rf-work-log.md")
    if os.path.exists(log_path):
        import re as _re
        items = []
        for line in open(log_path):
            m = _re.match(r"[-*]\s*(\d{4}-\d{2}-\d{2})\s*[:—-]\s*(.+)", line.strip())
            if m and str(wk_start) <= m.group(1) <= str(d_end):
                items.append(m.group(2).strip())
        if items:
            beyond = ('<div class="card"><h2>Beyond paid media — this week</h2>' +
                      "".join(f'<p style="margin:6px 0">• {E(i)}</p>' for i in items) + "</div>")

    html_out = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(ACCOUNT_NAME)} — weekly marketing report · {today}</title>
<style>{rh.CSS}</style></head>
<body class="viz-root"><div class="wrap">
  <h1>{E(ACCOUNT_NAME)} — Weekly Marketing Report</h1>
  <div class="sub">Week of {wk_start.strftime('%b %-d')} – {d_end.strftime('%b %-d, %Y')} · Google Ads + Local Services Ads · prepared by Eaveside</div>
  {tiles}
  {narrative}
  {beyond}
  {chan}
  <div style="margin-top:16px">{charts}</div>
  {table}
  <div class="mut" style="margin-top:20px">A "lead" = a phone call or form submission from search ads, or a charged
    Local Services lead. Conversion data can lag ~24h; minor restatements are normal.</div>
</div><div id="tip"></div>{rh.TIP_JS}</body></html>"""

    os.makedirs(OUT_DIR, exist_ok=True)
    html_path = os.path.join(OUT_DIR, f"exec-{today}.html")
    with open(html_path, "w") as f: f.write(html_out)
    print(f"TOTAL: {tot_wk['leads']:.0f} leads · {rh.fmt_usd(tot_wk['cost'])} spend · CPL {rh.fmt_usd(cpl)} "
          f"(ads {ads_wk['conv']:.0f}@{rh.fmt_usd(ads_cpl)} + LSA {lsa_wk['leads']}@{rh.fmt_usd(lsa_cpl)})")
    for s in story: print("·", s)
    print(f"[saved] {html_path}")

    if not no_discord:
        embed = {
            "title": f"{ACCOUNT_NAME} — Weekly Marketing Report · wk of {wk_start.strftime('%b %-d')}",
            "color": dp.BLUE,
            "description": f"**{tot_wk['leads']:.0f} total leads** · {rh.fmt_usd(tot_wk['cost'])} spend · **{rh.fmt_usd(cpl)}/lead blended**\n"
                           f"Search: {ads_wk['conv']:.0f} @ {rh.fmt_usd(ads_cpl)} · LSA: {lsa_wk['leads']} @ {rh.fmt_usd(lsa_cpl)}",
            "fields": [{"name": "Summary", "value": ("\n".join("• " + s for s in story))[:1024], "inline": False}],
            "footer": {"text": "Leadership-ready report attached — forward as is"},
        }
        ok = dp.post(DISCORD_WEBHOOK, embed=embed, file_path=html_path)
        print(f"[discord] {'posted OK' if ok else 'FAILED'}")

if __name__ == "__main__":
    main()
