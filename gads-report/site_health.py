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
    """Compact by default: one line when everything is healthy; a table of ONLY the
    problem pages when something is down, slow, or missing tracking."""
    rows = check_pages()
    if not rows:
        return ""
    up = [r for r in rows if r["status"] == 200]
    bad = [r for r in rows if r["status"] != 200]
    no_track = [r for r in up if not r["tracking"]]
    slow = [r for r in up if r["secs"] and r["secs"] > 4]
    times = [r["secs"] for r in rows if r["secs"] is not None]
    avg = sum(times) / len(times) if times else None
    if not bad and not no_track and not slow:
        line = (f"All {len(rows)} key pages up (homepage, market landing pages + top organic pages) · "
                f"average load {avg:.1f}s · tracking verified on every page." if avg else
                f"All {len(rows)} key pages up · tracking verified on every page.")
        return (f'<div class="card"><h2>{rh.E(title)}</h2>'
                f'<p style="margin:4px 0">{line}</p></div>')
    ok = lambda b: ('<span style="color:var(--goodtext);font-weight:600">OK</span>' if b
                    else '<span style="color:var(--crit);font-weight:600">CHECK</span>')
    # Fix Queue #20, 2026-08-13. The loop below used to rebind `up` and `slow` — the LISTS
    # built above — to per-row booleans. The next use of len(up) then raised
    # TypeError: object of type 'bool' has no len(), the caller's except swallowed it, and
    # the entire Website section vanished from the client report EXACTLY when a page was
    # down, i.e. the one time the section matters. Loop variables are now is_up / is_slow.
    # Do not reuse the list names inside the loop.
    n_total = len(rows)
    n_up = len(up)
    problem_rows = bad + slow + no_track  # only the problems get a table row
    body = ""
    for r in problem_rows:
        is_up = r["status"] == 200
        status_html = ok(True) if is_up else ok(False) + f' <span class="mut">({r["status"] or "no response"})</span>'
        speed = f'{r["secs"]:.1f}s' if r["secs"] is not None else "—"
        is_slow = r["secs"] is not None and r["secs"] > 4
        body += (f'<tr><td><b>{rh.E(r["label"])}</b><br><span class="mut">{rh.E(r["url"].replace("https://",""))}</span></td>'
                 f'<td class="num">{status_html}</td>'
                 f'<td class="num">{speed}{" ⚠" if is_slow else ""}</td>'
                 f'<td class="num">{ok(bool(r["tracking"])) if is_up else "—"}</td></tr>')
    sub = (f'<div class="mut" style="margin-top:8px">{n_up}/{n_total} pages up'
           + (f' · average load {avg:.1f}s' if avg else '')
           + ' · only pages needing attention are listed above</div>')
    return (f'<div class="card"><h2>{rh.E(title)}</h2><table>'
            '<tr><th>Page</th><th class="num">Up</th><th class="num">Load</th><th class="num">Tracking</th></tr>'
            + body + "</table>" + sub + "</div>")
