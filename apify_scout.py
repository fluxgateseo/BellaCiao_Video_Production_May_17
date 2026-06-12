"""
apify_scout.py — Apify-powered trend scraping for the script engine.

Distilled from video_pipeline/agent_11_trend_scout.py — keeps only the bits the
script engine needs:
  1. Scrape YouTube + Instagram restaurant content via Apify actors
  2. Hand the raw data to Claude for synthesis into actionable signals
  3. Save to data/trend_signals.json (consumed by strategy.py)

Required env vars (in .env at project root or script_engine/):
  APIFY_TOKEN
  APIFY_YT_ACTOR_ID            (default: h7sDV53CddomktSi5)
  APIFY_IG_HASHTAG_ACTOR_ID    (optional — IG hashtag scraper)
  APIFY_IG_REEL_ACTOR_ID       (optional — IG Reels scraper)
  ANTHROPIC_API_KEY
"""

import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv
from network_probe import require_host

# API keys are loaded from the shared Bellaciao Content/.env (parent folder),
# so every project under Bellaciao Content/ uses the same credentials file.
load_dotenv(Path(__file__).parent.parent / ".env")

BASE_DIR = Path(__file__).parent
SIGNALS_FILE = BASE_DIR / "data" / "trend_signals.json"

APIFY_TOKEN              = os.getenv("APIFY_TOKEN", "")
APIFY_YT_SCRAPER         = os.getenv("APIFY_YT_ACTOR_ID", "h7sDV53CddomktSi5")
APIFY_IG_HASHTAG_SCRAPER = os.getenv("APIFY_IG_HASHTAG_ACTOR_ID", "")
APIFY_IG_REEL_SCRAPER    = os.getenv("APIFY_IG_REEL_ACTOR_ID", "")
ANTHROPIC_API_KEY        = os.getenv("ANTHROPIC_API_KEY", "")

# Search seeds for the restaurant/hospitality niche
YT_SEARCH_QUERIES = [
    "restaurant no shows solution",
    "AI for restaurants",
    "restaurant booking system",
    "restaurant owner tips",
    "hospitality technology 2026",
]
IG_HASHTAGS = [
    "restaurantlife", "restaurantowner", "noshows",
    "hospitalitylife", "restauranttech", "cheflife",
]

# ─── Apify helpers ───────────────────────────────────────────────────────────

def _run_actor(actor_id: str, input_data: dict, timeout: int = 120) -> list:
    """Start an Apify actor run, poll until done, return dataset items."""
    if not APIFY_TOKEN or not actor_id:
        return []
    try:
        require_host("api.apify.com", "Apify")
    except Exception as e:
        print(f"  [Apify] skipped: {e}")
        return []

    start_url = f"https://api.apify.com/v2/acts/{actor_id}/runs?token={APIFY_TOKEN}"
    try:
        r = requests.post(start_url, json=input_data, timeout=30)
        r.raise_for_status()
        run_id = r.json().get("data", {}).get("id")
        if not run_id:
            return []
    except Exception as e:
        print(f"  [Apify] start failed for {actor_id}: {e}")
        return []

    poll_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}"
    elapsed, dataset_id = 0, ""
    while elapsed < timeout:
        time.sleep(10)
        elapsed += 10
        try:
            data = requests.get(poll_url, timeout=15).json().get("data", {})
            status = data.get("status", "")
            if status == "SUCCEEDED":
                dataset_id = data.get("defaultDatasetId", "")
                break
            if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                print(f"  [Apify] run {run_id} {status}")
                return []
        except Exception:
            continue

    if not dataset_id:
        print(f"  [Apify] run {run_id} timed out after {timeout}s")
        return []

    items_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_TOKEN}&limit=50"
    try:
        return requests.get(items_url, timeout=30).json()
    except Exception as e:
        print(f"  [Apify] dataset fetch failed: {e}")
        return []


def scrape_youtube() -> list:
    if not APIFY_TOKEN:
        return []
    print("  [Apify] scraping YouTube restaurant trends...")
    items = _run_actor(APIFY_YT_SCRAPER, {
        "searchQueries": YT_SEARCH_QUERIES,
        "maxResults": 10,
        "maxResultsShorts": 5,
        "downloadSubtitles": False,
    }, timeout=120)
    print(f"  [Apify] {len(items)} YouTube items")
    return items


def scrape_instagram_hashtags() -> list:
    if not APIFY_TOKEN or not APIFY_IG_HASHTAG_SCRAPER:
        return []
    print("  [Apify] scraping Instagram hashtags...")
    items = _run_actor(APIFY_IG_HASHTAG_SCRAPER, {
        "hashtags": IG_HASHTAGS,
        "resultsLimit": 20,
    }, timeout=120)
    print(f"  [Apify] {len(items)} IG hashtag items")
    return items


def scrape_instagram_reels() -> list:
    """
    Scrape IG Reels from curated restaurant-marketing profiles. The
    `apify/instagram-reel-scraper` actor wants `username` or `directUrls`,
    NOT hashtags (that's a different actor). This list is the same one
    recommended in the Apify hashtag scraper setup — creators who publish
    restaurant-marketing + local-SEO content.
    """
    if not APIFY_TOKEN or not APIFY_IG_REEL_SCRAPER:
        return []
    print("  [Apify] scraping Instagram Reels...")
    # Profile usernames to scrape reels from (restaurant marketing creators)
    IG_PROFILES = [
        "thedigitalrestaurant",
        "restaurantmarketingtips",
        "nextrestaurants",
        "therestaurantboss",
    ]
    items = _run_actor(APIFY_IG_REEL_SCRAPER, {
        "username":     IG_PROFILES,
        "resultsLimit": 10,
    }, timeout=180)
    print(f"  [Apify] {len(items)} IG Reel items")
    return items


# ─── Synthesise signals with Claude ──────────────────────────────────────────

def _analyze_with_claude(yt_items: list, ig_items: list, calendar_events: list) -> dict:
    """Hand raw scraped data to Claude Haiku, get back actionable JSON signals."""
    import anthropic
    require_host("api.anthropic.com", "Anthropic")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Format competitor IG posts (sorted by engagement)
    ig_text = ""
    if ig_items:
        for h in ig_items:
            h["_eng"] = (h.get("likesCount", 0) or 0) + (h.get("commentsCount", 0) or 0)
        for h in sorted(ig_items, key=lambda x: x.get("_eng", 0), reverse=True)[:8]:
            caption = (h.get("caption", "") or "")[:120]
            ig_text += (
                f"- @{h.get('ownerUsername','?')} "
                f"({h.get('likesCount',0)}❤ {h.get('commentsCount',0)}💬): "
                f"\"{caption}...\"\n"
            )

    # Format YouTube
    yt_text = ""
    if yt_items:
        for v in yt_items[:8]:
            yt_text += (
                f"- {v.get('title','')[:100]} "
                f"({v.get('viewCount',0)} views, "
                f"channel @{v.get('channelName','?')} "
                f"{v.get('numberOfSubscribers',0)} subs)\n"
            )

    # Format calendar
    cal_text = ""
    for e in (calendar_events or [])[:5]:
        cal_text += f"- {e.get('name','')} in {e.get('days_until','?')} days\n"

    prompt = f"""You are the Trend Scout for Bellaciao.ai — an AI receptionist for restaurants.
The 8 friends in our story universe (one must be picked for each script):
naomi (NYC seafood), sal (NYC Italian), jake (Melbourne brunch), enzo_maria
(Melbourne Italian, family), yasmin (London Lebanese), danny (London gastropub),
arun_priya (London Indian, couple), sophie (Melbourne fine dining).

Analyse the trending data below and output JSON with content recommendations.

UPCOMING CALENDAR EVENTS:
{cal_text or "(none in window)"}

TRENDING IG POSTS IN RESTAURANT NICHE:
{ig_text or "(no IG data)"}

TRENDING YOUTUBE VIDEOS:
{yt_text or "(no YT data)"}

Output ONLY this JSON, nothing else:
{{
  "this_week_priority": "one sentence — the single most important angle this week",
  "timely_hooks": [
    {{"hook": "specific sensory hook text", "friend": "friend_id", "pillar": 1, "urgency": "high"}}
  ],
  "trending_formats": [
    {{"format": "format name", "bella_adaptation": "how to use it"}}
  ],
  "hashtag_opportunities": [{{"tag": "#tag", "reason": "why"}}],
  "content_gaps": ["specific gap"],
  "analyzed_at": "{datetime.now().isoformat()}"
}}
"""
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```", 2)[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rsplit("```", 1)[0].strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Find outermost {...}
            start = raw.find("{")
            depth = 0
            for i in range(start, len(raw)):
                if raw[i] == "{":
                    depth += 1
                elif raw[i] == "}":
                    depth -= 1
                    if depth == 0:
                        return json.loads(raw[start:i + 1])
            raise
    except Exception as e:
        print(f"  [Trend Scout] Claude analysis failed: {e}")
        return {"error": str(e), "analyzed_at": datetime.now().isoformat()}


# ─── Public entry point ──────────────────────────────────────────────────────

def run() -> dict:
    """Full scrape + analyse cycle. Saves data/trend_signals.json."""
    print("\n[Apify Scout] Scanning competitor restaurant content...")

    yt = scrape_youtube()
    ig_hash = scrape_instagram_hashtags()
    ig_reels = scrape_instagram_reels()

    # Lazy import — strategy.py owns the calendar logic
    try:
        from strategy import upcoming_events
        events = upcoming_events(days_ahead=14)
    except Exception:
        events = []

    signals = _analyze_with_claude(yt, ig_hash + ig_reels, events)
    signals["raw_counts"] = {
        "youtube": len(yt),
        "instagram_hashtags": len(ig_hash),
        "instagram_reels": len(ig_reels),
        "calendar_events": len(events),
    }

    SIGNALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SIGNALS_FILE.write_text(json.dumps(signals, indent=2))
    print(f"  [Apify Scout] saved → {SIGNALS_FILE.name}")
    print(f"  Priority: {signals.get('this_week_priority', '(none)')}")
    return signals


def get_trend_context() -> str:
    """Return a formatted prompt block of trend signals (consumed by strategy.py)."""
    if not SIGNALS_FILE.exists():
        return "No trend data available. Run apify_scout.run() first."

    signals = json.loads(SIGNALS_FILE.read_text())

    # Stale after 24h
    try:
        age = datetime.now() - datetime.fromisoformat(signals.get("analyzed_at", ""))
        if age > timedelta(hours=24):
            return "Trend data is stale (>24h). Re-run apify_scout.run()."
    except Exception:
        pass

    lines = []
    if signals.get("this_week_priority"):
        lines.append(f"THIS WEEK'S PRIORITY: {signals['this_week_priority']}")

    if signals.get("timely_hooks"):
        lines.append("\nTIMELY HOOKS:")
        for h in signals["timely_hooks"][:5]:
            lines.append(
                f"  [{h.get('urgency','?').upper()}] \"{h.get('hook','')}\" "
                f"→ friend: {h.get('friend','any')}, pillar: {h.get('pillar','?')}"
            )

    if signals.get("trending_formats"):
        lines.append("\nTRENDING FORMATS:")
        for f in signals["trending_formats"][:3]:
            lines.append(f"  - {f.get('format','')}: {f.get('bella_adaptation','')}")

    if signals.get("hashtag_opportunities"):
        lines.append("\nHASHTAG OPPORTUNITIES:")
        for t in signals["hashtag_opportunities"][:5]:
            lines.append(f"  - {t.get('tag','')}: {t.get('reason','')}")

    if signals.get("content_gaps"):
        lines.append("\nCONTENT GAPS:")
        for g in signals["content_gaps"][:3]:
            lines.append(f"  - {g}")

    return "\n".join(lines) or "No actionable trend signals."


if __name__ == "__main__":
    out = run()
    print(json.dumps(out, indent=2))
