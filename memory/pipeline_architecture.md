---
name: Pipeline architecture
description: The three-stage script engine flow — apify_scout → strategy → engine — and how each stage hands off via JSON files on disk
type: project
---

The engine is three stages, each independently runnable, each reading the previous stage's JSON output from disk. `run.py` is the single CLI entry point that chains them.

**Stage 1 — apify_scout.py (TREND DATA)**
Scrapes YouTube + Instagram via Apify actors, then asks Claude Haiku to synthesise what's converting in the restaurant niche right now → `data/trend_signals.json`. Signals expire after 24h. Apify is optional — missing token = empty signals, run continues.

**Stage 2 — strategy.py (BRIEF)**
Loads next 30 days of `data/calendar.json`, the 8 friends from `data/friends.json`, and the trend signals. Asks Claude Opus to pick ONE brief: format/pillar/friend/enemy/ally/tone/duration/calendar_event/director_note → `data/strategy_brief.json`. Tier-1 calendar events (Valentine's, Mother's Day, Christmas) MUST be referenced when in window.

**Stage 3 — engine.py (WRITE)**
Runs 4 writer models (Claude Sonnet, GPT-4o, Gemini 2.0 Flash, DeepSeek) in parallel threads with distinct MODEL_ROLES voices. Labels A/B/C/D are blind to the Opus judge. Judge scores on 9 weighted dimensions. Winner runs through 7-gate check. Up to 3 rewrite rounds with structured per-dimension feedback, then a polish pass on the 2 weakest dimensions if still under 9.5. Output → `data/jobs/{episode_id}.json`.

**Why:** The on-disk handoff makes every stage independently re-runnable (e.g. iterate on engine.py against an existing brief without re-scraping). Parallel writers + blind judging avoids single-model bias and is the part that actually pushes scores past 9.5.

**How to apply:** When changing one stage, only its inputs/outputs are the contract. Re-running engine.py against the same brief produces a NEW timestamped episode_id — previous jobs are never overwritten. Writers run in parallel; judge and polish are sequential. If you add a new writer, append to the tasks list in `generate_scripts_parallel()` and add a `MODEL_ROLES` entry in brand.py.
