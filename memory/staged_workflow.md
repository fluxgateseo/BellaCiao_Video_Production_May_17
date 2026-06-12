---
name: Staged pipeline with Airtable verdict gates
description: Staged manual-control workflow. Each stage refuses to advance unless the upstream Airtable verdict is approved.
type: project
---

The script_engine pipeline is a **staged workflow with manual verdict gates in Airtable**. The user explicitly requested this on 2026-04-10 ("I want to verify main days of the year, story to tell and input before we create scripts. update the pipeline to give me full manual control").

## The stages — IMPLEMENTED 2026-04-10

```
1. CALENDAR  python3 run.py --stage calendar --days 90 --tier 1
             → calendar_sync.sync_calendar() walks calendar.json
             → upserts Tier-1 events to Calendar table by event_id_year
             → verdict=unreviewed on new rows; existing verdicts preserved
             → STOP. User marks scheduled/skip per event.

2. PLAN      python3 run.py --stage plan --plan-start 2026-04-15 --plan-days 14
             → content_calendar_sync generates ContentCalendar rows
                  (2 per day × N days = story + reel slots)
             → status=draft on new rows; existing statuses preserved
             → STOP. User marks planned/skip per slot, may override
                  friend/pillar per row.

3. BRIEF     python3 run.py --stage brief --target-date 2026-04-25 --slot reel
             → REFUSES if ContentCalendar has no status=planned row for
                  (target_date, slot) — unless --force
             → REFUSES if Calendar has target_date as Tier-1 verdict=skip
             → runs logical_gate.run_gate(target_date)
             → runs strategy.generate_brief() — anchors on friend profile,
                  neighbourhood, operational detail, and Tier-1 calendar
                  events when in window
             → builds writer_prompt_preview from engine.build_generation_prompt()
             → briefs_sync.preview_brief() pushes BOTH to Briefs row
                  with script_produced=false and verdict=unreviewed
             → STOP. User reviews the brief + prompt in Airtable,
                  marks good/reject/rewrite_needed.

4. WRITE     python3 run.py --stage write --target-date 2026-04-25 --slot reel
             python3 run.py --stage write --brief-id rec123
             → REFUSES unless brief verdict=good (--force to bypass)
             → REFUSES if script_produced already true (no duplicates)
             → briefs_sync.fetch_approved_brief_for_date() picks the brief
             → runs engine.write_and_judge() + supervisor (+ polish)
             → ssml_tagger.tag_script() + shot_director.build_shot_list()
             → continuity.update_state_from_job() → per-friend arc update
             → writes Creatives/Daily assets/Day N/scripts/{episode_id}.json
             → push_script() to the Scripts table
             → mark_brief_episode() stamps the brief row with episode_id
```

`python3 run.py --status` (or just `python3 run.py`) shows row counts per
verdict for each of the tables, plus the next 10 pending briefs and
scheduled calendar events. Always safe to run.

## Refusal rules

- `--stage brief` refuses if **ContentCalendar** has no `status=planned` row for (target_date, slot) — unless `--force` is passed.
- `--stage brief` refuses if **Calendar** has the target_date as a Tier-1 event with `verdict=skip` (the user explicitly said no script for that event) — unless `--force`.
- `--stage write` refuses unless the brief's `verdict=good` — unless `--force`.

`--force` exists for testing and emergencies; the warning text reminds the user they're bypassing review.

## Why a `Briefs` row covers BOTH "story to tell" AND "input"

The user listed things to verify: main days, **story to tell**, **input**. Story-to-tell is the structured brief (calendar event / friend / enemy / tone / director_note). Input is the assembled writer prompt the LLMs will see. Both live on the same Briefs row — the brief is the structured fields, the `writer_prompt_preview` is the assembled string. One row, one verdict, both checkpoints satisfied at once.

## Default vs auto

`python3 run.py` (no stage) defaults to `--status` — never runs anything, never spends API tokens. The legacy "do everything in one shot" behaviour is available via `python3 run.py --auto --target-date YYYY-MM-DD`. Auto bypasses ALL verdict gates and is for testing / smoke checks only — never use for production output.

## Modules involved

- `calendar_sync.py` — sync calendar.json → Calendar table; `list_calendar()`
- `content_calendar.py` + `content_calendar_sync.py` — daily plan generation → ContentCalendar table
- `logical_gate.py` — locks market/city/friend/currency before the director runs
- `strategy.py` — generates the brief, anchored on friend profile + calendar events only
- `engine.py` — multi-model writers + self-grader + judge
- `quality_supervisor.py` — 7-gate check + polish pass
- `ssml_tagger.py` — ElevenLabs SSML markup
- `shot_director.py` — model-agnostic per-clip prompts
- `continuity.py` — per-friend serialised narrative arc update (post-approval)
- `memory.py` — mechanical cooldowns (friend/enemy/ally/scenario/pillar)
- `briefs_sync.py` — `preview_brief()` (push for review), `fetch_approved_brief_for_date()`, `mark_brief_episode()`
- `airtable_sync.py` — `push_script()` (final archive)
- `run.py` — the staged orchestrator with all stage functions plus `stage_status` and `stage_auto`

## Why this matters

- **The user is in the loop on every input that shapes a script.** No more "run it and pray".
- **Airtable becomes the editorial workspace.** Phone-friendly, multi-user, no terminal needed for review.
- **Re-running a stage is idempotent.** Calendar/ContentCalendar upsert by id, Briefs upsert by run_id.
- **The legacy auto path still exists** for tests, dry runs, and any future automation, behind `--auto` so it's never accidentally invoked.

## How to apply

- When extending the pipeline, ALWAYS add the new behaviour as a stage or as a check inside an existing stage. Never add background work that bypasses the verdict gates.
- When the user asks to "skip the review" or "just run it", confirm they want `--force` (single stage) or `--auto` (whole pipeline). Default to `--force` since it's more granular.
- Verdicts are NEVER auto-set by the pipeline. Only the user moves them from unreviewed to anything else.
