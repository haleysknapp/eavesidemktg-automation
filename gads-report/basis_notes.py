"""
Counting-basis changes — the register of dates where "a lead" started meaning
something different in Google Ads.

WHY THIS EXISTS
---------------
On 2026-07-31 the "Calls from ads" conversion action was demoted Primary ->
Secondary. That was CORRECT: since 2026-07-23 the CTM tracking numbers sit on
both the ad call assets and the website DNI swap, so the same physical call was
being booked twice (Google as an ad-call, CTM as an attributed web call).
Confirmed against CALL-1609: Google call_view 5 Aug 00:59:37 / 51s / area 573 /
Kansas City New Search == CTM 5 Aug 01:59:36 / 52s / (573) 366-7081 / Kansas
City New Search. One hour apart = Denver vs Central. Same call.

But it means any comparison spanning 2026-07-31 compares leads counted two
different ways, and the reports were showing that as a real -58% collapse.
Two separate sessions have now re-litigated this from scratch. Hence the
register: every report that draws a trend line or a vs-last-period delta calls
in here and prints the caveat automatically.

TO ADD A FUTURE CHANGE: append a dict to CHANGES. Nothing else to touch.
"""
from datetime import date, datetime

CHANGES = [
    {
        "date": date(2026, 7, 31),
        "short": "call counting changed 31 Jul",
        "note": (
            "Google Ads stopped counting call-asset calls separately on 31 July, so the "
            "same call is no longer counted twice. Weeks before and after that date count "
            "leads differently — the drop across it is a counting change, not a real one."
        ),
        "internal": (
            "'Calls from ads' (AD_CALL) demoted Primary -> Secondary 2026-07-31. Correct: "
            "CTM numbers went into the call assets 2026-07-23, so ad-calls were also being "
            "uploaded by CTM as 'Call Tracking Lead'. Verified via CALL-1609. Primary now: "
            "Call Tracking Lead (UPLOAD_CLICKS) only. Like-for-like L7 3-9 Aug = 14 @ $255 "
            "vs prior 22 @ $176, NOT 14 vs 33."
        ),
    },
]


def _as_date(d):
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    return datetime.strptime(str(d)[:10], "%Y-%m-%d").date()


def spanning(start, end):
    """Basis changes that fall inside [start, end] — i.e. this range is mixed."""
    s, e = _as_date(start), _as_date(end)
    return [c for c in CHANGES if s < c["date"] <= e]


def between(period_a_start, period_b_end):
    """Basis changes that fall between two periods being compared."""
    return spanning(period_a_start, period_b_end)


def flagged_weeks(week_end_dates):
    """Given trend x-axis labels (week-ending dates), return {label: short} for
    any week whose 7-day window contains a basis change."""
    out = {}
    for label in week_end_dates:
        e = _as_date(label)
        s = date.fromordinal(e.toordinal() - 6)
        hits = [c for c in CHANGES if s <= c["date"] <= e]
        if hits:
            out[str(label)] = hits[0]["short"]
    return out


def flagged_months(month_labels):
    """Same idea for monthly trends. Accepts 'YYYY-MM' or date-like labels."""
    out = {}
    for label in month_labels:
        txt = str(label)
        for c in CHANGES:
            if txt.startswith(c["date"].strftime("%Y-%m")):
                out[txt] = c["short"]
    return out


def client_note(start, end, prefix="Note: "):
    """Client-facing sentence for a report covering [start, end]. '' if clean."""
    hits = spanning(start, end)
    if not hits:
        return ""
    return prefix + " ".join(c["note"] for c in hits)


def internal_note(start, end):
    """Full technical detail, for Discord / console / Haley — never the client."""
    hits = spanning(start, end)
    return " | ".join(f"{c['date']}: {c['internal']}" for c in hits)


def trend_footnote(week_end_dates):
    """One line to sit under a trend chart, naming the affected buckets."""
    flags = flagged_weeks(week_end_dates)
    if not flags:
        return ""
    buckets = ", ".join(sorted(flags))
    only = CHANGES[0]["note"] if len(set(flags.values())) == 1 else \
        " ".join(c["note"] for c in CHANGES)
    return f"Bucket(s) {buckets} span a change in how leads are counted. {only}"
