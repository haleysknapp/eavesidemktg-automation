#!/usr/bin/env python3
"""
MKTG Bot — live Discord listener.

Connects to the Discord gateway and, for every human message in the client
channel, invokes a headless Claude Code session (claude -p) working inside the
gads-report folder. Claude interprets the message (approvals, negative-keyword
requests, questions), acts with the same guardrail scripts used everywhere
else, and replies in the channel itself.

Messages sent while the Mac was asleep are processed on wake (backfill since
the last handled message id). One Claude session runs at a time.

COST CONTROLS (added 2026-08-07):
  * CLAUDE_MODEL — pins the headless session to a cheap model instead of
    inheriting the account default (was Opus). Override with MKTG_BOT_MODEL.
  * is_chatter() — acknowledgments ("thanks", "👍", "got it") are answered with
    a reaction only; they never spawn a Claude session. Replies and bot
    mentions ALWAYS bypass this filter, so "yes" under a report still counts.
  * last_id is saved at ENQUEUE time, not after processing. Previously a crash
    mid-message meant the restart re-queued the same message and spawned Claude
    again — with launchd KeepAlive that could loop. Now delivery is at-most-once.
  * Backfill is capped at MAX_BACKFILL messages and MAX_BACKFILL_AGE_HOURS, so a
    long offline stretch can't trigger a burst of sessions on wake.
"""
import os, sys, json, re, asyncio, subprocess, time
from datetime import datetime, timedelta, timezone

# macOS Python often ships without SSL root certificates wired up, which makes
# every connection to discord.com fail with CERTIFICATE_VERIFY_FAILED. Point the
# ssl module at certifi's CA bundle before discord/aiohttp create any contexts.
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass

import discord

BASE = os.path.dirname(os.path.abspath(__file__))
GADS = os.path.join(BASE, "gads-report")
STATE_PATH = os.path.join(BASE, "state.json")
INSTRUCTIONS = open(os.path.join(BASE, "BOT_INSTRUCTIONS.md")).read()
CLAUDE_TIMEOUT = 900  # seconds per message

# --- cost controls -----------------------------------------------------------
# This bot runs scripts and applies negatives; it does not need a frontier model.
CLAUDE_MODEL = os.environ.get("MKTG_BOT_MODEL", "sonnet")
# On wake, never replay more than this many messages, or anything older than this.
MAX_BACKFILL = 15
MAX_BACKFILL_AGE_HOURS = 12

# Pure acknowledgments — no reply needed, and definitely no Claude session.
# NOTE: deliberately excludes "yes"/"no"/"all"/"approve" — those can be real
# instructions. Replies bypass this filter entirely regardless of wording.
_ACK_WORDS = (
    r"thanks?|thank\s*you|thx|ty|got\s*it|sounds?\s*good|will\s*do|"
    r"perfect|great|nice|awesome|cool|sweet|sick|clean|"
    r"ok(?:ay)?|kk?|word|bet|ditto|same|agreed|"
    r"love\s*it|amazing|beautiful|lol|lmao|haha+|nvm|never\s*mind"
)
_PUNCT_EMOJI = r"[\s!.,~\-—…\U0001F000-\U0001FAFF -㌀️‍]*"
ACK_RE = re.compile(rf"^{_PUNCT_EMOJI}(?:(?:{_ACK_WORDS}){_PUNCT_EMOJI})+$", re.IGNORECASE)
# Emoji / punctuation only, e.g. "👍" or "🔥🔥" — no letters or digits at all.
SYMBOLS_ONLY_RE = re.compile(r"^[^0-9A-Za-z]+$")


def env():
    e = {}
    for line in open(os.path.join(GADS, ".env")):
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            e[k.strip()] = v.strip()
    return e

ENV = env()
TOKEN = ENV["discord_bot_token"]
CHANNEL_ID = int(ENV["discord_channel_id"])

def load_state():
    try:
        return json.load(open(STATE_PATH))
    except Exception:
        return {}

def save_state(s):
    json.dump(s, open(STATE_PATH, "w"))

def mark_seen(mid):
    """Record a message as handled. Called at ENQUEUE time so a crash during
    processing cannot cause the same message to be replayed on restart."""
    st = load_state()
    st["last_id"] = str(mid)
    save_state(st)

def is_chatter(content, is_reply, mentions_bot):
    """True when a message is a bare acknowledgment worth zero Claude tokens."""
    if is_reply or mentions_bot:
        return False              # a reply to a report may be "yes" / "all" / "1,3"
    c = (content or "").strip()
    if not c or len(c) > 40:
        return False
    return bool(ACK_RE.match(c) or SYMBOLS_ONLY_RE.match(c))

def say_fallback(text):
    """Plain post used only when Claude itself fails."""
    import urllib.request
    req = urllib.request.Request(
        f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages",
        data=json.dumps({"content": text}).encode(),
        headers={"Authorization": f"Bot {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": "EavesideMktgBot/1.0"}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=30)
    except Exception:
        pass

def run_claude(prompt):
    return subprocess.run(
        ["claude", "-p", prompt, "--model", CLAUDE_MODEL, "--dangerously-skip-permissions"],
        cwd=GADS, capture_output=True, text=True, timeout=CLAUDE_TIMEOUT)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
queue: asyncio.Queue = asyncio.Queue()

def build_prompt(author, content, ref_author=None, ref_content=None, msg_id=None):
    ref = ""
    if ref_content is not None:
        ref = f'\n\nThis message is a REPLY to a message from {ref_author}: """{ref_content[:1500]}"""'
    return (f"{INSTRUCTIONS}\n\n---\nNEW DISCORD MESSAGE (id {msg_id}) from {author}:\n"
            f'"""{content}"""{ref}\n\nHandle it now per the instructions above. '
            f"Remember: every reply to the channel goes through discord_post.dp.say(...) — "
            f"your stdout is not visible to anyone.")

async def react_to(mid, emoji):
    """Best-effort reaction on a message — 👀 = seen/working, ✅ = done, ⚠️ = failed,
    👍 = seen, nothing to do (chatter)."""
    try:
        ch = client.get_channel(CHANNEL_ID) or await client.fetch_channel(CHANNEL_ID)
        msg = await ch.fetch_message(int(mid))
        await msg.add_reaction(emoji)
    except Exception as e:
        print(f"reaction {emoji} on {mid} failed: {e}", flush=True)

async def worker():
    while True:
        item = await queue.get()
        author, content, ref_a, ref_c, mid = item
        prompt = build_prompt(author, content, ref_a, ref_c, mid)
        print(f"[{time.strftime('%H:%M:%S')}] processing msg {mid} from {author} "
              f"({CLAUDE_MODEL}): {content[:80]!r}", flush=True)
        try:
            r = await asyncio.to_thread(run_claude, prompt)
            if r.returncode != 0:
                print("claude error:", (r.stderr or r.stdout)[:500], flush=True)
                say_fallback("⚠️ I hit an error handling that — try rephrasing, or Haley can check the listener logs.")
                await react_to(mid, "⚠️")
            else:
                await react_to(mid, "✅")
        except subprocess.TimeoutExpired:
            say_fallback("⚠️ That took too long and I gave up — try a simpler request.")
            await react_to(mid, "⚠️")
        except FileNotFoundError:
            say_fallback("⚠️ Claude Code CLI not found on this machine — Haley, run the installer again.")
        queue.task_done()

async def enqueue_message(m):
    if m.author.bot or m.channel.id != CHANNEL_ID:
        return
    content = (m.content or "").strip()
    if not content:
        return

    is_reply = bool(m.reference and m.reference.resolved
                    and isinstance(m.reference.resolved, discord.Message))
    mentions_bot = client.user in getattr(m, "mentions", [])

    # Cheap path: pure chatter never reaches Claude.
    if is_chatter(content, is_reply, mentions_bot):
        print(f"[{time.strftime('%H:%M:%S')}] skipping chatter {m.id}: {content[:60]!r}", flush=True)
        mark_seen(m.id)
        await react_to(m.id, "👍")
        return

    ref_a = ref_c = None
    if is_reply:
        ref_a = m.reference.resolved.author.display_name
        ref_c = m.reference.resolved.content or "(attachment/embed — likely a report)"

    # Mark handled BEFORE the expensive work, so a crash can't cause a replay loop.
    mark_seen(m.id)
    try:
        await m.add_reaction("👀")   # instant "I see it" acknowledgment
    except Exception:
        pass
    await queue.put((m.author.display_name, content, ref_a, ref_c, m.id))

@client.event
async def on_ready():
    print(f"logged in as {client.user} — watching channel {CHANNEL_ID} "
          f"(model={CLAUDE_MODEL})", flush=True)
    asyncio.create_task(worker())
    # backfill anything missed while offline — bounded by count AND age
    st = load_state()
    last = st.get("last_id")
    ch = client.get_channel(CHANNEL_ID) or await client.fetch_channel(CHANNEL_ID)
    if last:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_BACKFILL_AGE_HOURS)
        stale = 0
        async for m in ch.history(after=discord.Object(id=int(last)),
                                  limit=MAX_BACKFILL, oldest_first=True):
            if m.created_at < cutoff:
                stale += 1
                mark_seen(m.id)          # too old to be actionable — retire it
                continue
            await enqueue_message(m)
        if stale:
            print(f"backfill: skipped {stale} message(s) older than "
                  f"{MAX_BACKFILL_AGE_HOURS}h", flush=True)
    else:
        # first ever run: don't replay history
        st["last_id"] = str(ch.last_message_id or 0)
        save_state(st)

@client.event
async def on_message(message):
    await enqueue_message(message)

if __name__ == "__main__":
    client.run(TOKEN)
