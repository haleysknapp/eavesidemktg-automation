#!/usr/bin/env python3
"""
Landing page audit — read-only. Changes nothing in Google Ads.

Answers: where is each campaign actually sending its clicks? Built because the
CTM call log showed a Kansas City campaign click landing on a Fort Smith page
and picking up the Fort Smith DNI number, which would break any attribution
keyed on the tracking number.

Four sections:
  1. Clicks by campaign x actual landing page (landing_page_view = ground truth)
  2. Final URLs configured on the ads themselves, by campaign and ad group
  3. Sitelink assets at campaign level, with their URLs
  4. Sitelink assets at ACCOUNT level - these apply to every campaign, so an
     account-level sitelink pointing at one market's page sends traffic there
     from all of them

Window: 2026-08-04 .. 2026-08-12 (same as window B in dni_check.py)

Usage:  python3 lp_check.py
"""
import os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from config import google_ads_client, CUSTOMER_ID, ACCOUNT_NAME

START, END = "2026-08-04", "2026-08-12"


def run(svc, query):
    out = []
    for batch in svc.search_stream(customer_id=CUSTOMER_ID, query=query):
        for r in batch.results:
            out.append(r)
    return out


def section(title):
    print("\n" + "=" * 92)
    print(title)
    print("=" * 92)


def safe(label, fn):
    try:
        fn()
    except Exception as e:
        print(f"\n  [{label}] query failed: {type(e).__name__}: {str(e)[:300]}\n")


def main():
    client = google_ads_client()
    svc = client.get_service("GoogleAdsService")
    print(f"\n{ACCOUNT_NAME} — landing page audit  {START} .. {END}  (read-only)")

    # ---------- 1. where clicks actually landed ----------
    def s1():
        section("1. ACTUAL LANDING PAGES — clicks by campaign x final URL")
        q = f"""
          SELECT campaign.name, campaign.status,
                 landing_page_view.unexpanded_final_url,
                 metrics.clicks, metrics.impressions
          FROM landing_page_view
          WHERE segments.date BETWEEN '{START}' AND '{END}'
            AND campaign.status != 'REMOVED'
        """
        agg = defaultdict(int)
        for r in run(svc, q):
            if r.metrics.clicks:
                agg[(r.campaign.name, r.landing_page_view.unexpanded_final_url)] += r.metrics.clicks
        if not agg:
            print("\n  no landing page rows with clicks in this window")
            return
        bycamp = defaultdict(list)
        for (camp, url), clicks in agg.items():
            bycamp[camp].append((clicks, url))
        for camp in sorted(bycamp, key=lambda c: -sum(x[0] for x in bycamp[c])):
            tot = sum(x[0] for x in bycamp[camp])
            print(f"\n  {camp}   —   {tot} clicks")
            for clicks, url in sorted(bycamp[camp], reverse=True):
                pct = 100.0 * clicks / tot if tot else 0
                flag = ""
                print(f"      {clicks:>5}  ({pct:>5.1f}%)  {url}{flag}")

    # ---------- 2. final urls on the ads ----------
    def s2():
        section("2. CONFIGURED AD FINAL URLS — by campaign / ad group")
        q = f"""
          SELECT campaign.name, ad_group.name, ad_group_ad.ad.final_urls,
                 metrics.clicks
          FROM ad_group_ad
          WHERE segments.date BETWEEN '{START}' AND '{END}'
            AND campaign.status != 'REMOVED'
            AND ad_group_ad.status != 'REMOVED'
        """
        agg = defaultdict(int)
        for r in run(svc, q):
            for u in r.ad_group_ad.ad.final_urls:
                agg[(r.campaign.name, r.ad_group.name, u)] += r.metrics.clicks
        if not agg:
            print("\n  no ad rows returned")
            return
        bycamp = defaultdict(list)
        for (camp, ag, url), clicks in agg.items():
            bycamp[camp].append((ag, url, clicks))
        for camp in sorted(bycamp):
            print(f"\n  {camp}")
            for ag, url, clicks in sorted(bycamp[camp], key=lambda x: (x[0], -x[2])):
                print(f"      [{clicks:>4} clicks]  {ag[:34]:<34}  {url}")

    # ---------- 3. campaign-level sitelinks ----------
    def s3():
        section("3. SITELINKS AT CAMPAIGN LEVEL")
        q = """
          SELECT campaign.name, campaign.status,
                 asset.sitelink_asset.link_text, asset.final_urls,
                 campaign_asset.status
          FROM campaign_asset
          WHERE campaign_asset.field_type = 'SITELINK'
            AND campaign_asset.status != 'REMOVED'
            AND campaign.status != 'REMOVED'
        """
        rows = run(svc, q)
        if not rows:
            print("\n  none — sitelinks are not set at campaign level")
            return
        bycamp = defaultdict(list)
        for r in rows:
            for u in r.asset.final_urls:
                bycamp[r.campaign.name].append((r.asset.sitelink_asset.link_text, u))
        for camp in sorted(bycamp):
            print(f"\n  {camp}")
            for text, u in sorted(set(bycamp[camp])):
                print(f"      {text[:30]:<30}  {u}")

    # ---------- 4. account-level sitelinks (apply to ALL campaigns) ----------
    def s4():
        section("4. SITELINKS AT ACCOUNT LEVEL — these apply to EVERY campaign")
        q = """
          SELECT asset.sitelink_asset.link_text, asset.final_urls,
                 customer_asset.status
          FROM customer_asset
          WHERE customer_asset.field_type = 'SITELINK'
            AND customer_asset.status != 'REMOVED'
        """
        rows = run(svc, q)
        if not rows:
            print("\n  none at account level")
            return
        seen = set()
        for r in rows:
            for u in r.asset.final_urls:
                seen.add((r.asset.sitelink_asset.link_text, u))
        print()
        for text, u in sorted(seen):
            print(f"      {text[:30]:<30}  {u}")
        print(f"\n  {len(seen)} account-level sitelink destinations, live on all campaigns.")

    safe("landing_page_view", s1)
    safe("ad_group_ad", s2)
    safe("campaign_asset", s3)
    safe("customer_asset", s4)
    print()


if __name__ == "__main__":
    main()
