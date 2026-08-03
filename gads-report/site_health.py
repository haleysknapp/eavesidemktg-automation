#!/usr/bin/env python3
"""Website health checks for report inclusion: uptime, load time, tracking tag presence.
Pages listed in site-pages.txt as 'Label|URL' lines. Never raises — returns (rows, card_html)."""
import os, time
import requests

BASE = os.path.dirname(os.path.abspath(__file__))
PAGES_FILE = os.path.join(BASE, "site-pages.txt")
UA = {"User-Agent": "Mozilla/5.0 (compatible; EavesideReports/1.0)"}

def check_pages():
    rows = []
    if not os.path.exists(PAGES_FILE):
        return rows
    for line in open(PAGES_FILE):
        line = line.strip()
        if not line or line.startswith("#") or "|" not in line:
            continue
        label, url = [x.strip() for x in line.split("|", 1)]
        row = {"label": label, "url": url, "status": None, "secs": None, "tracking": None}
        try:
            t0 = time.time()
            r = requests.get(url, headers=UA, timeout=20, allow_redirects=True)
            row["secs"] = time.time() - t0
            row["status"] = r.status_code
            body = r.text.lower()
            row["tracking"] = ("googletagmanager" in body or "gtag(" in body or
                               "gtag.js" in body or "calltrk" in body)
        except Exception:
            row["status"] = 0
        rows.append(row)
    return rows

def card(rh, title="Website status"):
    rows = check_pages()
    if not rows:
        return ""
    ok = lambda b: ('<span style="color:var(--goodtext);font-weight:600">OK</span>' if b
                    else '<span style="color:var(--crit);font-weight:600">CHECK</span>')
    body = ""
    for r in rows:
        up = r["status"] == 200
        status_html = ok(True) if up else ok(False) + f' <span class="mut">({r["status"] or "no response"})</span>'
        speed = f'{r["secs"]:.1f}s' if r["secs"] is not None else "—"
        slow = r["secs"] is not None and r["secs"] > 4
        body += (f'<tr><td><b>{rh.E(r["label"])}</b><br><span class="mut">{rh.E(r["url"].replace("https://",""))}</span></td>'
                 f'<td class="num">{status_html}</td>'
                 f'<td class="num">{speed}{" ⚠" if slow else ""}</td>'
                 f'<td class="num">{ok(bool(r["tracking"])) if up else "—"}</td></tr>')
    n_up = sum(1 for r in rows if r["status"] == 200)
    sub = f'<div class="mut" style="margin-top:8px">{n_up}/{len(rows)} pages up · load time measured from data center · tracking = Google tag / call tracking detected</div>'
    return (f'<div class="card"><h2>{rh.E(title)}</h2><table>'
            '<tr><th>Page</th><th class="num">Up</th><th class="num">Load</th><th class="num">Tracking</th></tr>'
            + body + "</table>" + sub + "</div>")
