# Call Tracking — Apps Script (the call grader)

## Source of truth

**`00 Agency OS/call-intelligence/Eaveside-Call-Grader.gs` is AUTHORITATIVE.**
Haley's call, 2026-08-14.

The file in this folder is a MIRROR for version control. Before editing or
committing it, pull from the authoritative path:

```
cp "<Roofing Agency>/00 Agency OS/call-intelligence/Eaveside-Call-Grader.gs" \
   apps-script/Call-Tracking/Eaveside-Call-Grader.gs
```

Do NOT edit this copy directly and do NOT paste an older version over it. On
2026-08-14 a session wrote a 544-line copy here that was already stale against
the 562-line authoritative file, and committing it would have silently reverted
two real fixes:

1. **The AH column move.** `dupe_of` has its own column (AH) and `EXT_HEADERS`
   has five entries. It used to share AF with `geo_source`, which was a live
   trap: both `rfGrade_backfillGeo()` and the re-grade SELECT on AF and treat a
   non-empty AF as "already handled", so `rfGrade_flagDupes()` stamping
   `superseded-by-row-N` there made every duplicate row permanently invisible to
   both, with nothing logged. Separate columns are the fix; a run-order rule is
   not. If you see a version whose `EXT_HEADERS` has four entries, it is old.
2. **The Claude call fixes.** `_claudeOnce()` with one retry, `CLAUDE_MAX_TOKENS`
   1500 (was 600), and `stop_reason == 'max_tokens'` detection. The 2026-08-13
   prompt added `caller_town`, `objection` and `service_type`; at 600 tokens the
   JSON truncated mid-string and surfaced only as a silent "grade fail", so calls
   went ungraded with no error. If you see `max_tokens:600` inline in `_claude()`,
   it is old.

Quick staleness check — the authoritative file is 562 lines / 41,002 bytes,
md5 `0a5c3505f6c6591c51d4426512cb1ac8`.

## Where this runs

Apps Script project `1J57bcvG0OPFnAs5juG-nLx8N4whwI4-cN-87prggzn4FSO_D54yB59xX`
on **haley@eaveside.com** (`/u/0/`). The similarly-named project on the gmail
account was verified empty on 2026-08-11 and renamed `ZZ EMPTY DECOY` — it is
not a second version and there is nothing to diff against it.

Apps Script source is not reachable from disk, so this mirror only updates when
someone pastes the live source out. It can drift from what is actually running.
Treat a mismatch as "the mirror is stale", not "the live project is wrong",
unless you have checked.

## Not yet mirrored

Only the grader is here. The project's other files — including `LeadCommand.gs`
— are still uncaptured and remain one-copy-on-earth. See Fix Queue #38.

The sibling scratch files in `00 Agency OS/call-intelligence/` (`audit.gs`,
`diag.gs`, `fixgeo.gs`, `julybackfill-fixes.gs`, `regrade.gs`, `scopepass.gs`)
are deliberately NOT mirrored. Decide whether any are load-bearing before
treating them as throwaway.
