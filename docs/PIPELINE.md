# Script Engine — Pipeline Specification

*Last updated: 2026-04-10*

This document is the canonical reference for HOW a Bella script gets written.
Read this before changing `apify_scout.py`, `strategy.py`, or `engine.py`.

## Pipeline diagram

```
                    ┌─────────────────────────────┐
                    │  run.py  (CLI entry point)  │
                    └──────────────┬──────────────┘
                                   │
                ┌──────────────────┼──────────────────┐
                ▼                  ▼                  ▼
       ┌────────────────┐  ┌──────────────┐  ┌──────────────┐
       │ apify_scout.py │  │  strategy.py │  │   engine.py  │
       │  (TREND DATA)  │  │   (BRIEF)    │  │   (WRITE)    │
       └───────┬────────┘  └──────┬───────┘  └──────┬───────┘
               │                  │                 │
               ▼                  ▼                 ▼
   data/trend_signals.json  data/strategy_brief.json   data/jobs/{id}.json
               │                  │                 ▲
               └──────────────────┴─────────────────┘
                          (read by next stage)
```

Each stage reads the output of the previous stage from disk. Stages are
independently runnable — you can re-run `engine.py` against an existing
`strategy_brief.json` without re-scraping or re-strategising.

## Stage 1 — Apify Trend Scout (`apify_scout.py`)

**Purpose**: Find what's converting *right now* in the restaurant niche, so
the strategy stage can pick angles that ride active trends instead of guessing.

**Inputs**:
- `APIFY_TOKEN` + actor IDs from `.env`
- Hardcoded YouTube search queries (5 restaurant/hospitality terms)
- Hardcoded Instagram hashtags (`restaurantlife`, `noshows`, etc.)
- Calendar events from `data/calendar.json` (next 14 days, via `strategy.upcoming_events`)

**Process**:
1. Run the Apify YouTube actor (`h7sDV53CddomktSi5` by default) with the
   search queries. Poll until `SUCCEEDED`. Fetch up to 50 dataset items.
2. Run the Apify Instagram hashtag actor (if configured). Poll, fetch.
3. Run the Apify Instagram Reels actor (if configured). Poll, fetch.
4. Sort the IG posts by engagement (likes + comments).
5. Build a synthesis prompt for Claude Haiku containing:
   - Top 5 upcoming calendar events
   - Top 8 IG posts (engagement-ranked)
   - Top 8 YouTube videos
6. Claude Haiku returns a JSON object with `this_week_priority`,
   `timely_hooks`, `trending_formats`, `hashtag_opportunities`,
   `content_gaps`, and `analyzed_at`.

**Output**: `data/trend_signals.json` — consumed by `strategy.py`.

**Failure modes**:
- Apify token missing → returns empty list, scout still runs but with no
  scraped data; Claude analyses calendar only.
- Actor poll timeout (default 120s) → that source returns `[]`, others continue.
- Claude JSON parse failure → returns `{"error": ..., "analyzed_at": ...}`,
  saved to disk so the strategy stage knows the signals are broken.

**Freshness**: signals expire after 24h. `get_trend_context()` returns "stale"
text after that, which Claude Opus in the strategy stage will treat as
"no trend data — use calendar only".

**Where to extend**:
- New scraping sources → add a `scrape_*()` function and call it from `run()`.
- New monitored hashtags → edit `IG_HASHTAGS` constant.
- New search queries → edit `YT_SEARCH_QUERIES` constant.
- Change synthesis model → swap the model name in `_analyze_with_claude`.

---

## Stage 2 — Strategy Director (`strategy.py`)

**Purpose**: Pick the SINGLE next piece of content. Calendar-first storytelling.

**Inputs**:
- `data/friends.json` (8 canonical friends)
- `data/calendar.json` (40+ restaurant events with tier + storytelling_hook)
- `data/trend_signals.json` (output of stage 1, optional)
- `brand.py` (mission, pillars, enemies, allies, duration guide)
- CLI overrides: `--format`, `--pillar`, `--friend`

**Process**:
1. **Calendar resolution**: `upcoming_events(days_ahead=30)` walks
   `data/calendar.json` and returns events whose next occurrence falls within
   30 days, sorted ascending by `days_until`.
   - `fixed` events: same month/day every year
   - `nth_weekday` events: e.g. "2nd Sunday in February" (Super Bowl)
   - `cultural` events: a recurring weekday
2. **Tier system** (tier 1 = highest revenue impact):
   - Tier 1 in window → ALL content MUST reference the event
   - Tier 2 in window → at least 2/3 references
   - Tier 3 in window → at least 1/3 references
   - Multiple events overlap → tier first, then `days_until`
3. **Trend injection**: `get_trend_context()` from `apify_scout` returns a
   formatted string of priorities, timely hooks, formats, hashtags, gaps.
4. **Brief generation**: Claude Opus is given the full prompt
   (mission + duration guide + events + trends + friends + enemies + allies +
   pillars + constraints) and asked to return ONE JSON brief.
5. **JSON parse + save** to `data/strategy_brief.json`.

**The brief schema**:
```jsonc
{
  "format": "reel" | "story",
  "pillar": 1 | 2 | 3 | 4 | 5,
  "calendar_event": "Mother's Day",
  "calendar_days_until": 14,
  "friend": "naomi",
  "enemy": "the_no_show",
  "ally": "the_staff_member_who_stayed",
  "tone": "warm_and_real" | "funny_and_painful" | "quietly_proud" | "late_night_honest",
  "target_duration_seconds": 18,
  "duration_rationale": "why this length serves the engagement goal",
  "food_hook_hint": "specific dish for the sensory hook",
  "trend_anchor": "Mother's Day restaurant bookings 2026",
  "director_note": "the single most important thing the writer must nail"
}
```

**Failure modes**:
- Calendar file missing → `upcoming_events()` returns `[]`, Opus picks from
  evergreen pillar pain points.
- Trend signals stale or missing → text says "no trend data", Opus falls back
  to calendar-driven angles only.
- JSON parse failure → not currently retried; the run fails.

**Where to extend**:
- New event types → add a branch in `_next_occurrence()`.
- New tones → update the `tone` field allowed values + the prompt + the
  writer prompts in `engine.py`.
- New duration buckets → edit `DURATION_GUIDE` in `brand.py`.
- New calendar events → add to `data/calendar.json` with `revenue_tier`,
  `campaign_window_days`, `content_angles`, `storytelling_hook`.

---

## Stage 3 — Multi-Model Engine (`engine.py`)

**Purpose**: Take the brief and produce a script that scores ≥9.5/10.

This is the heart of the project. It is the part that turns "we'd like a
good script" into "the restaurant owner shares this at 11 PM without writing
a caption".

**Inputs**:
- `data/strategy_brief.json` (output of stage 2)
- `brand.py` (Bella brief, Disney universe, Pixar/Vogler, sensory arc, rules,
  scoring weights, gates)
- `data/friends.json` (resolves the brief's `friend` ID to full friend record)

**Process**:

### 3.1 — Build the generation prompt
`build_generation_prompt(brief)` concatenates:
1. `brand.BELLA_BRIEF` — non-negotiable character rules
2. `brand.DISNEY_UNIVERSE` — required cast roles
3. `brand.DUAL_FRAMEWORK` — Pixar Spine + Vogler Inner Journey
4. `brand.SENSORY_ARC` — 3-act video structure
5. `brand.CONTENT_RULES` — banned words, hard rules
6. **The cast section** built from the brief (HERO/SHADOW/ALLY with
   descriptions from `brand.ENEMIES` / `brand.ALLIES`)
7. **Output instructions**: SECTION 1 (Story Spine), SECTION 2 (Video Script
   with word-count target = `duration × 2.5`), SECTION 3 (Caption),
   SECTION 4 (Scene Brief JSON)
8. **Rewrite notes** (from previous round, if any)

### 3.2 — Parallel writers
`generate_scripts_parallel(prompt)` runs all configured writers in parallel
threads. Each writer gets a distinct system role from `brand.MODEL_ROLES`:

| Model | Role | Voice |
|---|---|---|
| Claude Sonnet 4.6 | `claude` | Restraint and precision. Every word earns its place. |
| GPT-4o | `gpt4o` | Narrative architect. Builds stories with momentum. |
| Gemini 2.0 Flash | `gemini` | Cinematic frame before sentence. |
| DeepSeek | `deepseek` | The inside angle. Truth precisely written. |

Labels A/B/C/D are blind to the judge. Failed writers are skipped — the run
continues with whatever survives.

### 3.3 — Blind judge (Claude Opus)
`judge_scripts(scripts)` sends all surviving candidates to Claude Opus with
the `JUDGE_PROMPT`. Opus scores each on 9 weighted dimensions:

| Dimension | Weight | What it measures |
|---|---|---|
| Sensory opening | 20% | Can the first sentence be smelled / heard / felt? |
| Emotional recognition | 25% | "That's me right now." The leans-in moment. |
| Story Spine momentum | 15% | Does Pixar's 8-sentence structure hold? |
| Enemy presence | 10% | Is the Shadow specific and inevitable? |
| Vogler transformation | 10% | Does the hero change inside? |
| Bella as mentor | 5% | Present but not dominant. |
| Ciao turning point | 5% | Appears once. Marks the turn. Inner monologue, never speech. |
| The Elixir | 10% | Small, human, earned — never a product. |
| Zero-sell integrity | 5% | BINARY 10 or 0. Any pitch = automatic 0. |

Returns: `{scores, recommendation: WINNER|SYNTHESISE|REWRITE, winner, rewrite_notes, best_weighted_score}`.

### 3.4 — 7-gate final check
If the winner clears `PASS_THRESHOLD = 9.5`, `run_7_gate(candidate)` runs the
seven final quality gates (see `brand.SEVEN_GATES`):

1. Does the first sentence stop the scroll before the second word?
2. Is the ordeal so specific it could only be THIS restaurant, THIS night?
3. Does Ciao's appearance mark a real turning point — not decoration?
4. Is the Elixir small, human, earned — not a product?
5. Are there 3+ consecutive words that could be cut?
6. Can this run unchanged on ElevenLabs at natural pace within target duration?
7. Would a restaurant owner share this at 11 PM without writing a caption?

**Near-perfect override**: if score ≥ 9.6 AND 6/7 gates pass, accept anyway.
Don't let one picky gate kill an excellent script.

### 3.5 — Rewrite loop
If the score is below 9.5 OR gates failed, build structured per-dimension
feedback via `build_rewrite_notes()`:

- Each dimension is marked ❌ WEAK / ⚠️ THIN / ✓ strong
- The judge's `best` and `improve` notes are surfaced
- The list of weak dimensions is named explicitly: "push these above 9.5"
- The instruction is **surgical**: do NOT change what already works

This loops up to `MAX_ROUNDS = 3` times. Best score and best candidate are
tracked across all rounds.

### 3.6 — Polish pass (last resort)
If no round cleared 9.5 after 3 rounds, `polish_script()` runs a surgical
Opus pass on the 2 weakest dimensions:
- Same SECTION 1/2/3/4 headers
- Same hero, enemy, ally, duration, beats
- Only the lines holding the score back get rewritten
- Re-judged. If improved, replaces the best candidate.

### 3.7 — Output assembly
`_build_output()` assembles the final job dict:
```jsonc
{
  "episode_id": "bella_jake_p1_20260410_1432",
  "brief": { ... },
  "round": 2 | "polish",
  "score": 9.62,
  "verdict": { "scores": {...}, "winner": "C", ... },
  "script": "<full SECTION 1/2/3/4 text>",
  "story_spine": "<SECTION 1>",
  "video_script": "<SECTION 2 — spoken by Bella>",
  "caption": "<SECTION 3 — caption with 5 woven hashtags>",
  "scene_brief": "<SECTION 4 — scene JSON>",
  "gates": { "gate_1": {"pass": true, ...}, ... },
  "near_perfect_override": false,
  "generated_at": "2026-04-10T14:32:11"
}
```

Saved to `data/jobs/{episode_id}.json`.

**Failure modes**:
- All writers fail → `RuntimeError`. The run dies.
- Judge JSON malformed → returns `recommendation: REWRITE` with empty notes,
  next round retries blind.
- Polish output missing SECTION headers → reverts to original best candidate.
- Polish re-judge fails → keeps the original.
- Best-effort fallback: if `final_output is None` but `best_candidate` exists,
  ship the best candidate with score < 9.5 (exit code 2).
- Hard failure: `{"status": "ESCALATED", "best_score": 0}`.

**Where to extend**:
- Add a 5th writer → add a `_modelname()` function and append to the `tasks`
  list in `generate_scripts_parallel()`.
- Change scoring weights → edit `brand.SCORING_WEIGHTS` and update the
  `JUDGE_PROMPT` weights inline.
- Tune the polish pass → change `MODEL_CLAUDE_JUDGE` to a different model,
  or change the "fix only weakest 2 dimensions" rule.
- Lower/raise threshold → edit `brand.PASS_THRESHOLD` and `brand.NEAR_PERFECT`.

---

## Data contracts

### `data/friends.json` (8 records)
```jsonc
{
  "id": "jake",                          // unique slug, used by --friend flag
  "name": "Jake",
  "age": 37,
  "nationality": "Australian-Nepalese",
  "location": "Melbourne",               // NY | London | Melbourne ONLY
  "neighbourhood": "Fitzroy",
  "restaurant_style": "...",
  "fantasy_restaurant_name": "Narrow Lane",
  "archetype_owned": "The Grinder — ...",
  "story_angle": "...",                  // one-line story seed
  "sensory_food_hook": "A single-origin pour-over served at exactly 93 degrees, ...",
  "pillar_affinity": 1,                  // suggested default pillar
  "avatar_context": "busy",              // busy|kitchen|calm|sharp|table|bar
  "enemy_archetype": "The Overflow — when success becomes the thing that breaks you",
  "yt_seo_title": "300 Covers and the Call He Missed (Jake's Story)",
  // optional for couples:
  "is_couple": true,
  "partner_name": "Maria",
  "child": { "name": "Luca", "age": 8, "gender": "male" }
}
```

### `data/calendar.json`
```jsonc
{
  "_note": "Calendar-first storytelling engine.",
  "events": [
    {
      "name": "Mother's Day",
      "countries": ["AU", "UK", "US"],
      "type": "fixed" | "nth_weekday" | "cultural",
      "month": 5,
      "day": 11,                          // for "fixed"
      "weekday": 6,                       // for "nth_weekday" / "cultural" (0=Mon..6=Sun)
      "n": 2,                             // for "nth_weekday" (2nd Sunday)
      "revenue_tier": 1,                  // 1 | 2 | 3
      "campaign_window_days": 21,         // how many days before content must reference it
      "content_angles": ["...", "..."],
      "storytelling_hook": "The emotional seed for the story",
      "emoji": "💐",
      "notes": "..."                      // optional
    }
  ]
}
```

### `data/trend_signals.json` (output of `apify_scout.py`)
```jsonc
{
  "this_week_priority": "one sentence",
  "timely_hooks": [
    {"hook": "...", "friend": "naomi", "pillar": 1, "urgency": "high"}
  ],
  "trending_formats": [
    {"format": "specific_number_hook", "bella_adaptation": "$8,400 lost in 4 days"}
  ],
  "hashtag_opportunities": [{"tag": "#noshows", "reason": "..."}],
  "content_gaps": ["..."],
  "raw_counts": {"youtube": 12, "instagram_hashtags": 0, "instagram_reels": 0, "calendar_events": 4},
  "analyzed_at": "2026-04-10T14:00:00"
}
```

### `data/strategy_brief.json` (output of `strategy.py`)
See "the brief schema" in §3.1.

### `data/jobs/{episode_id}.json` (output of `engine.py`)
See §3.7.

---

## Concurrency model

- `apify_scout`: sequential HTTP polling to Apify (no concurrency — Apify is
  rate-limited and the actors are slow).
- `strategy`: single Opus call. No concurrency.
- `engine`: writers run in **parallel threads** via
  `concurrent.futures.ThreadPoolExecutor`. Judge and polish are sequential.
- Disk I/O: each stage writes its own file atomically (`.write_text(json.dumps(...))`).
  No locks needed because no two stages run concurrently within a single run.

## Idempotency

Re-running any stage overwrites its output file with a fresh result. Re-running
`engine.py` against the same brief will produce a NEW episode_id (timestamped),
so previous jobs are never overwritten.

## Error budget per stage

| Stage | Soft fail | Hard fail |
|---|---|---|
| Apify Scout | Empty results, Claude error | Never — always produces a `trend_signals.json` even if empty |
| Strategy | Calendar empty, trends stale | JSON parse failure on Opus reply |
| Engine | Single writer fail, judge malformed, gate fail | All writers fail in all 3 rounds, AND polish fails |

## What "good" looks like

A run is "good" when the operator can read `data/jobs/{id}.json#video_script`,
nod, and forward it to a video stage without rewriting a single word.

A run is "great" when the operator reads it and feels uncomfortable because
they recognise themselves in the friend's struggle.
