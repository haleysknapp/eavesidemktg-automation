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
"""
import os, sys, json, asyncio, subprocess, time
import discord

BASE = os.path.dirname(os.path.abspath(__file__))
GADS = os.path.join(BASE, "gads-report")
STATE_PATH = os.path.join(BASE, "state.json")
INSTRUCTIONS = open(os.path.join(BASE, "BOT_INSTRUCTIONS.md")).read()
CLAUDE_TIMEOUT = 900  # seconds per message

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
        ["claude", "-p", prompt, "--dangerously-skip-permissions"],
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

async def worker():
    while True:
        item = await queue.get()
        author, content, ref_a, ref_c, mid = item
        prompt = build_prompt(author, content, ref_a, ref_c, mid)
        print(f"[{time.strftime('%H:%M:%S')}] processing msg {mid} from {author}: {content[:80]!r}", flush=True)
        try:
            r = await asyncio.to_thread(run_claude, prompt)
            if r.returncode != 0:
                print("claude error:", (r.stderr or r.stdout)[:500], flush=True)
                say_fallback("⚠️ I hit an error handling that — try rephrasing, or Haley can check the listener logs.")
        except subprocess.TimeoutExpired:
            say_fallback("⚠️ That took too long and I gave up — try a simpler request.")
        except FileNotFoundError:
            say_fallback("⚠️ Claude Code CLI not found on this machine — Haley, run the installer again.")
        st = load_state()
        st["last_id"] = str(mid)
        save_state(st)
        queue.task_done()

async def enqueue_message(m):
    if m.author.bot or m.channel.id != CHANNEL_ID:
        return
    content = (m.content or "").strip()
    if not content:
        return
    ref_a = ref_c = None
    if m.reference and m.reference.resolved and isinstance(m.reference.resolved, discord.Message):
        ref_a = m.reference.resolved.author.display_name
        ref_c = m.reference.resolved.content or "(attachment/embed — likely a report)"
    await queue.put((m.author.display_name, content, ref_a, ref_c, m.id))

@client.event
async def on_ready():
    print(f"logged in as {client.user} — watching channel {CHANNEL_ID}", flush=True)
    asyncio.create_task(worker())
    # backfill anything missed while offline
    st = load_state()
    last = st.get("last_id")
    ch = client.get_channel(CHANNEL_ID) or await client.fetch_channel(CHANNEL_ID)
    if last:
        async for m in ch.history(after=discord.Object(id=int(last)), limit=50, oldest_first=True):
            await enqueue_message(m)
    else:
        # first ever run: don't replay history
        st["last_id"] = str(ch.last_message_id or 0)
        save_state(st)

@client.event
async def on_message(message):
    await enqueue_message(message)

if __name__ == "__main__":
    client.run(TOKEN)
