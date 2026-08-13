#!/usr/bin/env python3
"""
Roofing Force — weekly leadership report (Fridays).
Combines Google Ads (search) + Local Services Ads + Meta (Facebook) into total
leads / spend / blended cost per lead, with channel + market breakouts and a
plain-language story.

CHANNELS ARE A LIST, NOT HARDCODED BLOCKS (2026-08-13)
------------------------------------------------------
Every headline number below is a sum over `channels`. Adding a channel to that
list is the only thing needed to get it into total leads, total spend, the
By-channel table AND the blended cost per lead. This exists because when Meta
launched, blended CPL was being computed from Google + LSA only and therefore
read BETTER than reality — the exact failure mode this structure removes.

Usage: python3 weekly_exec.py [--no-discord]
"""
import os, sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import google_ads_client, CUSTOMER_ID, ACCOUNT_NAME, DISCORD_WEBHOOK, BASE_DIR
from lsa import fetch_lsa, window as lsa_window
import meta as meta_mod
import render_html as rh
import discord_post as dp
import basis_notes

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
    meta_data = meta_mod.fetch_meta(d_start, d_end)

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

    # ---- meta (facebook) aggregation ----
    # Facebook-ATTRIBUTED results from Ads Manager, never the pixel's raw Lead total.
    meta_wk_cost, meta_wk_leads = meta_mod.window(meta_data, wk_start, d_end)
    meta_pw_cost, meta_pw_leads = meta_mod.window(meta_data, pw_start, pw_end)
    meta_weekly = meta_mod.weekly_buckets(meta_data, d_end, TREND_WEEKS)
    # Only surface Meta once it is actually live. Before first spend, showing a row of
    # zeroes just invites "is Facebook broken?" on a call.
    meta_live = bool(meta_wk_cost or meta_wk_leads or meta_pw_cost or meta_pw_leads)

    # ---- channels ----
    # THE source of truth for totals. Anything not in this list is not in the report.
    channels = [
        {"key": "google", "label": "Google Search ads",
         "leads": ads_wk["conv"], "cost": ads_wk["cost"],
         "p_leads": ads_pw["conv"], "p_cost": ads_pw["cost"],
         "weekly": ads_weekly},
        {"key": "lsa", "label": "Local Services Ads",
         "leads": lsa_wk["leads"], "cost": lsa_wk["cost"],
         "p_leads": lsa_pw["leads"], "p_cost": lsa_pw["cost"],
         "weekly": lsa_weekly},
    ]
    if meta_live:
        channels.append(
            {"key": "meta", "label": "Facebook ads",
             "leads": meta_wk_leads, "cost": meta_wk_cost,
             "p_leads": meta_pw_leads, "p_cost": meta_pw_cost,
             "weekly": meta_weekly,
             "definition": meta_mod.DEFINITION})
    for ch in channels:
        ch["cpl"] = ch["cost"] / ch["leads"] if ch["leads"] else 0

    # ---- combined totals (sum over channels — Meta included whenever it is live) ----
    tot_wk = {"leads": sum(c["leads"] for c in channels),
              "cost": sum(c["cost"] for c in channels)}
    tot_pw = {"leads": sum(c["p_leads"] for c in channels),
              "cost": sum(c["p_cost"] for c in channels)}
    cpl = tot_wk["cost"] / tot_wk["leads"] if tot_wk["leads"] else 0
    pcpl = tot_pw["cost"] / tot_pw["leads"] if tot_pw["leads"] else 0
    ads_cpl = ads_wk["cost"] / ads_wk["conv"] if ads_wk["conv"] else 0
    lsa_cpl = lsa_wk["cost"] / lsa_wk["leads"] if lsa_wk["leads"] else 0
    meta_cpl = meta_wk_cost / meta_wk_leads if meta_wk_leads else 0

    weeks_sorted = sorted(set().union(*[set(c["weekly"]) for c in channels]))
    spend_series = [sum(c["weekly"][w]["cost"] for c in channels) for w in weeks_sorted]
    lead_series = [sum(c["weekly"][w]["conv"] for c in channels) for w in weeks_sorted]

    # ---- narrative ----
    story = []
    dl = (tot_wk["leads"] - tot_pw["leads"]) / tot_pw["leads"] * 100 if tot_pw["leads"] else 0
    ds = (tot_wk["cost"] - tot_pw["cost"]) / tot_pw["cost"] * 100 if tot_pw["cost"] else 0
    labels = [c["label"] for c in channels]
    chan_phrase = (" and ".join(labels) if len(labels) < 3
                   else ", ".join(labels[:-1]) + " and " + labels[-1])
    story.append(f"Across {chan_phrase}, the account generated {tot_wk['leads']:.0f} leads "
                 f"this week on {rh.fmt_usd(tot_wk['cost'])} of total ad spend — {rh.fmt_usd(cpl)} per lead"
                 + (f", vs {tot_pw['leads']:.0f} leads at {rh.fmt_usd(pcpl)} last week." if tot_pw["leads"] else "."))
    split = (f"Search ads drove {ads_wk['conv']:.0f} leads at {rh.fmt_usd(ads_cpl)} each; "
             f"Local Services Ads added {lsa_wk['leads']:.0f} at {rh.fmt_usd(lsa_cpl)} each.")
    if meta_live:
        split = split[:-1] + (f"; Facebook ads added {meta_wk_leads:.0f} at "
                              f"{rh.fmt_usd(meta_cpl) if meta_cpl else '—'} each.")
    story.append(split)
    if meta_live:
        story.append("Facebook numbers are the results Meta attributes to the ads in Ads Manager — "
                     "not every form on the site, which fills from search and direct traffic too.")
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

    # Counting-basis guard: if this week vs last week straddles a change in how
    # leads are counted, say so instead of reporting the artefact as a real drop.
    basis_wk = basis_notes.client_note(pw_start, d_end, prefix="")
    if basis_wk:
        story.append(basis_wk + " The like-for-like comparison is the one to use.")

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

    # By channel — one row per entry in `channels`, plus an explicit Total row so the
    # blended cost per lead can be checked against the rows above it rather than taken
    # on trust. A channel missing from this table is a channel missing from blended CPL.
    chan_rows = ""
    for c in channels:
        chan_rows += (
            f"""      <tr><td><b>{E(c['label'])}</b></td><td class="num">{c['leads']:.0f} <span class="mut">(last wk {c['p_leads']:.0f})</span></td>
          <td class="num">{rh.fmt_usd(c['cost'])} <span class="mut">(last wk {rh.fmt_usd(c['p_cost'])})</span></td>
          <td class="num">{rh.fmt_usd(c['cpl']) if c['cpl'] else '—'}</td></tr>\n""")
    chan_rows += (
        f"""      <tr style="border-top:2px solid var(--baseline)"><td><b>All channels</b></td><td class="num"><b>{tot_wk['leads']:.0f}</b> <span class="mut">(last wk {tot_pw['leads']:.0f})</span></td>
          <td class="num"><b>{rh.fmt_usd(tot_wk['cost'])}</b> <span class="mut">(last wk {rh.fmt_usd(tot_pw['cost'])})</span></td>
          <td class="num"><b>{rh.fmt_usd(cpl) if cpl else '—'}</b></td></tr>\n""")
    chan_note = ""
    if meta_live:
        chan_note = (f'<p class="mut" style="margin:8px 2px 0;font-size:12px">{E(meta_mod.DEFINITION_LONG)}</p>')
    chan = (f'<div class="card"><h2>By channel</h2><table>\n'
            f'      <tr><th>Channel</th><th class="num">Leads</th><th class="num">Spend</th><th class="num">Cost/lead</th></tr>\n'
            + chan_rows + f'    </table>{chan_note}</div>')

    charts = ('<div class="charts">' +
              rh._bar_chart(f"Total weekly leads — last {TREND_WEEKS} weeks", weeks_sorted, lead_series, "var(--s2)",
                            lambda v: f"{v:g}", lambda d, v: f"<b>week ending {d}</b><br>{v:g} leads") +
              rh._bar_chart(f"Total weekly ad spend — last {TREND_WEEKS} weeks", weeks_sorted, spend_series, "var(--s1)",
                            lambda v: f"${v:,.0f}", lambda d, v: f"<b>week ending {d}</b><br>{rh.fmt_usd(v)}") +
              '</div>')

    # Footnote under the 8-week trend for any bucket that spans a basis change.
    trend_fn = basis_notes.trend_footnote(weeks_sorted)
    if trend_fn:
        charts += (f'<p class="mut" style="margin:6px 2px 0;font-size:12px">{E(trend_fn)}</p>')

    # Meta rolls into one market: the ad set targets Johnson County KS, which reports
    # under Kansas City. Read from clients.json so a second Meta market is a config
    # change, not a code change.
    meta_market_rows = []
    if meta_live:
        _mcfg = meta_mod.load_meta_config()
        meta_market_rows = [(_mcfg.get("_market", "Kansas City"), meta_wk_leads, meta_wk_cost)]

    table = rh.merged_market_table(
        "By market (this week)",
        [(market(c["name"]), c["wk"]["conv"], c["wk"]["cost"]) for c in enabled],
        [(x["name"], x["wk_leads"], x["wk_cost"]) for x in lsa_rows_out if x["wk_cost"] or x["wk_leads"]],
        meta_rows=meta_market_rows)

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
            beyond = ('<div class="card"><h2>Initiatives — this week</h2>' +
                      "".join(f'<p style="margin:6px 0">• {E(i)}</p>' for i in items) + "</div>")

    # Every figure states its definition. The 2026-08-07 escalation came from an
    # ambiguous lead definition (LSA "charged" vs "total" under one heading); Meta adds
    # a second way to be ambiguous, so it gets named explicitly rather than implied.
    footer_note = ('A "lead" = a phone call or form submission from search ads, or a charged '
                   'Local Services lead. Conversion data can lag ~24h; minor restatements are normal.')
    if meta_live:
        footer_note = ('A "lead" = a phone call or form submission from search ads, a charged '
                       'Local Services lead, or a Facebook-attributed result from Ads Manager. '
                       'Facebook results count conversions Meta ties back to an ad click — not the '
                       'pixel\'s raw Lead total, which also counts form fills from other traffic '
                       'sources. Conversion data can lag ~24h; minor restatements are normal.')

    html_out = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(ACCOUNT_NAME)} — weekly marketing report · {today}</title>
<style>{rh.CSS}</style></head>
<body class="viz-root"><div class="wrap">
  {rh.brand_header("Weekly Marketing Report", f"Week of {wk_start.strftime('%b %-d')} – {d_end.strftime('%b %-d, %Y')}", f"{ACCOUNT_NAME} · " + " + ".join(["Google Ads", "Local Services Ads"] + (["Facebook Ads"] if meta_live else [])))}
  {tiles}
  {narrative}
  {beyond}
  {chan}
  <div style="margin-top:16px">{charts}</div>
  {table}
  {rh.brand_footer(footer_note)}
</div><div id="tip"></div>{rh.TIP_JS}</body></html>"""

    os.makedirs(OUT_DIR, exist_ok=True)
    html_path = os.path.join(OUT_DIR, f"exec-{today}.html")
    with open(html_path, "w") as f: f.write(html_out)
    _split = (f"ads {ads_wk['conv']:.0f}@{rh.fmt_usd(ads_cpl)} + LSA {lsa_wk['leads']}@{rh.fmt_usd(lsa_cpl)}"
              + (f" + Meta {meta_wk_leads:.0f}@{rh.fmt_usd(meta_cpl)}" if meta_live else ""))
    print(f"TOTAL: {tot_wk['leads']:.0f} leads · {rh.fmt_usd(tot_wk['cost'])} spend · CPL {rh.fmt_usd(cpl)} "
          f"({_split})")
    # Loud, internal-only. A blended CPL that silently omits a live channel reads better
    # than reality — that is the failure this whole change exists to prevent.
    meta_warn = ""
    if not meta_data.get("available") and meta_mod.load_meta_config():
        meta_warn = ("Meta is configured for this client but could not be read "
                     f"({meta_data.get('reason', 'unknown')}). Blended cost per lead above "
                     "EXCLUDES any Meta spend and is therefore optimistic if the campaign is live.")
        print(f"[META] ⚠️  {meta_warn}")
    elif meta_data.get("available") and not meta_live:
        print("[META] connected, no spend or results in this window — Meta omitted from the report by design.")
    for s in story: print("·", s)
    _internal = basis_notes.internal_note(pw_start, d_end)
    if _internal:
        print(f"[BASIS] {_internal}")
    print(f"[saved] {html_path}")

    if not no_discord:
        embed = {
            "title": f"{ACCOUNT_NAME} — Weekly Marketing Report · wk of {wk_start.strftime('%b %-d')}",
            "color": dp.BLUE,
            "description": f"**{tot_wk['leads']:.0f} total leads** · {rh.fmt_usd(tot_wk['cost'])} spend · **{rh.fmt_usd(cpl)}/lead blended**\n"
                           f"Search: {ads_wk['conv']:.0f} @ {rh.fmt_usd(ads_cpl)} · LSA: {lsa_wk['leads']} @ {rh.fmt_usd(lsa_cpl)}"
                           + (f" · Facebook: {meta_wk_leads:.0f} @ {rh.fmt_usd(meta_cpl)}" if meta_live else ""),
            "fields": [{"name": "Summary", "value": ("\n".join("• " + s for s in story))[:1024], "inline": False}]
                      + ([{"name": "⚠️ Meta not counted", "value": meta_warn[:1024], "inline": False}] if meta_warn else []),
            "footer": {"text": "Leadership-ready report attached — forward as is"},
        }
        ok = dp.post(DISCORD_WEBHOOK, embed=embed)
        print(f"[discord] {'posted OK' if ok else 'FAILED'}")

if __name__ == "__main__":
    main()
