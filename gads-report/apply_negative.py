#!/usr/bin/env python3
"""
Apply a negative keyword to Roofing Force campaigns (campaign-level), with SOP guardrails.

Usage:
  python3 apply_negative.py --term "erie home olathe" --campaigns kc --match phrase
  python3 apply_negative.py --term "qxo" --campaigns all
  python3 apply_negative.py --list-campaigns
Options:
  --campaigns   comma list of campaign name fragments (kc, wichita, "st louis", joplin, "fort smith") or "all"
  --match       phrase (default) | exact | broad
  --force       override guardrail blocks (converting term, core intent, brand, erie-outside-KC rule)
  --dry-run     validate + show what would happen, apply nothing
  --requested-by  name recorded in the log (default: Haley via Discord)
  --no-discord  skip the Discord confirmation post

Guardrails (block unless --force):
  * never negate own brand ("roofing force")
  * never negate a term with conversions in the last 60 days
  * warn-block on core lead intent (roof repair/replacement/companies + no junk signal)
  * "erie" negatives are KC-only per SOP (Erie Home is a KC-market competitor)
Always: skips if an identical negative already exists; appends to out/negatives-log.md.
"""
import os, re, sys, json, argparse
from datetime import date
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import google_ads_client, CUSTOMER_ID, BASE_DIR
import discord_post as dp

LOG = os.path.join(BASE_DIR, "out", "negatives-log.md")

def get_campaigns(client):
    svc = client.get_service("GoogleAdsService")
    q = """SELECT campaign.id, campaign.name FROM campaign
           WHERE campaign.status = 'ENABLED'
             AND campaign.advertising_channel_type = 'SEARCH'"""
    return [(r.campaign.id, r.campaign.name) for r in svc.search(customer_id=CUSTOMER_ID, query=q)]

def resolve(frag_list, camps):
    if any(f.strip().lower() == "all" for f in frag_list):
        return camps
    out, misses = [], []
    for frag in frag_list:
        f = frag.strip().lower()
        hits = [c for c in camps if f in c[1].lower()]
        if not hits and f in ("kc", "kansas city"):
            hits = [c for c in camps if "kc" in c[1].lower() or "kansas" in c[1].lower()]
        if not hits and f in ("stl", "st louis", "st. louis", "saint louis"):
            hits = [c for c in camps if "louis" in c[1].lower() or "stl" in c[1].lower()]
        if not hits:
            misses.append(frag)
        out.extend(hits)
    if misses:
        names = ", ".join(c[1] for c in camps)
        sys.exit(f"BLOCKED: no campaign matches {misses}. Enabled search campaigns: {names}")
    return sorted(set(out))

def conversions_60d(client, term):
    svc = client.get_service("GoogleAdsService")
    from datetime import timedelta
    start = (date.today() - timedelta(days=60)).isoformat()
    t = term.replace("'", "\\'")
    q = f"""SELECT search_term_view.search_term, metrics.conversions
            FROM search_term_view
            WHERE search_term_view.search_term = '{t}'
              AND segments.date BETWEEN '{start}' AND '{date.today().isoformat()}'"""
    return sum(r.metrics.conversions for r in svc.search(customer_id=CUSTOMER_ID, query=q))

def guardrails(term, targets, conv, force):
    t = term.lower()
    blocks = []
    if re.search(r"\broofing\s*force\b", t):
        blocks.append("this is the client's OWN BRAND — negating it would block branded leads")
    if conv > 0:
        blocks.append(f"this term drove {conv:.1f} conversion(s) in the last 60 days")
    if re.search(r"\berie\b", t):
        non_kc = [c[1] for c in targets if not re.search(r"kc|kansas", c[1], re.I)]
        if non_kc:
            blocks.append(f"SOP: 'erie' negatives are KC-only, but targets include {non_kc}")
    core = re.search(r"\b(roof(ing)?|roofer)\b", t) and re.search(
        r"\b(repair|replace(ment)?|compan(y|ies)|contractor|estimate|quote|inspection|near me)\b", t)
    junk = re.search(r"\b(jobs?|hiring|salary|diy|training|supply|supplies|wholesale|calculator|erie|qxo)\b", t)
    if core and not junk:
        blocks.append("looks like CORE LEAD INTENT (roofing + service/buy language)")
    if blocks and not force:
        print("BLOCKED (use --force to override):")
        for b in blocks:
            print(f"  * {b}")
        sys.exit(2)
    return blocks

def existing_negatives(client, cid):
    svc = client.get_service("GoogleAdsService")
    q = f"""SELECT campaign_criterion.keyword.text, campaign_criterion.keyword.match_type
            FROM campaign_criterion
            WHERE campaign.id = {cid} AND campaign_criterion.negative = TRUE
              AND campaign_criterion.type = 'KEYWORD'"""
    return {(r.campaign_criterion.keyword.text.lower(), r.campaign_criterion.keyword.match_type.name)
            for r in svc.search(customer_id=CUSTOMER_ID, query=q)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--term")
    ap.add_argument("--campaigns", default="all")
    ap.add_argument("--match", default="phrase", choices=["phrase", "exact", "broad"])
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--requested-by", default="Haley via Discord")
    ap.add_argument("--no-discord", action="store_true")
    ap.add_argument("--list-campaigns", action="store_true")
    a = ap.parse_args()

    client = google_ads_client()
    camps = get_campaigns(client)
    if a.list_campaigns:
        for cid, name in camps:
            print(f"{cid}  {name}")
        return
    if not a.term:
        sys.exit("--term is required")

    term = a.term.strip().strip('"').strip("'").lower()
    targets = resolve(a.campaigns.split(","), camps)
    conv = conversions_60d(client, term)
    overridden = guardrails(term, targets, conv, a.force)
    mt = a.match.upper()

    applied, skipped = [], []
    for cid, name in targets:
        if (term, mt) in existing_negatives(client, cid):
            skipped.append(name)
            continue
        if a.dry_run:
            applied.append(name)
            continue
        op_svc = client.get_service("CampaignCriterionService")
        op = client.get_type("CampaignCriterionOperation")
        crit = op.create
        crit.campaign = client.get_service("CampaignService").campaign_path(CUSTOMER_ID, cid)
        crit.negative = True
        crit.keyword.text = term
        crit.keyword.match_type = client.enums.KeywordMatchTypeEnum[mt]
        op_svc.mutate_campaign_criteria(customer_id=CUSTOMER_ID, operations=[op])
        applied.append(name)

    tag = "DRY RUN — would add" if a.dry_run else "Added"
    row = f"| {date.today().isoformat()} | \"{term}\" | {a.match} | {', '.join(applied) or '—'} | {a.requested_by} |"
    print(f"{tag} negative \"{term}\" ({a.match}) to: {applied or 'none'}; already present in: {skipped or 'none'}")
    print("log row:", row)

    if not a.dry_run and applied:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        if not os.path.exists(LOG):
            open(LOG, "w").write("# RF Negatives Log (applied via MKTG Bot)\n\n| date | term | match | campaigns | requested by |\n|---|---|---|---|---|\n")
        open(LOG, "a").write(row + "\n")
        if not a.no_discord:
            note = f" (guardrails overridden: {'; '.join(overridden)})" if overridden else ""
            skips = f" Already present in: {', '.join(skipped)}." if skipped else ""
            dp.say(f":no_entry_sign: Added negative **\"{term}\"** ({a.match} match) to: {', '.join(applied)}.{skips}{note}\n`{row}`")

if __name__ == "__main__":
    main()
