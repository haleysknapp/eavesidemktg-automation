#!/usr/bin/env python3
"""
Roofing Force — weekly search-terms analyzer (Mondays).
16-week lookback with week-by-week pacing. Verdicts:
  CUT    — junk with any spend; competitor $60+/0conv across 3+ wks; relevant $90+/0conv
  WATCH  — $30+/0conv (on the radar); competitor names at low spend
  REVIEW — converts, but CPL > 2x the $180 target
Outputs HTML + posts to Discord. Recommend-only: nothing is changed in the account.

Usage: python3 weekly_terms.py [--no-discord]
"""
import os, sys, json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import google_ads_client, CUSTOMER_ID, ACCOUNT_NAME, DISCORD_WEBHOOK, BASE_DIR
from classify import classify, verdict, load_competitors, load_brands, TARGET_CPL, CUT_RELEVANT_SPEND, CUT_RELEVANT_CLICKS, WATCH_SPEND
import render_html as rh
import discord_post as dp

TZ = ZoneInfo("America/Denver")
OUT_DIR = os.path.join(BASE_DIR, "out")
LOOKBACK_WEEKS = 16

def money(m): return m / 1_000_000

def fetch(client, d_start, d_end):
    svc = client.get_service("GoogleAdsService")
    q = f"""
      SELECT search_term_view.search_term, search_term_view.status,
             campaign.name, segments.week,
             metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions
      FROM search_term_view
      WHERE segments.date BETWEEN '{d_start}' AND '{d_end}'
    """
    rows = list(svc.search(customer_id=CUSTOMER_ID, query=q))
    q2 = f"""
      SELECT campaign.name, metrics.cost_micros FROM campaign
      WHERE segments.date BETWEEN '{d_start}' AND '{d_end}'
        AND campaign.status IN ('ENABLED','PAUSED')
    """
    camp_cost = {}
    for r in svc.search(customer_id=CUSTOMER_ID, query=q2):
        camp_cost[r.campaign.name] = camp_cost.get(r.campaign.name, 0) + money(r.metrics.cost_micros)
    return rows, camp_cost

def analyze(rows, competitors, brands):
    terms = {}
    for r in rows:
        cost = money(r.metrics.cost_micros)
        if cost == 0 and r.metrics.clicks == 0:
            continue
        key = r.search_term_view.search_term
        t = terms.setdefault(key, {
            "term": key, "status": r.search_term_view.status.name,
            "campaigns": set(), "weeks": defaultdict(float),
            "cost": 0.0, "clicks": 0, "impr": 0, "conv": 0.0,
        })
        t["campaigns"].add(r.campaign.name)
        t["weeks"][str(r.segments.week)] += cost
        t["cost"] += cost
        t["clicks"] += r.metrics.clicks
        t["impr"] += r.metrics.impressions
        t["conv"] += r.metrics.conversions

    out = []
    for t in terms.values():
        cat, detail = classify(t["term"], competitors, brands)
        weeks_active = sum(1 for v in t["weeks"].values() if v > 0)
        v, reason = verdict(cat, t["cost"], t["conv"], weeks_active, term=t["term"], clicks=t["clicks"])
        if t["status"] == "EXCLUDED":     # already negated
            continue
        t.update({"cat": cat, "cat_detail": detail, "weeks_active": weeks_active,
                  "verdict": v, "reason": reason,
                  "wk_avg": t["cost"] / max(weeks_active, 1),
                  "campaigns": sorted(t["campaigns"])})
        out.append(t)
    return out

def week_spark(t, all_weeks):
    """Tiny per-term pacing bars over the lookback weeks."""
    vals = [t["weeks"].get(w, 0.0) for w in all_weeks]
    mx = max(vals) or 1
    n = len(vals); w_px, h = 6, 22
    W = n * w_px
    bars = []
    for i, v in enumerate(vals):
        bh = max(1.5, (v / mx) * (h - 4)) if v > 0 else 0
        if bh:
            bars.append(f'<rect x="{i*w_px+1}" y="{h-bh:.1f}" width="{w_px-2}" height="{bh:.1f}" '
                        f'rx="1" fill="var(--s1)"/>')
    return f'<svg width="{W}" height="{h}" aria-hidden="true"><line x1="0" y1="{h-0.5}" x2="{W}" y2="{h-0.5}" stroke="var(--baseline)" stroke-width="1"/>{"".join(bars)}</svg>'

CAT_LABEL = {"junk": "Junk", "brand": "Materials brand", "competitor": "Competitor",
             "maybe_company": "Company name?", "relevant": "Relevant"}

def render(run_date, d_start, d_end, terms, all_weeks, camp_cost):
    E = rh.E; fmt = rh.fmt_usd
    cuts = sorted([t for t in terms if t["verdict"] == "CUT"], key=lambda t: -t["cost"])
    verify = sorted([t for t in terms if t["verdict"] == "VERIFY"], key=lambda t: -t["cost"])
    watch = sorted([t for t in terms if t["verdict"] == "WATCH"], key=lambda t: -t["cost"])
    review = sorted([t for t in terms if t["verdict"] == "REVIEW"], key=lambda t: -t["cost"])
    cut_cost = sum(t["cost"] for t in cuts)
    verify_cost = sum(t["cost"] for t in verify)
    watch_cost = sum(t["cost"] for t in watch)
    total_camp = sum(camp_cost.values())
    visible_cost = sum(t["cost"] for t in terms)
    hidden_cost = max(0.0, total_camp - visible_cost)
    hidden_pct = hidden_cost / total_camp * 100 if total_camp else 0

    tiles = f"""
    <div class="tiles">
      <div class="tile"><div class="label">Cut — add as negatives</div>
        <div class="value">{len(cuts)}</div>
        <div class="delta neutral">{fmt(cut_cost)} spent over {LOOKBACK_WEEKS} wks with nothing to show</div></div>
      <div class="tile"><div class="label">Verify — competitor?</div>
        <div class="value">{len(verify)}</div>
        <div class="delta neutral">{fmt(verify_cost)} on names that need a quick check</div></div>
      <div class="tile"><div class="label">Watch list</div>
        <div class="value">{len(watch)}</div>
        <div class="delta neutral">{fmt(watch_cost)} so far — not at the cut bar yet</div></div>
      <div class="tile"><div class="label">Review — expensive</div>
        <div class="value">{len(review)}</div>
        <div class="delta neutral">real queries burning cash — fix fit, do not negate</div></div>
      <div class="tile"><div class="label">Hidden "other terms" spend</div>
        <div class="value">{hidden_pct:.0f}%</div>
        <div class="delta neutral">{fmt(hidden_cost)} of {fmt(total_camp)} not shown in the search-terms report</div></div>
    </div>"""

    def table(title, ts, empty):
        if not ts:
            body = f'<tr><td colspan="7" class="mut">{empty}</td></tr>'
        else:
            rows = []
            for t in ts[:60]:
                cpl = fmt(t["cost"]/t["conv"]) if t["conv"] else "—"
                rows.append(f"""<tr>
                  <td><b>{E(t['term'])}</b><br><span class="mut">{E(', '.join(t['campaigns']))}{' · already an added keyword' if t['status']=='ADDED' else ''}</span></td>
                  <td>{CAT_LABEL[t['cat']]}</td>
                  <td class="num">{fmt(t['cost'],2)}</td>
                  <td class="num">{t['clicks']}</td>
                  <td class="num">{t['conv']:.1f}</td>
                  <td>{week_spark(t, all_weeks)}<br><span class="mut">{t['weeks_active']} of {LOOKBACK_WEEKS} wks · ~{fmt(t['wk_avg'])}/wk</span></td>
                  <td class="sub">{E(t['reason'])}</td></tr>""")
            body = "".join(rows)
        return f"""<div class="card"><h2>{title}</h2><table>
          <tr><th>Term</th><th>Type</th><th class="num">Cost {LOOKBACK_WEEKS}wk</th>
          <th class="num">Clicks</th><th class="num">Leads</th><th>Weekly pacing</th><th>Why</th></tr>
          {body}</table></div>"""

    # SOP-aligned negatives: competitor -> broadened "phrase" campaign-level;
    # junk/brand/relevant -> [exact] per campaign. Erie stays out of St. Louis (conquest).
    by_camp, log_rows, erie_skips, proposals = {}, [], [], []
    added_cuts = [t for t in cuts if t["status"] == "ADDED"]
    for t in cuts:
        if t["status"] == "ADDED":
            continue
        if t["cat"] == "competitor":
            raw = t["cat_detail"] or t["term"]
            text = '"' + raw + '"'; mtype = "phrase"
        else:
            raw = t["term"]
            text = "[" + raw + "]"; mtype = "exact"
        camps_ok = []
        for cname in t["campaigns"]:
            if "st. louis" in cname.lower() or "st louis" in cname.lower():
                if "erie" in t["term"].lower():
                    erie_skips.append(t["term"]); continue
            camps_ok.append(cname)
            by_camp.setdefault(cname, set()).add(text)
            log_rows.append((run_date, text, mtype, cname, f"${t['cost']:.2f}", "0",
                             t["reason"], "n/a (0 conv)", "Claude sweep (recommended)"))
        if camps_ok:
            proposals.append({"term": raw, "match": mtype, "campaigns": sorted(set(camps_ok)),
                              "cost": round(t["cost"], 2), "clicks": t["clicks"],
                              "leads": round(t["conv"], 1), "reason": t["reason"], "cat": t["cat"]})
    neg_list = "\n".join(
        f"--- {c} (add at campaign level) ---\n" + "\n".join(sorted(v))
        for c, v in sorted(by_camp.items()))
    log_tsv = "date\tterm\tmatch\twhere added\tspend at add\tconv at add\twhy\tlead-quality check\tadded by\n" +               "\n".join("\t".join(r) for r in log_rows)
    added_note = ""
    if added_cuts:
        added_note = ('<div class="sub" style="margin-top:8px">⚠️ These CUT terms are keywords you actively bid on — '
                      'pause the keyword instead of adding a negative: <b>'
                      + ", ".join(E(t["term"]) for t in added_cuts) + "</b></div>")
    if erie_skips:
        added_note += ('<div class="sub" style="margin-top:8px">🛡️ Held out of St. Louis (deliberate Erie conquest per SOP): <b>'
                       + ", ".join(E(x) for x in sorted(set(erie_skips))) + "</b></div>")

    html_doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(ACCOUNT_NAME)} — search terms weekly · {run_date}</title>
<style>{rh.CSS}</style></head>
<body class="viz-root"><div class="wrap">
  {rh.brand_header("Search Terms Review", f"{run_date}", f"{ACCOUNT_NAME} · lookback {d_start} → {d_end} ({LOOKBACK_WEEKS} weeks) · junk = cut at any spend · relevant = cut at {fmt(CUT_RELEVANT_SPEND)}/0 leads · watch from {fmt(WATCH_SPEND)}")}
  {tiles}
  {table("✂️ CUT — add these as negatives", cuts, "Nothing to cut this week.")}
  {table("❓ VERIFY — looks like a company name; competitor or coincidence?", verify, "Nothing to verify.")}
  {table("👀 WATCH — building evidence, not at the cut bar yet", watch[:25], "Watch list is empty.")}
  {table("🔍 REVIEW — real queries that are expensive (do NOT negate)", review, "Nothing in review.")}
  <div class="card"><h2>Negatives to add — grouped by campaign · "quotes" = phrase (competitors, broadened) · [brackets] = exact</h2>
    <button class="copybtn" data-target="neglist">Copy list</button>
    <div class="copy" id="neglist">{E(neg_list) or "(nothing to cut)"}</div>{added_note}</div>
  <div class="card"><h2>Negatives Log rows — paste into the GADS tracker "Negatives Log" tab after adding</h2>
    <button class="copybtn" data-target="loglist">Copy rows (TSV)</button>
    <div class="copy" id="loglist" style="font-size:11px">{E(log_tsv) if log_rows else "(nothing to log)"}</div></div>
  <div class="mut" style="margin-top:20px">Recommend-only: no changes were made to the account.
    Competitor names come from competitors.txt — tell Claude to add/remove names.
    Excluded (already-negated) terms are filtered out automatically.</div>
</div><div id="tip"></div>{rh.TIP_JS}</body></html>"""
    return html_doc, cuts, verify, watch, review, cut_cost, proposals

def main():
    no_discord = "--no-discord" in sys.argv
    today = datetime.now(TZ).date()
    d_end = today - timedelta(days=1)
    d_start = today - timedelta(weeks=LOOKBACK_WEEKS)
    client = google_ads_client()
    rows, camp_cost = fetch(client, d_start, d_end)
    competitors = load_competitors()
    brands = load_brands()
    terms = analyze(rows, competitors, brands)
    # ordered list of ISO weeks present, ascending
    all_weeks = sorted({w for t in terms for w in t["weeks"]})

    html_out, cuts, verify, watch, review, cut_cost, proposals = render(str(today), d_start, d_end, terms, all_weeks, camp_cost)
    os.makedirs(OUT_DIR, exist_ok=True)
    html_path = os.path.join(OUT_DIR, f"terms-{today}.html")
    with open(html_path, "w") as f: f.write(html_out)

    top_cuts = "\n".join(f'✂️ "{t["term"]}" — {rh.fmt_usd(t["cost"],2)}, {t["conv"]:.0f} leads ({t["cat"]})'
                         for t in cuts[:8]) or "Nothing to cut this week 🎉"
    print(f"CUT {len(cuts)} (${cut_cost:,.0f} wasted) · VERIFY {len(verify)} · WATCH {len(watch)} · REVIEW {len(review)}")
    if verify:
        print("VERIFY (web-check these, real competitors go in competitors.txt):")
        for t in verify[:10]:
            print("? " + t["term"] + " — " + rh.fmt_usd(t["cost"],2) + f", {t['clicks']} clicks")
    print(top_cuts)
    print(f"[saved] {html_path}")
    if not no_discord:
        # save numbered proposals so the hourly inbox run can apply approvals by number
        state_dir = os.path.join(BASE_DIR, "state")
        os.makedirs(state_dir, exist_ok=True)
        with open(os.path.join(state_dir, "pending_negatives.json"), "w") as f:
            json.dump({"date": str(today),
                       "proposals": [{"n": i + 1, **p} for i, p in enumerate(proposals)]}, f, indent=1)

        def shorten(c):  # campaign display names
            return (c.replace(" New Search", "").replace(" - Search", "")
                     .replace("Kansas City", "KC"))
        # compact dark table image of the proposals (Discord renders it inline)
        CAT_SHORT = {"competitor": "competitor", "brand": "materials", "junk": "junk",
                     "maybe_company": "company?", "relevant": "relevant"}
        trs = "".join(
            f"<tr><td class='n'>{i+1}</td><td class='t'>{rh.E(p['term'])}</td>"
            f"<td>{CAT_SHORT.get(p['cat'], p['cat'])}</td>"
            f"<td>{rh.E(', '.join(shorten(c) for c in p['campaigns']))}</td>"
            f"<td class='r'>${p['cost']:,.0f}</td><td class='r'>{p['clicks']}</td></tr>"
            for i, p in enumerate(proposals))
        table_html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
          body {{ margin:0; background:#1e1f22; font:15px/1.45 -apple-system,'Segoe UI',Roboto,sans-serif; color:#dbdee1; }}
          table {{ border-collapse:collapse; width:880px; }}
          th {{ text-align:left; font-size:12px; letter-spacing:.06em; text-transform:uppercase;
               color:#949ba4; padding:10px 14px 8px; border-bottom:1px solid #3f4147; }}
          td {{ padding:8px 14px; border-bottom:1px solid #2b2d31; }}
          tr:nth-child(even) td {{ background:#232428; }}
          .n {{ color:#949ba4; width:24px; }} .t {{ font-weight:600; color:#f2f3f5; }}
          .r {{ text-align:right; font-variant-numeric:tabular-nums; }}
          th.r {{ text-align:right; }}
        </style></head><body><table>
          <tr><th>#</th><th>Search term</th><th>Type</th><th>Campaign</th><th class="r">Wasted</th><th class="r">Clicks</th></tr>
          {trs}</table></body></html>"""
        img_path = None
        if proposals:
            tbl_path = os.path.join(OUT_DIR, f"terms-{today}-proposals.html")
            open(tbl_path, "w").write(table_html)
            img_path = dp.render_png(tbl_path, width=880)
        embed = {
            "title": f"{ACCOUNT_NAME} — Search Terms · {today}",
            "color": dp.RED if proposals else dp.GREEN,
            "description": f"**{len(proposals)} proposed negatives** — {rh.fmt_usd(cut_cost)} spent, 0 leads · ranked by wasted spend",
            "fields": ([{"name": "To approve", "value": "Reply **approve all**, **approve 1, 3**, or **all except 2** — I'll apply them campaign-level, confirm here, and log them.", "inline": False}]
                       if proposals else
                       [{"name": "Nothing to cut", "value": "No junk above the spend bar this run 🎉", "inline": False}]),
        }
        # attach the proposals JSON so the live bot (running elsewhere) can
        # map "approve 1, 3" to exact terms without sharing a filesystem
        attachments = []
        pend = os.path.join(BASE_DIR, "state", "pending_negatives.json")
        if proposals and os.path.exists(pend):
            attachments.append(pend)
        ok = dp.post(DISCORD_WEBHOOK, embed=embed, file_path=attachments or None, image_path=img_path)
        print(f"[discord] {'posted OK' if ok else 'FAILED'}")

if __name__ == "__main__":
    main()
