---
name: Data contracts
description: JSON schemas for the four data files that flow between stages — friends, calendar, trend_signals, strategy_brief, jobs
type: reference
---

Stage handoffs are JSON files in `data/`. The canonical schema reference lives in [docs/PIPELINE.md](../docs/PIPELINE.md) "Data contracts" section. Quick map:

- **`data/friends.json`** — 8 canonical friends (Naomi, Sal, Jake, Enzo & Maria, Yasmin, Danny, Arun & Priya, Sophie). Each has `id` (slug used by --friend), `name`, `age`, `nationality`, `location` (NY/London/Melbourne ONLY), `restaurant_style`, `archetype_owned`, `sensory_food_hook`, `pillar_affinity`, `enemy_archetype`, `yt_seo_title`. Couples have `is_couple`, `partner_name`, optional `child` (used silently for "what the parent almost missed" stories).
- **`data/calendar.json`** — 40+ restaurant events. Each: `name`, `countries`, `type` (`fixed` | `nth_weekday` | `cultural`), date fields, `revenue_tier` (1=highest), `campaign_window_days`, `content_angles`, `storytelling_hook`. Tier 1 in window → ALL content MUST reference; Tier 2 → 2/3; Tier 3 → 1/3.
- **`data/trend_signals.json`** — apify_scout output. Fields: `this_week_priority`, `timely_hooks[]`, `trending_formats[]`, `hashtag_opportunities[]`, `content_gaps[]`, `raw_counts`, `analyzed_at`. Expires after 24h.
- **`data/strategy_brief.json`** — strategy.py output. The single brief: `format`, `pillar`, `calendar_event`, `friend`, `enemy`, `ally`, `tone`, `target_duration_seconds`, `food_hook_hint`, `trend_anchor`, `director_note`.
- **`data/jobs/{episode_id}.json`** — engine.py final output. Fields: `episode_id` (`bella_{friend}_p{pillar}_{ts}`), `brief`, `round`, `score`, `verdict`, `script`, `story_spine`, `video_script`, `caption`, `scene_brief`, `gates`, `near_perfect_override`, `generated_at`.

**How to apply:** Read the live schemas from docs/PIPELINE.md before changing any stage's outputs — these contracts are how stages stay independently runnable. Adding a field means updating both the producing stage and the consuming stage's reader. New friends/events go into the JSON files, not into code.
