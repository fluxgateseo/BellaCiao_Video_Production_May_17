# Resume — BellaCiao Video Production

**Saved:** 2026-06-25 · **Branch:** `claude/nifty-wozniak-83k8ed`

## What this repo is right now

The **v2 premise-pivot canon is now in the repo**:

- `CLAUDE.md` — v2 operating guardrails (auto-loaded by Claude Code each session).
- `BellaCiao_Master_Bible_v2.md` — single source of truth; `@`-imported by CLAUDE.md.
- `CONTENT_CALENDAR_June.md` — Days 10–24 / Jun 4–18; `@`-imported by CLAUDE.md.
- `.claude/agents/premise-guard.md` — PROACTIVE reviewer that fails SEO drift, on-camera pitch, retired enemies, off-canon cast.
- `Master Documents/Avatar_Prompts_Linh_Kostas.md` + `friends_db_additions_Linh_Kostas.json` — staging for the two new AU friends. Not yet integrated into `friends_db.json` (that file isn't in this repo yet — see Gaps).

The runbook (`BellaCiao_May17_Update_Runbook.md` in the `Bella Ciao Video - June 26` Drive folder) calls Steps 1–3 "safe drop-ins for instant alignment." Those are now landed. Steps 4–10 (data + code migration) are still ahead and need the source pipeline to be located first.

## What yesterday's commit produced — now RETIRED

The `docs/day10-elevenlabs-redo.md` handoff that drove yesterday's work described "Bistrot Maison / no Reserve button / Bella front-facing host pitching a fix." That premise is **retired** by v2 (Bible §17, conflict #1) and would FAIL `premise-guard` on rules 1, 3, and 4 (SEO drift, on-camera pitch, retired GBP enemies). The destination Drive folder it pointed at (`1DpqBx2dUZP9ZA3W9Kfk2HXmY9_t6MaNE`) sits under the **Dao / destinybydao** project's "Day 10", not Bella Ciao — uploading there would have mis-attributed assets across two channels.

The three files from yesterday's commit are still in place but each has a **RETIRED** notice prepended:

- `docs/day10-elevenlabs-redo.md`
- `scripts/audio/day10_elevenlabs_vo.py`
- `scripts/audio/README.md`

They are kept for reference; **do not run**. The canonical Day 10 angle per `CONTENT_CALENDAR_June.md` is **Jake / Narrow Lane (Melb · Fitzroy) / Pillar A `the_missed_call`** — phone rings under the espresso machine, 9 brunch calls ring out, the 11am table walks next door, Ciao lifts his head.

## Open decision — only the user can answer

**ElevenLabs voice ID for Bella.** Three candidates in play:

| Source | ID |
|---|---|
| v2 bible + pipeline | `9DxYbhovJvj6zRtn0Pvc` *(adopted as canon, pending one-time live confirmation)* |
| Legacy v1.2 bible | `M7ya1YbaeFaPXljg9BpK` |
| Yesterday's handoff (off-canon) | `YtOuYjXDObEJdpOIyUu1` |

Confirm against the live ElevenLabs voice once, then lock it everywhere (per Runbook Step 4c).

## Gaps blocking real "daily videos"

This repo currently has the **canon** but not the **pipeline**. The runbook references files that don't live here yet:

- `friends_db.json` (the 10-friend roster + arcs).
- `run.py` with stages `plan` / `brief` / `write` (the daily generator).
- `brand.py`, `video_prompts.py`, `ssml_tagger.py`, `quality_supervisor.py`.
- `Master Documents/Bella_Shorts_Hooks.xlsx` + `hooks_sync.py` + `data/bella_hooks.json`.
- `Bella_Ciao_Content_Sales_Alignment_Brief.md` (referenced by CLAUDE.md but not in scope folder).
- ElevenLabs egress (`api.elevenlabs.io`) is still off the environment allowlist — same blocker yesterday's note flagged.

Locate the prior pipeline (probably a sibling repo or a Drive zip) before Step 4 of the runbook can run.

## Suggested next step

After the voice-ID confirmation, work through the runbook in order, pausing for a diff review after each task:

1. **Task 4a** — import `friends_db.json` from the source pipeline, merge Linh + Kostas from `Master Documents/friends_db_additions_Linh_Kostas.json`, reframe every before/after to calls/bookings.
2. **Task 4b** — grep & retire the GBP enemies in any imported code.
3. **Task 4c** — lock the chosen voice id everywhere.
4. **Task 4d** — rewrite the 20 hooks; run `hooks_sync.py`.
5. **Verify** — `python3 run.py --stage plan --plan-start 2026-06-04 --plan-days 14`, then `--stage brief --target-date 2026-06-04 --slot both --force`; invoke premise-guard on the Day 10 brief; must PASS.

Once verify is green and ElevenLabs egress is open, daily output (1 Reel + 1 Story + YouTube reuse) becomes a single `run.py --stage write --target-date <YYYY-MM-DD>` per day.
