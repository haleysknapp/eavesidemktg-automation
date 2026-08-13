#!/usr/bin/env python3
"""
token_cost.py — measure what a Claude session actually cost.

Parses a Claude session transcript (.jsonl) and reports the real dollar cost,
broken down by token type and by activity. Appends a row to a CSV log so you
build a cost history across report runs.

Usage:
    python3 token_cost.py                          # newest local session
    python3 token_cost.py --list                   # list local sessions
    python3 token_cost.py --transcript PATH        # a specific one
    python3 token_cost.py --label "RF Aug monthly" # tag the run in the log
    python3 token_cost.py --model son5             # price at Sonnet rates instead
    python3 token_cost.py --no-log                 # print only, don't append

Cloud Cowork sessions keep their transcript inside the cloud container, not on
this Mac — for those, run this from inside the session itself (just ask Claude
to "log the cost of this run") and it will commit the row back here.
"""

import argparse, csv, glob, json, os, sys
from collections import Counter
from datetime import datetime, timezone

# ---- prices, USD per million tokens (platform.claude.com, Aug 2026) ---------
# cr = cache read, cw = 1-hour cache write, out = output, inp = plain input
PRICES = {
    "opus5":  {"label": "Opus 5",              "inp": 5,  "cr": 0.50, "cw": 10, "out": 25},
    "son5":   {"label": "Sonnet 5 (intro)",    "inp": 2,  "cr": 0.20, "cw":  4, "out": 10},
    "son5s":  {"label": "Sonnet 5 (Sept+)",    "inp": 3,  "cr": 0.30, "cw":  6, "out": 15},
    "haiku":  {"label": "Haiku 4.5",           "inp": 1,  "cr": 0.10, "cw":  2, "out":  5},
    "fable5": {"label": "Fable 5",             "inp": 10, "cr": 1.00, "cw": 20, "out": 50},
}

# effective-token weights, for the "where did attention go" view
W = {"inp": 1.0, "cr": 0.1, "cw": 2.0, "out": 5.0}

DEFAULT_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "token-cost-log.csv")


def config_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")


def find_transcripts():
    pat = os.path.join(config_dir(), "projects", "*", "*.jsonl")
    files = glob.glob(pat)
    return sorted(files, key=os.path.getmtime, reverse=True)


def group_for(tool):
    if not tool:
        return None
    if tool.startswith("mcp__claude-in-chrome__"):
        return "Claude in Chrome"
    if tool.startswith("mcp__remote-devices__"):
        return "Mac file bridge"
    if tool.startswith("mcp__"):
        # mcp__Gmail__x -> Gmail
        parts = tool.split("__")
        return parts[1] if len(parts) > 1 else "Connectors"
    if tool in ("WebSearch", "WebFetch"):
        return "Web research"
    if tool in ("Read", "Write", "Edit", "Glob", "Grep", "Bash", "NotebookEdit"):
        return "Files & shell"
    if tool == "Skill":
        return "Loading skills"
    if tool == "ToolSearch":
        return "Loading tools"
    if tool in ("TaskCreate", "TaskUpdate", "TaskList", "AskUserQuestion"):
        return "Task list & questions"
    if tool in ("Agent", "Workflow"):
        return "Subagents"
    return "Other tools"


def load_turns(path):
    """Return ordered assistant turns: [{'usage':..., 'tools':[...]}]"""
    turns = []
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "assistant":
                continue
            msg = rec.get("message") or {}
            usage = msg.get("usage")
            if not usage:
                continue
            tools = [
                c.get("name")
                for c in (msg.get("content") or [])
                if isinstance(c, dict) and c.get("type") == "tool_use"
            ]
            turns.append({"usage": usage, "tools": tools})
    return turns


def analyse(turns, price):
    raw = Counter()
    by_group_eff = Counter()
    by_group_usd = Counter()
    total_usd = 0.0
    total_eff = 0.0
    ctx_samples = []

    for n, t in enumerate(turns):
        u = t["usage"]
        inp = u.get("input_tokens", 0) or 0
        cr = u.get("cache_read_input_tokens", 0) or 0
        cw = u.get("cache_creation_input_tokens", 0) or 0
        out = u.get("output_tokens", 0) or 0

        raw["inp"] += inp; raw["cr"] += cr; raw["cw"] += cw; raw["out"] += out
        ctx_samples.append(inp + cr + cw)

        usd = (inp * price["inp"] + cr * price["cr"]
               + cw * price["cw"] + out * price["out"]) / 1e6
        eff = inp * W["inp"] + cr * W["cr"] + cw * W["cw"] + out * W["out"]
        total_usd += usd
        total_eff += eff

        # First turn is the system prompt + tool list being cached.
        if n == 0:
            g = "Claude's instructions"
        else:
            g = None
            for tool in turns[n - 1]["tools"]:
                g = group_for(tool)
                if g:
                    break
            if g is None:
                g = "Conversation carried forward"
        by_group_eff[g] += eff
        by_group_usd[g] += usd

    return {
        "raw": raw, "eff": by_group_eff, "usd": by_group_usd,
        "total_usd": total_usd, "total_eff": total_eff,
        "turns": len(turns),
        "avg_ctx": sum(ctx_samples) / len(ctx_samples) if ctx_samples else 0,
        "peak_ctx": max(ctx_samples) if ctx_samples else 0,
    }


def bar(frac, width=26):
    filled = int(round(frac * width))
    return "█" * filled + "·" * (width - filled)


def report(a, price, label, path):
    raw, total = a["raw"], a["total_usd"]
    print()
    print(f"  {label}")
    print(f"  {os.path.basename(path)} · {a['turns']} turns · priced at {price['label']}")
    print("  " + "─" * 60)

    print("\n  WHAT YOU PAID FOR")
    type_usd = {
        "Cache writes (new content in)": raw["cw"] * price["cw"] / 1e6,
        "Cache reads (re-reading it)":   raw["cr"] * price["cr"] / 1e6,
        "Output (Claude writing)":       raw["out"] * price["out"] / 1e6,
        "Plain input":                   raw["inp"] * price["inp"] / 1e6,
    }
    for k, v in sorted(type_usd.items(), key=lambda x: -x[1]):
        share = v / total if total else 0
        print(f"    {k:<32} {bar(share)} ${v:>7.2f}  {share*100:>5.1f}%")

    print("\n  WHERE IT WENT")
    mx = max(a["eff"].values()) if a["eff"] else 1
    for g, v in a["eff"].most_common():
        print(f"    {g:<32} {bar(v/mx)} ${a['usd'][g]:>7.2f}")

    print("\n  " + "─" * 60)
    print(f"    {'TOTAL':<32} {' ' * 26} ${total:>7.2f}")
    print(f"    {'per turn':<32} {' ' * 26} ${total/a['turns'] if a['turns'] else 0:>7.2f}")
    print(f"\n  Context: {a['avg_ctx']/1000:.0f}k average, {a['peak_ctx']/1000:.0f}k peak")
    print(f"  Raw tokens: {raw['cr']/1e6:.2f}M read · {raw['cw']/1e3:.0f}k written · "
          f"{raw['out']/1e3:.0f}k output")

    # What it'd cost on the cheaper tiers
    print("\n  SAME RUN ON OTHER MODELS")
    for key, p in PRICES.items():
        if key == "opus5" and price is PRICES["opus5"]:
            pass
        alt = (raw["inp"] * p["inp"] + raw["cr"] * p["cr"]
               + raw["cw"] * p["cw"] + raw["out"] * p["out"]) / 1e6
        mark = "  <- this run" if p is price else ""
        print(f"    {p['label']:<22} ${alt:>7.2f}{mark}")
    print()


def append_log(logpath, label, path, a, price, model_key):
    new = not os.path.exists(logpath)
    with open(logpath, "a", newline="") as fh:
        w = csv.writer(fh)
        if new:
            w.writerow(["date", "label", "model", "turns", "usd",
                        "usd_per_turn", "cache_write_tok", "cache_read_tok",
                        "output_tok", "avg_ctx_tok", "peak_ctx_tok", "transcript"])
        w.writerow([
            datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            label, model_key, a["turns"], f"{a['total_usd']:.4f}",
            f"{a['total_usd']/a['turns']:.4f}" if a["turns"] else "0",
            a["raw"]["cw"], a["raw"]["cr"], a["raw"]["out"],
            int(a["avg_ctx"]), int(a["peak_ctx"]), os.path.basename(path),
        ])
    print(f"  Logged to {logpath}\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--transcript")
    ap.add_argument("--label", default="")
    ap.add_argument("--model", default="opus5", choices=sorted(PRICES))
    ap.add_argument("--log", default=DEFAULT_LOG)
    ap.add_argument("--no-log", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        files = find_transcripts()
        if not files:
            print(f"No transcripts under {config_dir()}/projects/")
            return 1
        print(f"\n  Sessions under {config_dir()}/projects/\n")
        for f in files[:25]:
            mt = datetime.fromtimestamp(os.path.getmtime(f))
            print(f"    {mt:%Y-%m-%d %H:%M}  {os.path.getsize(f)/1024:>7.0f}KB  {f}")
        print()
        return 0

    path = args.transcript
    if not path:
        files = find_transcripts()
        if not files:
            print(f"No transcripts found under {config_dir()}/projects/.")
            print("If this was a cloud Cowork session, run this from inside "
                  "that session instead.")
            return 1
        path = files[0]

    if not os.path.exists(path):
        print(f"Not found: {path}")
        return 1

    turns = load_turns(path)
    if not turns:
        print(f"No usage data in {path} — is it a Claude transcript?")
        return 1

    price = PRICES[args.model]
    a = analyse(turns, price)
    label = args.label or "(unlabeled run)"
    report(a, price, label, path)

    if not args.no_log:
        append_log(args.log, label, path, a, price, args.model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
