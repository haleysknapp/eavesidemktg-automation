#!/usr/bin/env python3
"""
Roofing Force — monthly executive report (1st of the month, covers the prior month).
Google Ads + LSA combined: month vs prior month, year-over-year with fair framing
(efficiency-first when spend structure changed), 13-month trends, market breakdown.

Usage: python3 monthly_exec.py [--no-discord]
"""
import os, sys, calendar
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import google_ads_client, CUSTOMER_ID, ACCOUNT_NAME, DISCORD_WEBHOOK, BASE_DIR
from lsa import fetch_lsa, LSA_ACCOUNTS
import render_html as rh
import discord_post as dp

TZ = ZoneInfo("America/Denver")
OUT_DIR = os.path.join(BASE_DIR, "out")

def money(m): return m / 1_000_000

def month_key(d): return f"{d.year:04d}-{d.month:02d}"

def prev_month(y, m, k=1):
    for _ in range(k):
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return y, m

def main():
    no_discord = "--no-discord" in sys.argv
    today = datetime.now(TZ).date()
    ry, rm = prev_month(today.year, today.month)          # report month
    m_start = date(ry, rm, 1)
    m_end = date(ry, rm, calendar.monthrange(ry, rm)[1])
    py, pm = prev_month(ry, rm)                            # prior month
    yy, ym = ry - 1, rm                                    # same month last year
    hist_start = date(*prev_month(ry, rm, 12), 1)

    mk, pk, yk = f"{ry:04d}-{rm:02d}", f"{py:04d}-{pm:02d}", f"{yy:04d}-{ym:02d}"
    label = m_start.strftime("%B %Y")

    client = google_ads_client()
    svc = client.get_service("GoogleAdsService")

    # ---- google ads: monthly totals (13 mo) + per-campaign for report month ----
    q = f"""
      SELECT campaign.name, campaign.status, segments.month,
             metrics.cost_micros, metrics.conversions
      FROM campaign
      WHERE segments.date BETWEEN '{hist_start}' AND '{m_end}'
    """
    ads_monthly = defaultdict(lambda: {"cost": 0.0, "conv": 0.0})
    ads_camp_m = defaultdict(lambda: {"cost": 0.0, "conv": 0.0})
    for r in svc.search(customer_id=CUSTOMER_ID, query=q):
        mo = str(r.segments.month)[:7]
        cost, conv = money(r.metrics.cost_micros), r.metrics.conversions
        ads_monthly[mo]["cost"] += cost
        ads_monthly[mo]["conv"] += conv
        if mo == mk:
            ads_camp_m[r.campaign.name]["cost"] += cost
            ads_camp_m[r.campaign.name]["conv"] += conv

    # ---- lsa: 13 months ----
    lsa_data = fetch_lsa(client, hist_start, m_end)
    lsa_monthly = defaultdict(lambda: {"cost": 0.0, "leads": 0})
    lsa_market_m = {}
    for name, acct in lsa_data.items():
        mrow = {"cost": 0.0, "leads": 0}
        for dstr, v in acct["daily"].items():
            mo = dstr[:7]
            lsa_monthly[mo]["cost"] += v
            if mo == mk: mrow["cost"] += v
        for (dstr, charged, _s, _t) in acct["leads"]:
            if not charged: continue
            mo = dstr[:7]
            lsa_monthly[mo]["leads"] += 1
            if mo == mk: mrow["leads"] += 1
        lsa_market_m[name] = mrow

    def tot(mo):
        a, l = ads_monthly.get(mo, {"cost": 0, "conv": 0}), lsa_monthly.get(mo, {"cost": 0, "leads": 0})
        leads = a["conv"] + l["leads"]; cost = a["cost"] + l["cost"]
        return {"leads": leads, "cost": cost, "cpl": cost / leads if leads else 0,
                "ads": a, "lsa": l}
    M, P, Y = tot(mk), tot(pk), tot(yk)

    months_sorted = sorted(set(list(ads_monthly) + list(lsa_monthly)))
    months_sorted = [m for m in months_sorted if m <= mk][-13:]
    lead_series = [ads_monthly.get(m, {}).get("conv", 0) + lsa_monthly.get(m, {}).get("leads", 0) for m in months_sorted]
    spend_series = [ads_monthly.get(m, {}).get("cost", 0) + lsa_monthly.get(m, {}).get("cost", 0) for m in months_sorted]
    mlabels = [datetime.strptime(m, "%Y-%m").strftime("%b")[:3] + " " for m in months_sorted]

    # ---- narrative ----
    E = rh.E
    story = []
    story.append(f"In {label}, Roofing Force generated {M['leads']:.0f} leads across Google Search ads and Local "
                 f"Services Ads on {rh.fmt_usd(M['cost'])} of total ad spend — {rh.fmt_usd(M['cpl'])} per lead"
                 + (f", vs {P['leads']:.0f} leads at {rh.fmt_usd(P['cpl'])} in {date(py,pm,1).strftime('%B')}." if P["leads"] else "."))
    story.append(f"Search drove {M['ads']['conv']:.0f} leads at "
                 f"{rh.fmt_usd(M['ads']['cost']/M['ads']['conv']) if M['ads']['conv'] else '—'} each; "
                 f"Local Services added {M['lsa']['leads']} at "
                 f"{rh.fmt_usd(M['lsa']['cost']/M['lsa']['leads']) if M['lsa']['leads'] else '—'} each.")
    if P["cost"]:
        ds = (M["cost"] - P["cost"]) / P["cost"] * 100
        dl = (M["leads"] - P["leads"]) / P["leads"] * 100 if P["leads"] else 0
        if ds > 10 and dl >= ds - 10:
            story.append(f"Month over month, spend grew {ds:+.0f}% and leads kept pace ({dl:+.0f}%) — scaling is holding efficiency.")
        elif ds > 10:
            story.append(f"Month over month, spend grew {ds:+.0f}% while leads moved {dl:+.0f}% — efficiency is being watched as budgets scale.")

    # YoY with fair framing
    yoy_html = ""
    if Y["cost"] > 0:
        spend_gap = (M["cost"] - Y["cost"]) / Y["cost"] * 100
        yoy_note = ""
        if spend_gap < -30:
            cpl_line = ""
            if Y["cpl"] and M["cpl"]:
                if M["cpl"] < Y["cpl"]:
                    cpl_line = (f" On the like-for-like measure — cost per lead — the account is more efficient than a year ago: "
                                f"{rh.fmt_usd(M['cpl'])} now vs {rh.fmt_usd(Y['cpl'])} then.")
                else:
                    cpl_line = f" Cost per lead: {rh.fmt_usd(M['cpl'])} now vs {rh.fmt_usd(Y['cpl'])} then."
            ratio = Y["cost"] / M["cost"] if M["cost"] else 0
            yoy_note = (f"Context for the year-over-year comparison: {date(yy,ym,1).strftime('%B %Y')} ran at roughly "
                        f"{ratio:.1f}× today's ad budget. Spend was then throttled down sharply over the following months, "
                        f"and Eaveside inherited the account near its low point — so total volume isn't an apples-to-apples "
                        f"comparison. The current program is rebuilding spend from that base, with structures built to hold "
                        f"efficiency as budgets scale back up.{cpl_line}")
        def yrow(lab, t):
            return (f"<tr><td><b>{lab}</b></td><td class=num>{t['leads']:.0f}</td>"
                    f"<td class=num>{rh.fmt_usd(t['cost'])}</td>"
                    f"<td class=num>{rh.fmt_usd(t['cpl']) if t['cpl'] else '—'}</td></tr>")
        yoy_html = f"""<div class="card"><h2>Year over year — {m_start.strftime('%B')}</h2><table>
          <tr><th>Period</th><th class="num">Leads</th><th class="num">Spend</th><th class="num">Cost/lead</th></tr>
          {yrow(label, M)}{yrow(date(yy,ym,1).strftime('%B %Y'), Y)}</table>
          {'<div class="sub" style="margin-top:10px">' + E(yoy_note) + '</div>' if yoy_note else ''}</div>"""

    tiles = f"""
    <div class="tiles">
      <div class="tile"><div class="label">Total leads — {E(label)}</div>
        <div class="value">{M['leads']:.0f}</div>
        <div>{rh._delta(M['leads'], P['leads'], up_good=True)} <span class="mut">vs {date(py,pm,1).strftime('%B')} ({P['leads']:.0f})</span></div>
        {rh._spark(lead_series)}</div>
      <div class="tile"><div class="label">Total ad spend</div>
        <div class="value">{rh.fmt_usd(M['cost'])}</div>
        <div>{rh._delta(M['cost'], P['cost'])} <span class="mut">vs {date(py,pm,1).strftime('%B')} ({rh.fmt_usd(P['cost'])})</span></div>
        {rh._spark(spend_series)}</div>
      <div class="tile"><div class="label">Cost per lead (blended)</div>
        <div class="value">{rh.fmt_usd(M['cpl']) if M['cpl'] else '—'}</div>
        <div>{rh._delta(M['cpl'], P['cpl'], up_good=False) if M['cpl'] and P['cpl'] else ''} <span class="mut">vs {date(py,pm,1).strftime('%B')} ({rh.fmt_usd(P['cpl']) if P['cpl'] else '—'})</span></div></div>
    </div>"""

    chan = f"""<div class="card"><h2>By channel — {E(label)}</h2><table>
      <tr><th>Channel</th><th class="num">Leads</th><th class="num">Spend</th><th class="num">Cost/lead</th></tr>
      <tr><td><b>Google Search ads</b></td>
        <td class="num">{M['ads']['conv']:.0f} <span class="mut">({date(py,pm,1).strftime('%b')}: {P['ads']['conv']:.0f})</span></td>
        <td class="num">{rh.fmt_usd(M['ads']['cost'])} <span class="mut">({rh.fmt_usd(P['ads']['cost'])})</span></td>
        <td class="num">{rh.fmt_usd(M['ads']['cost']/M['ads']['conv']) if M['ads']['conv'] else '—'}</td></tr>
      <tr><td><b>Local Services Ads</b></td>
        <td class="num">{M['lsa']['leads']} <span class="mut">({date(py,pm,1).strftime('%b')}: {P['lsa']['leads']})</span></td>
        <td class="num">{rh.fmt_usd(M['lsa']['cost'])} <span class="mut">({rh.fmt_usd(P['lsa']['cost'])})</span></td>
        <td class="num">{rh.fmt_usd(M['lsa']['cost']/M['lsa']['leads']) if M['lsa']['leads'] else '—'}</td></tr>
    </table></div>"""

    charts = ('<div class="charts">' +
              rh._bar_chart("Total monthly leads — last 13 months", mlabels, lead_series, "var(--s2)",
                            lambda v: f"{v:g}", lambda d, v: f"<b>{d.strip()}</b><br>{v:g} leads") +
              rh._bar_chart("Total monthly ad spend — last 13 months", mlabels, spend_series, "var(--s1)",
                            lambda v: f"${v:,.0f}", lambda d, v: f"<b>{d.strip()}</b><br>{rh.fmt_usd(v)}") + '</div>')

    def market_name(name):
        for suf in (" New Search", " - Search", " Search"):
            if name.endswith(suf): return name[: -len(suf)]
        return name
    table = rh.merged_market_table(
        f"By market — {label}",
        [(market_name(c), v["conv"], v["cost"]) for c, v in ads_camp_m.items() if v["cost"] >= 1],
        [(n, v["leads"], v["cost"]) for n, v in lsa_market_m.items() if v["cost"] >= 1 or v["leads"]])

    # beyond paid media (work log entries in month)
    beyond = ""
    log_path = os.path.join(BASE_DIR, "rf-work-log.md")
    if os.path.exists(log_path):
        import re as _re
        items = []
        for line in open(log_path):
            m2 = _re.match(r"[-*]\s*(\d{4}-\d{2}-\d{2})\s*[:—-]\s*(.+)", line.strip())
            if m2 and str(m_start) <= m2.group(1) <= str(m_end):
                items.append(m2.group(2).strip())
        if items:
            beyond = ('<div class="card"><h2>Initiatives — ' + E(label) + '</h2>' +
                      "".join(f'<p style="margin:6px 0">• {E(i)}</p>' for i in items) + "</div>")

    # ---- new sections: lead quality (audited), site health ----
    quality = ""
    audit_path = os.path.join(OUT_DIR, "lead_audit.json")
    if os.path.exists(audit_path):
        try:
            import json as _json
            a = _json.load(open(audit_path))
            if a.get("month") == mk:
                rows_q = "".join(f'<tr><td><b>{E(k)}</b></td><td class="num">{E(str(v))}</td></tr>'
                                 for k, v in a.get("stats", {}).items())
                note_q = f'<div class="mut" style="margin-top:8px">{E(a["note"])}</div>' if a.get("note") else ""
                if rows_q:
                    quality = (f'<div class="card"><h2>Lead quality — audited · {E(label)}</h2>'
                               f'<table>{rows_q}</table>{note_q}</div>')
        except Exception as e:
            print(f"[warn] lead_audit.json unreadable: {e}")

    sitecard = ""
    try:
        import site_health
        sitecard = site_health.card(rh, f"Website status — checked {today.strftime('%b %-d')}")
    except Exception as e:
        print(f"[warn] site health failed: {e}")

    # focus & targets for the upcoming month (rf-focus.md, "## YYYY-MM" sections)
    focus = ""
    ny, nm = (ry + 1, 1) if rm == 12 else (ry, rm + 1)
    nk = f"{ny:04d}-{nm:02d}"
    next_label = date(ny, nm, 1).strftime("%B %Y")
    focus_path = os.path.join(BASE_DIR, "rf-focus.md")
    if os.path.exists(focus_path):
        import re as _re
        items, active = [], False
        for line in open(focus_path):
            s = line.strip()
            h = _re.match(r"##\s*(\d{4}-\d{2})", s)
            if h:
                active = (h.group(1) == nk)
                continue
            if active and _re.match(r"[-*]\s+", s):
                items.append(_re.sub(r"^[-*]\s+", "", s))
        if items:
            focus = ('<div class="card"><h2>Focus &amp; targets — ' + E(next_label) + '</h2>' +
                     "".join(f'<p style="margin:6px 0">• {E(i)}</p>' for i in items) + "</div>")

    narrative = '<div class="card"><h2>The month in brief</h2>' + \
                "".join(f'<p style="margin:8px 0">{E(s)}</p>' for s in story) + "</div>"

    html_out = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(ACCOUNT_NAME)} — monthly marketing report · {E(label)}</title>
<style>{rh.CSS}</style></head>
<body class="viz-root"><div class="wrap">
  {rh.brand_header("Monthly Marketing Report", label, f"{ACCOUNT_NAME} · Google Ads + Local Services Ads")}
  {tiles}
  {narrative}
  {beyond}
  {chan}
  {yoy_html}
  <div style="margin-top:16px">{charts}</div>
  {table}
  {quality}
  {sitecard}
  {focus}
  {rh.brand_footer('A "lead" = a phone call or form submission from search ads, or a charged Local Services lead. Figures may restate slightly as late conversions land.')}
</div><div id="tip"></div>{rh.TIP_JS}</body></html>"""

    os.makedirs(OUT_DIR, exist_ok=True)
    html_path = os.path.join(OUT_DIR, f"monthly-{mk}.html")
    with open(html_path, "w") as f: f.write(html_out)
    print(f"{label}: {M['leads']:.0f} leads · {rh.fmt_usd(M['cost'])} · CPL {rh.fmt_usd(M['cpl'])} "
          f"(prior mo: {P['leads']:.0f} @ {rh.fmt_usd(P['cpl'])}; YoY: {Y['leads']:.0f} @ {rh.fmt_usd(Y['cpl']) if Y['cpl'] else '—'})")
    for s in story: print("·", s)
    print(f"[saved] {html_path}")

    if not no_discord:
        embed = {
            "title": f"{ACCOUNT_NAME} — Monthly Report · {label}",
            "color": dp.BLUE,
            "description": f"**{M['leads']:.0f} total leads** · {rh.fmt_usd(M['cost'])} spend · **{rh.fmt_usd(M['cpl'])}/lead**\n"
                           f"vs {date(py,pm,1).strftime('%B')}: {P['leads']:.0f} @ {rh.fmt_usd(P['cpl']) if P['cpl'] else '—'}",
            "fields": [{"name": "Summary", "value": ("\n".join("• " + s for s in story))[:1024], "inline": False}],
            "footer": {"text": "Executive-ready report attached"},
        }
        ok = dp.post(DISCORD_WEBHOOK, embed=embed, file_path=html_path)
        print(f"[discord] {'posted OK' if ok else 'FAILED'}")

if __name__ == "__main__":
    main()
