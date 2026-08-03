"""Polished HTML rendering for the Roofing Force reports — Eaveside × Roofing Force branding."""
import html as _html
import json
import os as _os
import base64 as _b64

E = _html.escape

# ---- embedded assets (logo + Inter font) ----
_ASSET_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "assets")

def _asset_b64(name):
    try:
        with open(_os.path.join(_ASSET_DIR, name), "rb") as f:
            return _b64.b64encode(f.read()).decode()
    except Exception:
        return ""

_RF_LOGO_B64 = _asset_b64("rf-logo.png")

def _font_face(weight, fname):
    b = _asset_b64(fname)
    if not b: return ""
    return ("@font-face{font-family:'Inter';font-style:normal;font-weight:%d;font-display:swap;"
            "src:url(data:font/woff2;base64,%s) format('woff2');}" % (weight, b))

FONT_CSS = (_font_face(400, "inter-latin-400-normal.woff2") +
            _font_face(600, "inter-latin-600-normal.woff2") +
            _font_face(800, "inter-latin-800-normal.woff2"))

def brand_header(kicker, title, sub):
    """Eaveside × Roofing Force report masthead."""
    logo = (f'<span class="logobox"><img src="data:image/png;base64,{_RF_LOGO_B64}" alt="Roofing Force" class="rf-logo"></span>'
            if _RF_LOGO_B64 else '<span class="logotext">ROOFING FORCE</span>')
    return f"""
  <div class="masthead">
    {logo}
    <div class="mast-right">
      <div class="ewordmark">EAVESIDE</div>
      <div class="mast-sub">Marketing performance</div>
    </div>
  </div>
  <div class="titleblock">
    <div class="kicker">{E(kicker)}</div>
    <h1>{E(title)}</h1>
    <div class="sub">{E(sub)}</div>
  </div>
  <div class="rule"></div>"""

def brand_footer(note=""):
    n = f'<div class="mut" style="margin-top:14px">{E(note)}</div>' if note else ""
    return f"""{n}
  <div class="footer">
    <span class="ewordmark small">EAVESIDE</span>
    <span class="footnote">Prepared by Eaveside · eaveside.com · for Roofing Force leadership</span>
  </div>"""

# ---- palette (brand: Eaveside slate #3a5a72 structure · RF red #d02028 accent;
#      chart series validated light [#2569a3,#d02028] / dark [#4f95d6,#e2565e]) ----
CSS = FONT_CSS + """
:root { color-scheme: light dark; }
.viz-root {
  --page:#f6f5f2; --surface:#ffffff; --ink:#16181d; --ink2:#4d5560; --muted:#8a8f98;
  --grid:#e7e6e1; --baseline:#c9c8c0; --border:rgba(22,24,29,.09);
  --slate:#3a5a72; --red:#d02028;
  --s1:#2569a3; --s1-track:#d3e4f2; --s2:#d02028;
  --good:#0ca30c; --goodtext:#006300; --warn:#fab219; --serious:#ec835a; --crit:#b0322f;
  --shadow:0 1px 3px rgba(22,24,29,.06), 0 4px 16px rgba(22,24,29,.04);
}
@media (prefers-color-scheme: dark) {
  .viz-root {
    --page:#101114; --surface:#1a1c21; --ink:#f2f3f5; --ink2:#b8bdc6; --muted:#868b94;
    --grid:#2a2d33; --baseline:#3b3f47; --border:rgba(255,255,255,.09);
    --slate:#8fb0c9; --red:#e2565e;
    --s1:#4f95d6; --s1-track:#1c466e; --s2:#e2565e;
    --good:#0ca30c; --goodtext:#31c231; --warn:#fab219; --serious:#ec835a; --crit:#e05d5a;
    --shadow:none;
  }
}
* { box-sizing:border-box; }
body { margin:0; background:var(--page); color:var(--ink);
  font-family:'Inter',system-ui,-apple-system,"Segoe UI",sans-serif; font-size:14px; line-height:1.5;
  -webkit-font-smoothing:antialiased; }
.wrap { max-width:1040px; margin:0 auto; padding:36px 24px 56px; }
/* masthead */
.masthead { display:flex; align-items:center; justify-content:space-between; gap:16px; }
.logobox { display:inline-flex; background:#fff; border-radius:12px; padding:10px 14px;
  border:1px solid var(--border); }
.rf-logo { height:54px; display:block; }
.logotext { font-weight:800; letter-spacing:.14em; font-size:16px; }
.mast-right { text-align:right; }
.ewordmark { font-weight:800; font-size:15px; letter-spacing:.22em; color:var(--slate); }
.ewordmark.small { font-size:11px; letter-spacing:.2em; }
.mast-sub { font-size:11px; color:var(--muted); letter-spacing:.04em; margin-top:2px; }
.titleblock { margin-top:26px; }
.kicker { font-size:11.5px; font-weight:700; text-transform:uppercase; letter-spacing:.14em;
  color:var(--red); }
h1 { font-size:34px; font-weight:800; letter-spacing:-.02em; margin:2px 0 4px; }
.rule { height:3px; margin-top:18px; border-radius:2px;
  background:linear-gradient(90deg, var(--red) 0 96px, var(--slate) 96px 128px, var(--grid) 128px 100%); }
.footer { display:flex; align-items:baseline; gap:12px; margin-top:32px; padding-top:14px;
  border-top:1px solid var(--grid); }
.footnote { font-size:11px; color:var(--muted); }
.sub { color:var(--ink2); font-size:12.5px; }
.mut { color:var(--muted); font-size:12px; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:14px;
  padding:18px 20px; margin-top:16px; box-shadow:var(--shadow); }
@media print {
  .card, .tile, .chart, .charts > * { break-inside:avoid; page-break-inside:avoid; }
  .tiles { break-inside:avoid; }
  .wrap { padding-top:16px; }
}
h2 { display:flex; align-items:center; gap:8px; font-size:11.5px; font-weight:700; margin:0 0 12px;
  letter-spacing:.1em; text-transform:uppercase; color:var(--slate); }
h2::before { content:""; width:16px; height:3px; border-radius:2px; background:var(--red); flex:none; }
/* stat tiles */
.tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; margin-top:16px; }
.tile { background:var(--surface); border:1px solid var(--border); border-radius:14px; padding:16px 18px;
  box-shadow:var(--shadow); }
.tile .label { font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.07em; color:var(--muted); }
.tile .value { font-size:30px; font-weight:800; letter-spacing:-.02em; margin-top:4px;
  font-variant-numeric:tabular-nums; }
.tile .delta { font-size:12px; margin-top:2px; }
.up-good { color:var(--goodtext); } .down-bad { color:var(--crit); } .neutral { color:var(--ink2); }
/* alerts */
.alert { display:flex; gap:10px; align-items:baseline; padding:7px 0; border-bottom:1px solid var(--grid); }
.alert:last-child { border-bottom:none; }
.badge { flex:none; font-size:11px; font-weight:650; border-radius:5px; padding:1px 8px; }
.b-crit { background:var(--crit); color:#fff; } .b-serious { background:var(--serious); color:#1a1a19; }
.b-warn { background:var(--warn); color:#1a1a19; } .b-good { background:var(--good); color:#fff; }
.b-info { background:transparent; color:var(--ink2); border:1px solid var(--baseline); }
/* tables */
table { border-collapse:collapse; width:100%; font-size:13px; }
th { text-align:left; font-weight:600; font-size:11px; text-transform:uppercase; letter-spacing:.02em;
  color:var(--muted); padding:6px 10px; border-bottom:1px solid var(--baseline); }
td { padding:8px 10px; border-bottom:1px solid var(--grid); vertical-align:top; }
tr:last-child td { border-bottom:none; }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
.meter { height:6px; border-radius:3px; background:var(--s1-track); margin-top:5px; width:110px; overflow:hidden; }
.meter > div { height:100%; border-radius:3px; }
.qs { display:inline-block; min-width:20px; text-align:center; font-weight:600; font-variant-numeric:tabular-nums; }
.dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; vertical-align:baseline; }
/* charts */
.charts { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
@media (max-width:720px){ .charts { grid-template-columns:1fr; } }
svg text { font-family:inherit; }
.copy { background:var(--page); border:1px solid var(--grid); border-radius:8px; padding:12px;
  font-size:12px; font-family:ui-monospace,Menlo,monospace; white-space:pre-wrap; }
.copybtn { font:inherit; font-size:12px; border:1px solid var(--baseline); border-radius:6px;
  background:var(--surface); color:var(--ink); padding:4px 12px; cursor:pointer; margin-bottom:8px; }
.copybtn:hover { background:var(--page); }
#tip { position:fixed; pointer-events:none; background:var(--surface); border:1px solid var(--border);
  border-radius:8px; padding:7px 10px; font-size:12px; box-shadow:0 4px 14px rgba(0,0,0,.12);
  display:none; z-index:10; }
"""

TIP_JS = """
<script>
(function(){
  var tip = document.getElementById('tip');
  document.querySelectorAll('[data-tip]').forEach(function(el){
    el.addEventListener('mousemove', function(ev){
      tip.innerHTML = el.getAttribute('data-tip');
      tip.style.display = 'block';
      var x = ev.clientX + 14, y = ev.clientY + 14;
      var r = tip.getBoundingClientRect();
      if (x + r.width > window.innerWidth - 8) x = ev.clientX - r.width - 10;
      if (y + r.height > window.innerHeight - 8) y = ev.clientY - r.height - 10;
      tip.style.left = x + 'px'; tip.style.top = y + 'px';
    });
    el.addEventListener('mouseleave', function(){ tip.style.display='none'; });
  });
  document.querySelectorAll('.copybtn[data-target]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var el = document.getElementById(btn.getAttribute('data-target'));
      navigator.clipboard.writeText(el.innerText).then(function(){
        var orig = btn.textContent;
        btn.textContent = 'Copied ✓'; setTimeout(function(){ btn.textContent = orig; }, 1500);
      });
    });
  });
})();
</script>
"""

def fmt_usd(x, dec=0): return f"${x:,.{dec}f}"
def pct(x): return f"{x*100:.0f}%" if x is not None else "—"

def _delta(new, old, up_good=None, suffix=""):
    """Signed delta vs a named period. up_good True/False colors it; None = neutral."""
    if old in (0, None):
        return '<span class="delta neutral">—</span>'
    d = (new - old) / old * 100
    sign = "+" if d >= 0 else "−"
    cls = "neutral"
    if up_good is True:  cls = "up-good" if d >= 0 else "down-bad"
    if up_good is False: cls = "down-bad" if d > 0 else "up-good"
    return f'<span class="delta {cls}">{sign}{abs(d):.0f}%{suffix}</span>'

def _spark(series, w=120, h=30, color="var(--muted)", accent="var(--s1)"):
    """12–14 pt sparkline: line in de-emphasis hue, last point accented w/ surface ring."""
    if not series or max(series) == 0:
        return ""
    n = len(series); mx = max(series) or 1
    pts = [(i * (w - 8) / (n - 1) + 4, h - 4 - (v / mx) * (h - 10)) for i, v in enumerate(series)]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
    lx, ly = pts[-1]
    return (f'<svg width="{w}" height="{h}" aria-hidden="true">'
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2" '
            f'stroke-linejoin="round" stroke-linecap="round" opacity="0.55"/>'
            f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="4.5" fill="var(--surface)"/>'
            f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3" fill="{accent}"/></svg>')

def _nice_max(v):
    if v <= 0: return 1
    import math
    mag = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * mag: return m * mag
    return 10 * mag

def _bar_chart(title, days, values, color, fmt, tipfmt):
    """Single-series daily column chart. ≤24px columns, 4px rounded cap, square baseline,
    2px surface gap, hairline gridlines, clean y ticks, per-mark hover tooltip."""
    W, H, PL, PB, PT = 470, 190, 44, 26, 14
    n = len(days)
    top = _nice_max(max(values) if values else 1)
    plot_w, plot_h = W - PL - 10, H - PB - PT
    slot = plot_w / n
    bw = min(24, max(6, slot - 2))          # 2px surface gap between adjacent bars
    parts = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="{E(title)}">']
    # gridlines + ticks (0, half, top)
    for frac in (0, .5, 1):
        y = PT + plot_h * (1 - frac)
        v = top * frac
        parts.append(f'<line x1="{PL}" y1="{y:.1f}" x2="{W-10}" y2="{y:.1f}" '
                     f'stroke="var(--{"baseline" if frac==0 else "grid"})" stroke-width="1"/>')
        parts.append(f'<text x="{PL-6}" y="{y+4:.1f}" text-anchor="end" font-size="10" '
                     f'fill="var(--muted)">{fmt(v)}</text>')
    for i, (d, v) in enumerate(zip(days, values)):
        x = PL + i * slot + (slot - bw) / 2
        bh = (v / top) * plot_h if top else 0
        y = PT + plot_h - bh
        r = min(4, bh)  # rounded data-end only; square baseline
        parts.append(
            f'<path d="M{x:.1f},{PT+plot_h:.1f} V{y+r:.1f} Q{x:.1f},{y:.1f} {x+r:.1f},{y:.1f} '
            f'H{x+bw-r:.1f} Q{x+bw:.1f},{y:.1f} {x+bw:.1f},{y+r:.1f} V{PT+plot_h:.1f} Z" '
            f'fill="{color}" data-tip="{E(tipfmt(d, v))}"/>')
        if i % 2 == (n - 1) % 2:  # every other label, always incl. last
            parts.append(f'<text x="{x+bw/2:.1f}" y="{H-8}" text-anchor="middle" font-size="9.5" '
                         f'fill="var(--muted)">{d[5:].replace("-","/")}</text>')
    parts.append('</svg>')
    return (f'<div class="card"><h2>{E(title)}</h2>' + "".join(parts) + '</div>')

BADGE = {"critical": ("b-crit", "STOPPED"), "serious": ("b-serious", "PACING"),
         "warning": ("b-warn", "WATCH"), "good": ("b-good", "SCALE"), "info": ("b-info", "NOTE")}

def _qs_dot(qs):
    if qs is None: return '<span class="mut">—</span>'
    color = "var(--good)" if qs >= 7 else ("var(--warn)" if qs >= 5 else "var(--crit)")
    return f'<span class="dot" style="background:{color}"></span><span class="qs">{qs}</span>'

def render(run_date, account_name, account_id, camps, urgent, notes, daily, terms_yest):
    """Daily report: tiles -> urgent alerts -> campaigns -> charts -> yesterday's terms -> notes."""
    enabled = sorted([c for c in camps.values() if c["status"] == "ENABLED"],
                     key=lambda c: -c["last7"]["cost"])
    tot = {b: {k: sum(c[b][k] for c in enabled) for k in ("cost", "clicks", "conv", "value")}
           for b in ("yest", "last7", "prev7")}
    y, l7, p7 = tot["yest"], tot["last7"], tot["prev7"]
    cpl_y = y["cost"] / y["conv"] if y["conv"] else None
    cpl_7 = l7["cost"] / l7["conv"] if l7["conv"] else None
    cpl_p7 = p7["cost"] / p7["conv"] if p7["conv"] else None
    avg7 = l7["cost"] / 7

    spend_series = [d["cost"] for d in daily]
    conv_series = [d["conv"] for d in daily]
    days = [d["date"] for d in daily]

    tiles = f"""
    <div class="tiles" style="grid-template-columns:repeat(3,1fr)">
      <div class="tile"><div class="label">Spend yesterday</div>
        <div class="value">{fmt_usd(y['cost'])}</div>
        <div>{_delta(y['cost'], avg7)} <span class="mut">vs 7-day avg/day</span></div>
        {_spark(spend_series)}</div>
      <div class="tile"><div class="label">Leads yesterday</div>
        <div class="value">{y['conv']:.0f}</div>
        <div>{_delta(y['conv'], l7['conv']/7, up_good=True)} <span class="mut">vs 7-day avg/day</span></div>
        {_spark(conv_series)}</div>
      <div class="tile"><div class="label">CPL yesterday</div>
        <div class="value">{fmt_usd(cpl_y) if cpl_y else '—'}</div>
        <div>{_delta(cpl_y, cpl_7, up_good=False) if cpl_y and cpl_7 else '<span class="delta neutral">—</span>'} <span class="mut">vs 7-day CPL</span></div></div>
      <div class="tile"><div class="label">Spend last 7 days</div>
        <div class="value">{fmt_usd(l7['cost'])}</div>
        <div>{_delta(l7['cost'], p7['cost'])} <span class="mut">vs prior 7 days</span></div></div>
      <div class="tile"><div class="label">Leads last 7 days</div>
        <div class="value">{l7['conv']:.0f}</div>
        <div>{_delta(l7['conv'], p7['conv'], up_good=True)} <span class="mut">vs prior 7 days ({p7['conv']:.0f})</span></div></div>
      <div class="tile"><div class="label">CPL last 7 days</div>
        <div class="value">{fmt_usd(cpl_7) if cpl_7 else '—'}</div>
        <div>{_delta(cpl_7, cpl_p7, up_good=False) if cpl_7 and cpl_p7 else '<span class="delta neutral">—</span>'} <span class="mut">vs prior 7 days ({fmt_usd(cpl_p7) if cpl_p7 else '—'})</span></div></div>
    </div>"""

    def alert_rows(items):
        return "".join(
            f'<div class="alert"><span class="badge {BADGE[a["level"]][0]}">{BADGE[a["level"]][1]}</span>'
            f'<span>{E(a["msg"])}</span></div>' for a in items)
    urgent_html = (f'<div class="card" style="border-color:var(--crit)"><h2>⚠ Needs attention today</h2>'
                   f'{alert_rows(urgent)}</div>') if urgent else ""
    notes_html = (f'<div class="card"><h2>Notes (structural, not urgent)</h2>{alert_rows(notes)}</div>') if notes else ""

    def row_camp(c):
        cy, s, p = c["yest"], c["last7"], c["prev7"]
        cpl = s["cost"]/s["conv"] if s["conv"] else None
        pace = cy["cost"]/c["budget"] if c["budget"] else 0
        pace_color = "#c0392b" if pace < 0.3 else ("#e67e22" if pace < 0.7 else "#27ae60")
        lost = f'{pct(c["is"])}<br><span class="sub">rank −{pct(c["lost_rank"])} · budget −{pct(c["lost_budget"])}</span>' if c["is"] is not None else '<span class="mut">—</span>'
        return f"""<tr><td><b>{E(c['name'])}</b><br><span class="mut">{E(c['bid_label'])}</span></td>
        <td class="num">{fmt_usd(cy['cost'])}<br><span class="mut">{cy['conv']:.0f} leads</span></td>
        <td class="num">{fmt_usd(s['cost'])} <span class="delta">{delta_html(s['cost'],p['cost'])}</span><br><span class="mut">{s['conv']:.0f} leads {delta_html(s['conv'],p['conv'],True)}</span></td>
        <td class="num">{fmt_usd(cpl) if cpl else '—'}</td>
        <td><span class="sub">{fmt_usd(cy['cost'])} of {fmt_usd(c['budget'])} ({pace*100:.0f}%)</span>
        <div class="meter"><div style="width:{min(pace,1)*100:.0f}%;background:{pace_color}"></div></div></td>
        <td>{lost}</td></tr>"""
    camp_html = f"""<div class="card"><h2>Campaigns</h2><table>
      <tr><th>Campaign</th><th class="num">Yesterday</th><th class="num">Last 7d vs prior</th>
      <th class="num">CPL 7d</th><th>Budget pace yest.</th><th>Impr. share 7d</th></tr>
      {''.join(row_camp(c) for c in enabled)}</table></div>"""

    charts = ('<div class="charts">' +
              _bar_chart("Daily spend — last 14 days", days, spend_series, "var(--s1)",
                         lambda v: f"${v:,.0f}", lambda d, v: f"<b>{d}</b><br>Spend {fmt_usd(v, 2)}") +
              _bar_chart("Daily leads — last 14 days", days, conv_series, "var(--s2)",
                         lambda v: f"{v:g}", lambda d, v: f"<b>{d}</b><br>{v:g} leads") + '</div>')

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(account_name)} — Google Ads daily · {run_date}</title>
<style>{CSS}</style></head>
<body class="viz-root"><div class="wrap">
  {brand_header("Daily Pulse — Google Ads", str(run_date), f"{account_name} · account {account_id} · yesterday + trailing 7 days (vs prior 7)")}
  {tiles}
  {urgent_html}
  {camp_html}
  <div style="margin-top:16px">{charts}</div>
  {notes_html}
  {brand_footer('Generated automatically · data via Google Ads API · conversions may lag up to 24h')}
</div><div id="tip"></div>{TIP_JS}</body></html>"""

def delta_html(new, old, up_good=None):
    return _delta(new, old, up_good=up_good)
