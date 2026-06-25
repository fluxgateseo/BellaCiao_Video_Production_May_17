# Resume — BellaCiao Video Production

**Saved:** 2026-06-25 · **Branch:** `claude/nifty-wozniak-83k8ed`

## Channel goal (operative — overrides the bible's bare KPI line)

**Grow followers · keep character consistency · make restaurant owners relate to Bella.**

This is an audience-build phase. Optimise for identification over conversion. Concretely:

- **Primary signal:** follower growth + saves rate (>3%) + shares. Demo bookings / "DM CALL" triggers are the *lagging* signal that follows; they remain in the caption per Bible §10 but they're not the optimisation target right now.
- **Character consistency is a hard rule, not a quality note.** Bella's identity lock (Bible §1 — 25, NYC-born Irish-Italian, blue eyes, gold studs, voice id one-of `9DxYbhovJvj6zRtn0Pvc` / `M7ya1YbaeFaPXljg9BpK` / `YtOuYjXDObEJdpOIyUu1`) plus each friend's lock plus Ciao's lock must hold every render. New friends (Linh, Kostas) cannot ship until their `_close_face.png` exists and is wired in as the identity reference.
- **Relatability test (Quality Gate 7, promoted to a primary check):** "Would a restaurant owner share this at 11pm because it felt like their actual week?" If no, rewrite — even if every other gate passes.
- **Hook preference under this lens:** Type 4 (POV Confession), Type 5 (Uncomfortable Truth), Type 7 (Friend Cold Open) over the conversion-heavy Type 1 Callout. The Elixir stays human (Bible §6) — Jake takes Friday night off, Maria sleeps through the after-hours rush, Kostas pours wine instead of chasing the phone.

> The Bible's §2 north-star line ("demo bookings + DM triggers per week") was the *destination* metric; this section names the *navigation* metric for now. They don't conflict — followers + saves are the leading indicators of qualified demand. Folded into §17 (conflict log) at next bible revision.

## What this repo is right now

The **v2 premise-pivot canon is in the repo**:

- `CLAUDE.md` — v2 operating guardrails (auto-loaded by Claude Code each session).
- `BellaCiao_Master_Bible_v2.md` — single source of truth; `@`-imported by CLAUDE.md.
- `CONTENT_CALENDAR_June.md` — Days 10–24 / Jun 4–18; `@`-imported by CLAUDE.md.
- `.claude/agents/premise-guard.md` — PROACTIVE reviewer that fails SEO drift, on-camera pitch, retired enemies, off-canon cast.
- `Master Documents/Avatar_Prompts_Linh_Kostas.md` + `friends_db_additions_Linh_Kostas.json` — staging for the two new AU friends. Not yet integrated into `friends_db.json` (that file isn't in this repo yet — see Gaps).

The runbook (`BellaCiao_May17_Update_Runbook.md` in the `Bella Ciao Video - June 26` Drive folder) calls Steps 1–3 "safe drop-ins for instant alignment." Those are landed. Steps 4–10 (data + code migration) are still ahead and need the source pipeline to be located first.

## What yesterday's commit produced — now RETIRED

The `docs/day10-elevenlabs-redo.md` handoff that drove yesterday's work described "Bistrot Maison / no Reserve button / Bella front-facing host pitching a fix." That premise is **retired** by v2 (Bible §17, conflict #1) and would FAIL `premise-guard` on rules 1, 3, and 4 (SEO drift, on-camera pitch, retired GBP enemies). The destination Drive folder it pointed at (`1DpqBx2dUZP9ZA3W9Kfk2HXmY9_t6MaNE`) sits under the **Dao / destinybydao** project's "Day 10", not Bella Ciao — uploading there would have mis-attributed assets across two channels.

The three files from yesterday's commit are still in place but each has a **RETIRED** notice prepended:

- `docs/day10-elevenlabs-redo.md`
- `scripts/audio/day10_elevenlabs_vo.py`
- `scripts/audio/README.md`

They are kept for reference; **do not run**. The canonical Day 10 angle per `CONTENT_CALENDAR_June.md` is **Jake / Narrow Lane (Melb · Fitzroy) / Pillar A `the_missed_call`** — phone rings under the espresso machine, 9 brunch calls ring out, the 11am table walks next door, Ciao lifts his head. Under the goal above, this becomes a Type 7 Friend Cold Open ("Jake texted me mid-service…") with the Elixir = Jake taking Friday night off for the first time in months.

## Open decision — only the user can answer

**ElevenLabs voice ID for Bella.** Three candidates in play:

| Source | ID |
|---|---|
| v2 bible + pipeline | `9DxYbhovJvj6zRtn0Pvc` *(adopted as canon, pending one-time live confirmation)* |
| Legacy v1.2 bible | `M7ya1YbaeFaPXljg9BpK` |
| Yesterday's handoff (off-canon) | `YtOuYjXDObEJdpOIyUu1` |

Confirm against the live ElevenLabs voice once, then lock it everywhere (per Runbook Step 4c). Character consistency for Bella depends on this — pick wrong and every Reel sounds like a different person.

## Gaps blocking real "daily videos"

This repo currently has the **canon** but not the **pipeline**. The runbook references files that don't live here yet:

- `friends_db.json` (the 10-friend roster + arcs).
- `run.py` with stages `plan` / `brief` / `write` (the daily generator).
- `brand.py`, `video_prompts.py`, `ssml_tagger.py`, `quality_supervisor.py`.
- `Master Documents/Bella_Shorts_Hooks.xlsx` + `hooks_sync.py` + `data/bella_hooks.json`.
- `Bella_Ciao_Content_Sales_Alignment_Brief.md` (referenced by CLAUDE.md but not in scope folder).
- ElevenLabs egress (`api.elevenlabs.io`) is still off the environment allowlist — same blocker yesterday's note flagged.
- **Linh + Kostas `_close_face.png` + `_reference.png`** — character-consistency blocker for any AU episode that features them (Days 16, 18, 22 in the current calendar). Prompts in `Master Documents/Avatar_Prompts_Linh_Kostas.md`; Higgsfield MCP is connected and can generate from those prompts.

Locate the prior pipeline (probably a sibling repo or a Drive zip) before Step 4 of the runbook can run.

## Suggested next moves (in priority order under the goal above)

1. **Confirm Bella's voice id** (the only block that can't be worked around) — pick one of the three above against the live ElevenLabs voice.
2. **Generate Linh + Kostas avatar locks** via Higgsfield MCP from the committed prompts. Without these PNGs, character consistency for the two new AU friends has no anchor — they cannot appear in any Reel. (`_close_face.png` first, then pass it back as the identity reference for `_reference.png`.)
3. **Write Day 10 (Jake) under the relatability-first lens** — Type 7 Friend Cold Open hook, Elixir = Jake taking Friday night off, no demo pitch in script, DM trigger in caption. Run through `premise-guard` before any TTS.
4. **Locate the pipeline source** (`run.py`, `friends_db.json`, `brand.py`, `hooks_sync.py`) and merge into this repo — then Runbook Steps 4a–4h apply.
5. **Verify** — `python3 run.py --stage plan --plan-start 2026-06-04 --plan-days 14`, then `--stage brief --target-date 2026-06-04 --slot both --force`; invoke premise-guard on the Day 10 brief; must PASS.

Once verify is green and ElevenLabs egress is open, daily output (1 Reel + 1 Story + YouTube reuse) becomes a single `run.py --stage write --target-date <YYYY-MM-DD>` per day, with `premise-guard` gating every output.
