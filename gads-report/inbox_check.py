#!/usr/bin/env python3
"""
MKTG Bot inbox: print new human messages from the client Discord channel.

Usage:
  python3 inbox_check.py            # print new messages since last mark (does NOT advance state)
  python3 inbox_check.py --mark-done  # advance state to the newest message printed by the last run
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import discord_post as dp

BASE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(BASE, "state", "discord_inbox.json")

def load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {}

def save_state(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=1)

def main():
    st = load_state()
    if "--mark-done" in sys.argv:
        if st.get("pending_max_id"):
            st["last_id"] = st.pop("pending_max_id")
            save_state(st)
            print(f"marked done at {st['last_id']}")
        else:
            print("nothing pending")
        return

    last_id = st.get("last_id")
    if last_id is None:
        # fresh state (first run or env reset): look back 2 hours so recent
        # approvals aren't silently skipped, but don't replay all history
        from datetime import datetime, timedelta, timezone
        cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        recent = dp.fetch_after(None)
        msgs = [m for m in recent
                if datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00")) >= cutoff]
        if not msgs:
            newest = max((int(m["id"]) for m in recent), default=0)
            st["last_id"] = str(newest) if newest else "0"
            save_state(st)
            print("NO_NEW_MESSAGES (initialized inbox state)")
            return
        st["last_id"] = str(min(int(m["id"]) for m in msgs) - 1)
        last_id = st["last_id"]
        save_state(st)
        msgs = dp.fetch_after(last_id)
    else:
        msgs = dp.fetch_after(last_id)
    if not msgs:
        print("NO_NEW_MESSAGES")
        return

    st["pending_max_id"] = str(max(int(m["id"]) for m in msgs))
    save_state(st)
    print(f"{len(msgs)} new message(s):\n")
    for m in msgs:
        author = m["author"].get("global_name") or m["author"].get("username")
        ref = ""
        rm = m.get("referenced_message")
        if rm:
            ref_author = rm.get("author", {}).get("username", "?")
            ref = f'\n  [replying to {ref_author}: "{(rm.get("content") or "(attachment/embed)")[:120]}"]'
        print(f"--- id={m['id']} | {author} | {m['timestamp']}{ref}\n{m.get('content','')}\n")

if __name__ == "__main__":
    main()
