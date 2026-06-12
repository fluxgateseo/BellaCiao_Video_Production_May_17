# Script Engine — Project Scope

*Last updated: 2026-04-10*

## What this project is

A standalone, single-purpose engine that produces **one ≥9.5/10 Bella story
script per invocation** — fully formed, calendar-aware, trend-informed,
ready to hand to a video stage.

Inputs:
- An optional pillar/friend/format override (CLI flags)
- Live competitor data (Apify scraping of YouTube + Instagram)
- The 30-day restaurant calendar
- The 8-friend canonical roster

Output:
- One JSON job file containing the spoken script (Section 2), social
  caption (Section 3), scene brief (Section 4), Pixar story spine (Section 1),
  the judge's verdict, and the gate results.

That's it. No audio. No video. No analytics.

## What this project is NOT

- Not a video generator
- Not a TTS layer
- Not a memory system (no cross-session learning, no analytics loops)
- Not a multi-job orchestrator. One brief in, one script out.

If a user needs any of those capabilities, they belong in a separate sibling
project. Publishing of any kind, and any messaging-bot / approval-gate
workflow, are out of scope for the entire ecosystem — not just this project.

## Why split it out

Boundary failures dominate multi-stage pipelines. Script generation is the
part that **drives revenue** (a 9.5+ script is the difference between a DM
and a scroll-by) — it deserves to live on its own, with its own brand bible,
its own dependencies, its own tests, and its own runtime.

## Mission (inherited from MASTER_INSTRUCTIONS)

Convert restaurant owners in Australia, the USA, and the UK into demo bookings.

- **Primary metric**: Demo bookings + trial activations per week
- **Secondary metric**: DM trigger keywords ("BELLA" / "TRIAL" / "DEMO")
- **Game**: Authority Building (primary) + Explanatory Product (secondary)
- **Outlier criteria**: saves rate >3% OR DM trigger activated — never view count alone

## Success criteria for this project

A run is successful when:
1. The engine returns a script with `score ≥ 9.5` from the blind Opus judge, OR
2. The engine returns a script with `score ≥ 9.6` and 6/7 final gates passed
   (near-perfect override).

Soft success (exit code 2): the engine returns the best script it ever
produced even if it never cleared 9.5. The operator can decide whether to
rerun, force a different friend, or accept the lower score.

Hard failure: zero usable scripts after 3 rounds + polish pass + best-effort
fallback. Returns `{"status": "ESCALATED"}`.

## In-scope modules

| Module | Responsibility |
|---|---|
| `brand.py` | Brand bible constants. Single source of truth. |
| `apify_scout.py` | Scrape competitor content via Apify. Synthesise with Claude Haiku. |
| `strategy.py` | Resolve calendar events. Pick the brief (friend/pillar/enemy/duration). |
| `engine.py` | Multi-model writers + Opus judge + 7-gate + rewrite + polish. |
| `run.py` | CLI orchestrator: scout → strategy → engine. |

## Out-of-scope (explicitly)

- Audio generation, alignment, audio QA
- Video composition, captions, transitions, lipsync
- Image generation (food photos, avatar references)
- Cloudflare R2 / Drive / OAuth uploaders
- Multi-job orchestration, daily cron, batch runs
- Cross-session intelligent memory and analytics loops
- A/B testing, performance learning

**Out of scope for the entire Bellaciao ecosystem** (not just this project):
publishing of any kind, and any messaging-bot / approval-gate workflow.

If any of these creep in, **fork a separate project**. Do not pollute the
script engine.

## Dependencies

Hard requirements:
- Python 3.11+
- `ANTHROPIC_API_KEY` (judge + strategy + at least one writer)

Soft requirements (any subset works — more = better blind competition):
- `OPENAI_API_KEY` (GPT-4o writer)
- `GEMINI_API_KEY` or `GOOGLE_API_KEY` (Gemini 2.0 Flash writer)
- `DEEPSEEK_API_KEY` (DeepSeek writer)

Optional:
- `APIFY_TOKEN` + actor IDs (trend signals)

No external infrastructure: no databases, no queues, no Docker, no cloud
services. Pure Python + HTTP calls. Outputs are JSON files on disk.

## Versioning rule

The brand bible (`brand.py`) and the data files (`data/friends.json`,
`data/calendar.json`) are the only files that should change frequently.
The pipeline modules (`apify_scout.py`, `strategy.py`, `engine.py`, `run.py`)
should remain stable — if they need to change, the change goes through a
pipeline doc update first.
