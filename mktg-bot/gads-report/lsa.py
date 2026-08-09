"""Local Services Ads data: spend + leads per LSA account under the MCC."""
from datetime import datetime
from collections import defaultdict

LSA_ACCOUNTS = {
    "2344723790": "Fort Smith",
    "7020216103": "Joplin",
    "2664128737": "Olathe",
    "1830697125": "Wichita",
}

def money(m): return m / 1_000_000

def fetch_lsa(client, d_start, d_end):
    """Returns {account_name: {"daily": {date: cost}, "leads": [(date, charged, status, type)]}}"""
    svc = client.get_service("GoogleAdsService")
    out = {}
    for cid, name in LSA_ACCOUNTS.items():
        acct = {"daily": defaultdict(float), "leads": []}
        q = f"""SELECT segments.date, metrics.cost_micros FROM campaign
                WHERE segments.date BETWEEN '{d_start}' AND '{d_end}'"""
        try:
            for r in svc.search(customer_id=cid, query=q):
                acct["daily"][str(r.segments.date)] += money(r.metrics.cost_micros)
        except Exception as e:
            print(f"[lsa] spend query failed for {name}: {str(e)[:200]}")
        q2 = """SELECT local_services_lead.id, local_services_lead.lead_type,
                local_services_lead.lead_status, local_services_lead.creation_date_time,
                local_services_lead.lead_charged
                FROM local_services_lead"""
        try:
            for r in svc.search(customer_id=cid, query=q2):
                l = r.local_services_lead
                d = str(l.creation_date_time)[:10]
                if str(d_start) <= d <= str(d_end):
                    acct["leads"].append((d, bool(l.lead_charged),
                                          l.lead_status.name, l.lead_type.name))
        except Exception as e:
            print(f"[lsa] lead query failed for {name}: {str(e)[:200]}")
        out[name] = acct
    return out

def window(acct, d_start, d_end):
    """Totals for a date window: spend, charged leads, all leads."""
    spend = sum(v for d, v in acct["daily"].items() if str(d_start) <= d <= str(d_end))
    charged = sum(1 for (d, ch, _s, _t) in acct["leads"] if ch and str(d_start) <= d <= str(d_end))
    total = sum(1 for (d, _ch, _s, _t) in acct["leads"] if str(d_start) <= d <= str(d_end))
    return spend, charged, total
