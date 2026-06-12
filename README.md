# Bella Script Engine

The active script-layer engine for the Bellaciao content system. It owns:

- v2.1 staged script production in `run.py`
- v3.0 triplet expansion in `run_v3.py`
- ShotApproval prompt generation in `pipeline_v3/visualize_v3.py`

It produces Bella scripts, captions, triplet derivatives, YouTube metadata,
and ShotApproval prompt files. It deliberately does **not** render video,
generate voice, stitch clips, or publish.

It also coexists with two **global audit skills** in `~/.claude/skills/`:
`bella-coherence-strategist` ("The Soul") and
`bella-retention-architect` ("The Hook"). Those are review/rewrite tools for
Bella assets, not pipeline stages.

> **Source of truth:** `../CLAUDE.md`,
> `../Master Documents/DAILY_CHANNEL_OPERATING_MODEL.md`,
> `../Master Documents/CONTENT_PRODUCTION_SYSTEM.md`,
> `../Master Documents/CONTENT_PRODUCTION_SYSTEM_V3.md`,
> `../Master Documents/SHOTAPPROVAL_VISUALIZE_SPEC.md`,
> and `../Master Documents/BELLA_MASTER_BIBLE.md`.

## Mission

Convert restaurant owners in AU/US/UK into demo bookings. Game: Authority
Building. The full mission, persona, framework, and rules are distilled in
[brand.py](brand.py) — single source of truth for this engine.

## Default operating model

The canonical daily publishing model is:

- 1 Reel per day
- 1 Story per day
- YouTube reuses the Reel's core content with packaging changes

That means `run.py` is the default daily pipeline. `run_v3.py` remains available for additive experiments, not as the default day-to-day production path.

## Architecture

```
script_engine/
├── brand.py                Brand bible constants (mission, persona, rules, weights)
├── apify_scout.py          Apify YT + IG scraper → Claude synthesis → trend_signals.json
├── logical_gate.py         Pre-generation date/market/friend/currency lock
├── strategy.py             Calendar-driven brief picker
├── engine.py               Multi-model competition + self-grader + Opus judge (Claude)
├── quality_supervisor.py   7-gate check + rewrite loop + polish pass
├── ssml_tagger.py          ElevenLabs SSML markup (post-approval)
├── memory.py               Cross-session rotation tracking
├── assets.py               Bella / Ciao / friend avatar path resolver
├── run.py                  v2.1 staged CLI (calendar → plan → brief → write → play)
├── run_v3.py               v3 dispatcher (calendar / brief / write / package / visualize)
├── pipeline_v3/
│   ├── skills_client.py    Claude skill wrappers used by v3
│   ├── brief_v3.py         Adds triplet_strategy to approved Briefs rows
│   ├── write_v3.py         Copies approved Reel + derives YT Short + Carousel
│   ├── package_v3.py       Generates captions + YT metadata
│   └── visualize_v3.py     Pushes ShotApproval rows + image prompt bodies (Runway Gen-4 Image)
├── requirements.txt
├── data/
│   ├── friends_db.json      Canonical friends and identity metadata
│   ├── calendar.json        Restaurant events
│   ├── trend_signals.json   Output of apify_scout
│   ├── strategy_brief.json  Output of strategy
│   ├── memory.json          Cross-session state
│   └── jobs/                Archive copy of v2 scripts
├── ../Creatives/Daily assets/Day N/
│   ├── scripts/             v2 script JSON + text companions
│   ├── avatars/             character reference prompt files / images
│   └── ShotApproval/        per-shot prompt bodies for image generation
└── ../Scripts_v3/Day N/
    ├── *_REEL.json
    ├── *_YTSHORT.json
    ├── *_CAROUSEL.json
    ├── *_PACKAGE_YT.json
    └── *_CAPTION_{REEL,YT,CAROUSEL}.md
```

## Setup

API keys live in a **single shared `.env` at the parent `Bellaciao Content/`
folder** — every script in `script_engine/` (and any sibling project) loads
from that same file. There is no per-project `.env`.

```bash
cd script_engine
/opt/homebrew/bin/python3.11 -m venv --clear .venv
./.venv/bin/pip install -r requirements.txt

# One .env for the whole Bellaciao Content/ folder:
cp ../.env.example ../.env
# then fill in ANTHROPIC_API_KEY (required) + at least one other writer key
```

## Usage

Run every command from inside `Bellaciao Content/script_engine/` so the
relative `./.venv/bin/python` path stays stable even though the parent folder
name contains spaces.

```bash
cd script_engine

# Sanity-check the Python 3.11 venv first.
./.venv/bin/python --version

# If ./.venv/bin/python is missing or points at an older interpreter:
# /opt/homebrew/bin/python3.11 -m venv --clear .venv
# ./.venv/bin/pip install -r requirements.txt

# v2.1 status / control surface
./.venv/bin/python run.py --status

# Stage 1: sync calendar events for review
./.venv/bin/python run.py --stage calendar --days 90

# Stage 2: generate the planning calendar
./.venv/bin/python run.py --stage plan --plan-start 2026-04-15 --plan-days 14

# Stage 3: generate reviewable briefs for one day
./.venv/bin/python run.py --stage brief --target-date 2026-04-25 --slot both

# Stage 4: write one approved script
./.venv/bin/python run.py --stage write --target-date 2026-04-25 --slot story

# One-click queue flow for rows ticked ready_to_write
./.venv/bin/python run.py --stage play

# Legacy end-to-end smoke test (bypasses Airtable approval gates + Apify scout)
./.venv/bin/python run.py --auto --target-date 2026-04-25 --format reel --no-airtable --no-scout

# v3.0 additive triplet flow (optional, not the default daily path)
./.venv/bin/python run_v3.py --stage brief --day 12
./.venv/bin/python run_v3.py --stage write --day 12
./.venv/bin/python run_v3.py --stage package --day 12

# ShotApproval prompt generation
./.venv/bin/python run_v3.py --stage visualize --day 12

# Audit an existing Bella asset with the global Soul + Hook skills
# (Claude skill workflow, not a pipeline command)
# audit "Creatives/Daily assets/Day 1/Reel 01 (Day 1)/"
```

If Airtable is unavailable, `--stage plan` still writes the local plan to
`data/content_calendar.json` and `--stage brief` caches previews in
`data/briefs_local.json`. Those local files become the fallback control surface
until Airtable comes back.

For the legacy one-shot smoke path, add `--no-scout` alongside `--no-airtable` to avoid the Apify dependency too. That path still requires `ANTHROPIC_API_KEY` plus at least one writer model key.

## Outputs

The v2.1 Reel pipeline lands in two places:
- `data/jobs/{episode_id}.json` — internal archive
- `../Creatives/Daily assets/Day N/scripts/{episode_id}.json` — human-facing folder

Its planning gate now depends on four user-set Airtable choices before brief
generation can proceed:
- `hook_choice`
- `pillar_choice`
- `story_seed_choice`
- `sensory_hook_choice`

Each job file contains:

```jsonc
{
  "episode_id":          "bella_jake_p1_20260410_1432",
  "pipeline_version":    "1.2",
  "brief":               { ... },
  "gate_result":         { ... },
  "round":               2,
  "score":               9.62,
  "verdict":             { "winner": "C", "scores": {...}, ... },
  "supervisor":          { "status": "APPROVED", "gates": {...}, ... },
  "story_spine":         "<SECTION 1>",
  "video_script":        "<SECTION 2 — spoken by Bella>",
  "video_script_ssml":   "<ElevenLabs-ready SSML>",
  "caption":             "<SECTION 3 — caption with 5 woven hashtags>",
  "scene_brief":         { ... SECTION 4 JSON with avatar paths ... },
  "near_perfect_override": false,
  "generated_at":        "2026-04-10T14:32:11"
}
```

The v3.0 triplet pipeline writes to `../Scripts_v3/Day N/`:
- `{episode_id}_REEL.json`
- `{episode_id}_YTSHORT.json`
- `{episode_id}_CAROUSEL.json`
- `{episode_id}_PACKAGE_YT.json`
- `{episode_id}_CAPTION_REEL.md`
- `{episode_id}_CAPTION_YT.md`
- `{episode_id}_CAPTION_CAROUSEL.md`

The visualize stage writes to `../Creatives/Daily assets/Day N/`:
- `avatars/{character_id}_prompt.txt`
- `ShotApproval/{scene_id}_start_prompt.txt`
- `ShotApproval/{scene_id}_end_prompt.txt` when applicable

## What's out of scope

This project does NOT handle voice generation, video clip generation, lip sync,
final edit/stitch, caption burn-in, or publishing. Those remain downstream.

**Out of scope for the entire ecosystem** (not just this project): publishing
of any kind, and any messaging-bot / approval-gate workflow. The video tool
produces files; the user moves them by hand from there.
