"""Discord posting for MKTG Bot.

Prefers the bot token (posts as MKTG Bot into the client channel); falls back
to the legacy webhook if bot creds are missing. Also exposes message reading
for the reply-to-approve inbox loop.
"""
import json, os, requests

_DIR = os.path.dirname(os.path.abspath(__file__))
API = "https://discord.com/api/v10"

def _env():
    env = {}
    try:
        for line in open(os.path.join(_DIR, ".env")):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return env

def _bot_creds():
    env = _env()
    return env.get("discord_bot_token", ""), env.get("discord_channel_id", "")

def _headers(tok):
    return {"Authorization": f"Bot {tok}", "User-Agent": "EavesideMktgBot/1.0"}

def render_png(html_path, width=1000, dark=True):
    """Screenshot an HTML report to PNG so Discord shows it inline. Returns path or None."""
    try:
        from playwright.sync_api import sync_playwright
        png_path = os.path.splitext(html_path)[0] + ".png"
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            pg = b.new_page(viewport={"width": width, "height": 900},
                            color_scheme="dark" if dark else "light")
            pg.goto("file://" + os.path.abspath(html_path))
            pg.wait_for_timeout(400)
            pg.screenshot(path=png_path, full_page=True)
            b.close()
        # Discord inline-image cap safety: skip if absurdly large
        if os.path.getsize(png_path) > 9_500_000:
            return None
        return png_path
    except Exception as e:
        print(f"[png] render failed: {e}")
        return None

_MIME = {".html": "text/html", ".png": "image/png", ".txt": "text/plain"}

def post(webhook=None, embed=None, content=None, file_path=None, channel_id=None, image_path=None):
    """Post as the bot if configured, else via webhook. Returns True on success.

    image_path: optional PNG shown inline inside the embed (Discord renders it
    natively — use a compact, purpose-built image, never a full-page report).
    """
    tok, chan = _bot_creds()
    chan = channel_id or chan
    payload = {}
    if content: payload["content"] = content
    if embed: payload["embeds"] = [embed]

    files = [file_path] if isinstance(file_path, str) else list(file_path or [])
    if image_path:
        files.insert(0, image_path)
        if embed is not None and "image" not in embed:
            embed["image"] = {"url": f"attachment://{os.path.basename(image_path)}"}
            payload["embeds"] = [embed]

    if tok and chan:
        url = f"{API}/channels/{chan}/messages"
        if files:
            handles = []
            try:
                multipart = {}
                for i, p in enumerate(files):
                    fh = open(p, "rb"); handles.append(fh)
                    ext = os.path.splitext(p)[1].lower()
                    multipart[f"files[{i}]"] = (os.path.basename(p), fh, _MIME.get(ext, "application/octet-stream"))
                r = requests.post(url, headers=_headers(tok),
                                  data={"payload_json": json.dumps(payload)},
                                  files=multipart, timeout=120)
            finally:
                for fh in handles: fh.close()
        else:
            r = requests.post(url, headers={**_headers(tok), "Content-Type": "application/json"},
                              json=payload, timeout=30)
        ok = r.status_code in (200, 204)
        if not ok:
            print(f"[discord-bot] HTTP {r.status_code}: {r.text[:300]}")
        return ok

    # webhook fallback
    if not webhook or "discord.com/api/webhooks" not in webhook:
        print("[discord] no bot creds and no webhook; skipping")
        return False
    fp = files[-1] if files else None
    if fp:
        with open(fp, "rb") as f:
            r = requests.post(webhook, data={"payload_json": json.dumps(payload)},
                              files={"file": (os.path.basename(fp), f, "text/html")},
                              timeout=60)
    else:
        r = requests.post(webhook, json=payload, timeout=30)
    ok = r.status_code in (200, 204)
    if not ok:
        print(f"[discord] HTTP {r.status_code}: {r.text[:300]}")
    return ok

def say(content, channel_id=None, reply_to=None):
    """Plain text post as the bot (used by the inbox loop for confirmations)."""
    tok, chan = _bot_creds()
    chan = channel_id or chan
    payload = {"content": content}
    if reply_to:
        payload["message_reference"] = {"message_id": reply_to, "fail_if_not_exists": False}
    r = requests.post(f"{API}/channels/{chan}/messages",
                      headers={**_headers(tok), "Content-Type": "application/json"},
                      json=payload, timeout=30)
    if r.status_code != 200:
        print(f"[discord-bot] HTTP {r.status_code}: {r.text[:300]}")
    return r.status_code == 200

def fetch_after(after_id=None, channel_id=None, limit=50):
    """Fetch messages after a given ID (ascending). Excludes bot's own messages."""
    tok, chan = _bot_creds()
    chan = channel_id or chan
    params = f"?limit={limit}" + (f"&after={after_id}" if after_id else "")
    r = requests.get(f"{API}/channels/{chan}/messages{params}", headers=_headers(tok), timeout=30)
    r.raise_for_status()
    msgs = sorted(r.json(), key=lambda m: int(m["id"]))
    return [m for m in msgs if not m.get("author", {}).get("bot")]

# embed colors (decimal RGB)
GREEN, YELLOW, ORANGE, RED, BLUE = 0x0ca30c, 0xfab219, 0xec835a, 0xd03b3b, 0x2a78d6
