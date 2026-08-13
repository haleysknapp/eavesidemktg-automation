#!/usr/bin/env python3
"""
Roofing Force — monthly executive report (1st of the month, covers the prior month).
Google Ads + LSA + Meta (Facebook) combined: month vs prior month, year-over-year with
fair framing (efficiency-first when spend structure changed), 13-month trends, market
breakdown.

Totals come from a channel list, not from hardcoded per-channel blocks — see the same
note in weekly_exec.py. Blended cost per lead must include every live channel's spend.

Usage: python3 monthly_exec.py [--no-discord]
"""
import os, sys, calendar
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import google_ads_client, CUSTOMER_ID, ACCOUNT_NAME, DISCORD_WEBHOOK, BASE_DIR
from lsa import fetch_lsa, LSA_ACCOUNTS
import meta as meta_mod
import render_html as rh
import discord_post as dp
import basis_notes

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
    # REMOVED campaigns are excluded (Fix Queue #21, 2026-08-13). Without the filter,
    # spend from deleted campaigns entered the monthly totals the CLIENT sees, and the
    # 13-month trend could not be reconciled against the account.
    q = f"""
      SELECT campaign.name, campaign.status, segments.month,
             metrics.cost_micros, metrics.conversions
      FROM campaign
      WHERE segments.date BETWEEN '{hist_start}' AND '{m_end}'
        AND campaign.status != 'REMOVED'
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

    # ---- meta (facebook): same 13-month window ----
    # Facebook-ATTRIBUTED results from Ads Manager. Never the pixel's raw Lead total,
    # which also counts website form fills from every non-Facebook source.
    meta_data = meta_mod.fetch_meta(hist_start, m_end)
    meta_monthly = meta_mod.monthly_buckets(meta_data)
    meta_market_m = {}
    if meta_monthly.get(mk, {}).get("cost") or meta_monthly.get(mk, {}).get("leads"):
        _mc = meta_mod.load_meta_config()
        meta_market_m[_mc.get("_market", "Kansas City")] = dict(meta_monthly[mk])
    meta_live = bool(meta_market_m)

    def tot(mo):
        a = ads_monthly.get(mo, {"cost": 0, "conv": 0})
        l = lsa_monthly.get(mo, {"cost": 0, "leads": 0})
        f = meta_monthly.get(mo, {"cost": 0, "leads": 0})
        leads = a["conv"] + l["leads"] + f["leads"]
        cost = a["cost"] + l["cost"] + f["cost"]
        return {"leads": leads, "cost": cost, "cpl": cost / leads if leads else 0,
                "ads": a, "lsa": l, "meta": f}
    M, P, Y = tot(mk), tot(pk), tot(yk)

    months_sorted = sorted(set(list(ads_monthly) + list(lsa_monthly) + list(meta_monthly)))
    months_sorted = [m for m in months_sorted if m <= mk][-13:]
    lead_series = [ads_monthly.get(m, {}).get("conv", 0) + lsa_monthly.get(m, {}).get("leads", 0)
                   + meta_monthly.get(m, {}).get("leads", 0) for m in months_sorted]
    spend_series = [ads_monthly.get(m, {}).get("cost", 0) + lsa_monthly.get(m, {}).get("cost", 0)
                    + meta_monthly.get(m, {}).get("cost", 0) for m in months_sorted]
    mlabels = [datetime.strptime(m, "%Y-%m").strftime("%b")[:3] + " " for m in months_sorted]

    # ---- narrative ----
    E = rh.E
    story = []
    _across = ("Google Search ads, Local Services Ads and Facebook ads" if meta_live
               else "Google Search ads and Local Services Ads")
    story.append(f"In {label}, Roofing Force generated {M['leads']:.0f} leads across {_across}"
                 f" on {rh.fmt_usd(M['cost'])} of total ad spend — {rh.fmt_usd(M['cpl'])} per lead"
                 + (f", vs {P['leads']:.0f} leads at {rh.fmt_usd(P['cpl'])} in {date(py,pm,1).strftime('%B')}." if P["leads"] else "."))
    _split = (f"Search drove {M['ads']['conv']:.0f} leads at "
              f"{rh.fmt_usd(M['ads']['cost']/M['ads']['conv']) if M['ads']['conv'] else '—'} each; "
              f"Local Services added {M['lsa']['leads']} at "
              f"{rh.fmt_usd(M['lsa']['cost']/M['lsa']['leads']) if M['lsa']['leads'] else '—'} each.")
    if meta_live:
        _split = _split[:-1] + (f"; Facebook added {M['meta']['leads']:.0f} at "
                                f"{rh.fmt_usd(M['meta']['cost']/M['meta']['leads']) if M['meta']['leads'] else '—'} each.")
    story.append(_split)
    if meta_live:
        story.append("Facebook numbers are the results Meta attributes to the ads in Ads Manager — "
                     "not every form on the site, which fills from search and direct traffic too.")
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

    _pm = date(py, pm, 1).strftime('%b')
    _mchans = [
        {"label": "Google Search ads", "leads": M['ads']['conv'], "cost": M['ads']['cost'],
         "p_leads": P['ads']['conv'], "p_cost": P['ads']['cost']},
        {"label": "Local Services Ads", "leads": M['lsa']['leads'], "cost": M['lsa']['cost'],
         "p_leads": P['lsa']['leads'], "p_cost": P['lsa']['cost']},
    ]
    if meta_live:
        _mchans.append({"label": "Facebook ads", "leads": M['meta']['leads'], "cost": M['meta']['cost'],
                        "p_leads": P['meta']['leads'], "p_cost": P['meta']['cost']})
    _crows = ""
    for _c in _mchans:
        _ccpl = _c['cost'] / _c['leads'] if _c['leads'] else 0
        _crows += (f"""      <tr><td><b>{E(_c['label'])}</b></td>
        <td class="num">{_c['leads']:.0f} <span class="mut">({_pm}: {_c['p_leads']:.0f})</span></td>
        <td class="num">{rh.fmt_usd(_c['cost'])} <span class="mut">({rh.fmt_usd(_c['p_cost'])})</span></td>
        <td class="num">{rh.fmt_usd(_ccpl) if _ccpl else '—'}</td></tr>\n""")
    _crows += (f"""      <tr style="border-top:2px solid var(--baseline)"><td><b>All channels</b></td>
        <td class="num"><b>{M['leads']:.0f}</b> <span class="mut">({_pm}: {P['leads']:.0f})</span></td>
        <td class="num"><b>{rh.fmt_usd(M['cost'])}</b> <span class="mut">({rh.fmt_usd(P['cost'])})</span></td>
        <td class="num"><b>{rh.fmt_usd(M['cpl']) if M['cpl'] else '—'}</b></td></tr>\n""")
    _cnote = (f'<p class="mut" style="margin:8px 2px 0;font-size:12px">{E(meta_mod.DEFINITION_LONG)}</p>'
              if meta_live else '')
    chan = (f'<div class="card"><h2>By channel — {E(label)}</h2><table>\n'
            f'      <tr><th>Channel</th><th class="num">Leads</th><th class="num">Spend</th><th class="num">Cost/lead</th></tr>\n'
            + _crows + f'    </table>{_cnote}</div>')

    charts = ('<div class="charts">' +
              rh._bar_chart("Total monthly leads — last 13 months", mlabels, lead_series, "var(--s2)",
                            lambda v: f"{v:g}", lambda d, v: f"<b>{d.strip()}</b><br>{v:g} leads") +
              rh._bar_chart("Total monthly ad spend — last 13 months", mlabels, spend_series, "var(--s1)",
                            lambda v: f"${v:,.0f}", lambda d, v: f"<b>{d.strip()}</b><br>{rh.fmt_usd(v)}") + '</div>')

    # Counting-basis guard — flag any month in the 13-month trend that spans a
    # change in how leads are counted (see basis_notes.py).
    _mflags = basis_notes.flagged_months(months_sorted)
    if _mflags:
        _names = ", ".join(datetime.strptime(m, "%Y-%m").strftime("%b %Y") for m in sorted(_mflags))
        charts += (f'<p class="mut" style="margin:6px 2px 0;font-size:12px">'
                   f'{E(_names)} spans a change in how leads are counted. '
                   f'{E(basis_notes.CHANGES[0]["note"])}</p>')

    def market_name(name):
        for suf in (" New Search", " - Search", " Search"):
            if name.endswith(suf): return name[: -len(suf)]
        return name
    table = rh.merged_market_table(
        f"By market — {label}",
        [(market_name(c), v["conv"], v["cost"]) for c, v in ads_camp_m.items() if v["cost"] >= 1],
        [(n, v["leads"], v["cost"]) for n, v in lsa_market_m.items() if v["cost"] >= 1 or v["leads"]],
        meta_rows=[(n, v["leads"], v["cost"]) for n, v in meta_market_m.items()])

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

    # organic search (GSC sidecar: out/gsc.json, written from Search Console via Chrome)
    gsc_card = ""
    gsc_path = os.path.join(OUT_DIR, "gsc.json")
    if os.path.exists(gsc_path):
        try:
            import json as _json
            g = _json.load(open(gsc_path))
            if g.get("month") == mk and g.get("rows"):
                gr = "".join(f'<tr><td><b>{E(r[0])}</b></td><td class="num">{E(str(r[1]))}</td>'
                             f'<td class="num split">{E(str(r[2]))}</td></tr>' for r in g["rows"])
                gnote = f'<div class="mut" style="margin-top:8px">{E(g["note"])}</div>' if g.get("note") else ""
                gsc_card = (f'<div class="card"><h2>Organic search — {E(g.get("label", label))}</h2>'
                            f'<table><tr><th>Metric</th><th class="num">{E(g.get("label", label))}</th>'
                            f'<th class="num">{E(g.get("prev_label", "prior month"))}</th></tr>{gr}</table>{gnote}</div>')
        except Exception as e:
            print(f"[warn] gsc.json unreadable: {e}")

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

    # Every figure states its definition — see the 2026-08-07 LSA charged-vs-total escalation.
    footer_note = ('A "lead" = a phone call or form submission from search ads, or a charged '
                   'Local Services lead. Figures may restate slightly as late conversions land.')
    if meta_live:
        footer_note = ('A "lead" = a phone call or form submission from search ads, a charged '
                       'Local Services lead, or a Facebook-attributed result from Ads Manager. '
                       'Facebook results count conversions Meta ties back to an ad click — not the '
                       'pixel\'s raw Lead total, which also counts form fills from other traffic '
                       'sources. Figures may restate slightly as late conversions land.')

    html_out = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(ACCOUNT_NAME)} — monthly marketing report · {E(label)}</title>
<style>{rh.CSS}</style></head>
<body class="viz-root"><div class="wrap">
  {rh.brand_header("Monthly Marketing Report", label, f"{ACCOUNT_NAME} · " + " + ".join(["Google Ads", "Local Services Ads"] + (["Facebook Ads"] if meta_live else [])))}
  {tiles}
  {narrative}
  {beyond}
  {chan}
  {yoy_html}
  <div style="margin-top:16px">{charts}</div>
  {table}
  {quality}
  {gsc_card}
  {sitecard}
  <div class="endgroup">
  {focus}
  {rh.brand_footer(footer_note)}
  </div>
</div><div id="tip"></div>{rh.TIP_JS}</body></html>"""

    os.makedirs(OUT_DIR, exist_ok=True)
    html_path = os.path.join(OUT_DIR, f"monthly-{mk}.html")
    with open(html_path, "w") as f: f.write(html_out)
    if not meta_data.get("available") and meta_mod.load_meta_config():
        print(f"[META] ⚠️  Meta is configured but could not be read ({meta_data.get('reason','unknown')}). "
              "Blended cost per lead below EXCLUDES any Meta spend.")
    elif meta_data.get("available") and not meta_live:
        print("[META] connected, no spend or results in this month — Meta omitted by design.")
    print(f"{label}: {M['leads']:.0f} leads · {rh.fmt_usd(M['cost'])} · CPL {rh.fmt_usd(M['cpl'])} "
          f"(prior mo: {P['leads']:.0f} @ {rh.fmt_usd(P['cpl'])}; YoY: {Y['leads']:.0f} @ {rh.fmt_usd(Y['cpl']) if Y['cpl'] else '—'})")
    for s in story: print("·", s)
    print(f"[saved] {html_path}")

    if not no_discord:
        embed = {
            "title": f"{ACCOUNT_NAME} — Monthly Report · {label}",
            "color": dp.BLUE,
            "description": f"**{M['leads']:.0f} total leads** · {rh.fmt_usd(M['cost'])} spend · **{rh.fmt_usd(M['cpl'])}/lead**"
                           + (f" · Facebook: {M['meta']['leads']:.0f} @ {rh.fmt_usd(M['meta']['cost']/M['meta']['leads']) if M['meta']['leads'] else '—'}" if meta_live else "") + "\n"
                           f"vs {date(py,pm,1).strftime('%B')}: {P['leads']:.0f} @ {rh.fmt_usd(P['cpl']) if P['cpl'] else '—'}",
            "fields": [{"name": "Summary", "value": ("\n".join("• " + s for s in story))[:1024], "inline": False}],
            "footer": {"text": "Executive-ready report attached"},
        }
        ok = dp.post(DISCORD_WEBHOOK, embed=embed)
        print(f"[discord] {'posted OK' if ok else 'FAILED'}")

if __name__ == "__main__":
    main()
