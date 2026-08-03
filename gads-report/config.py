"""Load credentials from .env file next to this script."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_env(path=None):
    path = path or os.path.join(BASE_DIR, ".env")
    cfg = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg

ENV = load_env()

CUSTOMER_ID = "3298488566"          # Roofing Force (329-848-8566)
LOGIN_CUSTOMER_ID = ENV.get("login_customer_id", "9680763943").replace("-", "")
ACCOUNT_NAME = "Roofing Force"
DISCORD_WEBHOOK = ENV.get("discord_webhook", "")

def google_ads_client():
    from google.ads.googleads.client import GoogleAdsClient
    return GoogleAdsClient.load_from_dict({
        "developer_token": ENV["developer_token"],
        "client_id": ENV["client_id"],
        "client_secret": ENV["client_secret"],
        "refresh_token": ENV["refresh_token"],
        "login_customer_id": LOGIN_CUSTOMER_ID,
        "use_proto_plus": True,
    })
