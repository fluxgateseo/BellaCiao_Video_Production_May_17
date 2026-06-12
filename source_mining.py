"""
source_mining.py — Skill 1: Source Mining

Automated research layer that pulls emerging topics, trends, and conversations
from high-signal sources relevant to the restaurant/SEO niche.

Sources:
  - Apify scrapers (YouTube Shorts, IG Hashtags, IG Reels) — via apify_scout.py
  - Google Trends (restaurant-related queries by market)
  - RSS feeds (configurable industry blogs/publications)

Output: data/research_signals.json — timestamped array of raw signals.

Usage:
    python3 source_mining.py                    # all sources
    python3 source_mining.py --source apify     # specific source
    python3 source_mining.py --source rss
    python3 source_mining.py --source trends
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BASE_DIR       = Path(__file__).parent
SIGNALS_FILE   = BASE_DIR / "data" / "research_signals.json"
SOURCES_FILE   = BASE_DIR / "data" / "research_sources.json"


# ─── Default research sources ──────────────────────────────────────────────

DEFAULT_SOURCES = {
    "rss_feeds": [
        {"name": "Restaurant Dive", "url": "https://www.restaurantdive.com/feeds/news/"},
        {"name": "Modern Restaurant Management", "url": "https://modernrestaurantmanagement.com/feed/"},
        {"name": "Nation's Restaurant News", "url": "https://www.nrn.com/rss.xml"},
        {"name": "Eater", "url": "https://www.eater.com/rss/index.xml"},
    ],
    "google_trends_queries": [
        "restaurant SEO",
        "Google Maps restaurant",
        "restaurant marketing",
        "restaurant booking online",
        "restaurant Google profile",
    ],
    "twitter_queries": [
        "restaurant Google Maps -is:retweet lang:en",
        "restaurant SEO tips -is:retweet lang:en",
        "Google Business Profile restaurant -is:retweet lang:en",
    ],
    "markets": ["AU", "US", "UK"],
}


def _load_sources() -> dict:
    if SOURCES_FILE.exists():
        return json.loads(SOURCES_FILE.read_text())
    # Write defaults on first run
    SOURCES_FILE.parent.mkdir(parents=True, exist_ok=True)
    SOURCES_FILE.write_text(json.dumps(DEFAULT_SOURCES, indent=2))
    return DEFAULT_SOURCES


# ─── Source: Apify (existing scraper) ───────────────────────────────────────

def _mine_apify() -> list[dict]:
    """Pull signals from the existing Apify trend scout."""
    signals: list[dict] = []
    try:
        from apify_scout import run as run_scout, get_trend_context
        run_scout()
        context = get_trend_context()
        if context and "No trend data" not in context:
            signals.append({
                "source": "apify",
                "market": "ALL",
                "raw_content": context,
                "fetched_at": datetime.now().isoformat(timespec="seconds"),
                "relevance": "high",
            })
    except Exception as e:
        print(f"  [source-mining] apify failed: {e}")
    return signals


# ─── Source: RSS Feeds ──────────────────────────────────────────────────────

def _mine_rss(sources: dict) -> list[dict]:
    """Pull recent articles from configured RSS feeds."""
    signals: list[dict] = []
    try:
        import feedparser
    except ImportError:
        print("  [source-mining] RSS skipped — `pip install feedparser` to enable")
        return signals

    for feed_config in sources.get("rss_feeds", []):
        name = feed_config.get("name", "unknown")
        url = feed_config.get("url", "")
        if not url:
            continue
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:  # top 5 per feed
                signals.append({
                    "source": "rss",
                    "feed_name": name,
                    "market": "ALL",
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", "")[:500],
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "raw_content": f"{entry.get('title', '')} — {entry.get('summary', '')[:300]}",
                    "fetched_at": datetime.now().isoformat(timespec="seconds"),
                    "relevance": "medium",
                })
        except Exception as e:
            print(f"  [source-mining] RSS {name} failed: {e}")
    return signals


# ─── Source: Google Trends (lightweight) ────────────────────────────────────

def _mine_trends(sources: dict) -> list[dict]:
    """
    Pull Google Trends' daily "Trending Searches" RSS for each market (AU/US/UK).
    This is the topic/category-level feed, not per-query — much more reliable
    than the per-query RSS (which returns empty for most niche queries).

    Each market's RSS returns ~20 top trending searches of the day. We then
    filter to keep only food/restaurant-adjacent ones using a keyword list.
    """
    signals: list[dict] = []
    try:
        import feedparser
    except ImportError:
        print("  [source-mining] trends skipped — `pip install feedparser` to enable")
        return signals

    # Market → Google Trends geo code mapping
    GEO_MAP = {"AU": "AU", "US": "US", "UK": "GB"}
    markets = sources.get("markets", ["AU", "US", "UK"])

    # Food/restaurant-relevance filter — keep only trends that touch the niche
    RESTAURANT_KEYWORDS = {
        "restaurant", "food", "menu", "dining", "chef", "cuisine", "brunch",
        "lunch", "dinner", "takeaway", "delivery", "cafe", "coffee", "bar",
        "pub", "bakery", "recipe", "eatery", "michelin", "google maps",
        "michelin star", "open", "reservation", "booking", "yelp", "tipping",
        "mfwf", "food festival", "food guide", "beard", "food tour",
    }

    for market in markets:
        geo = GEO_MAP.get(market, "US")
        try:
            url = f"https://trends.google.com/trending/rss?geo={geo}"
            feed = feedparser.parse(url)
            kept = 0
            for entry in feed.entries[:25]:
                title = (entry.get("title", "") or "").lower()
                summary = (entry.get("summary", "") or "").lower()
                combined = f"{title} {summary}"
                # Keep only food/restaurant-adjacent trends
                if not any(kw in combined for kw in RESTAURANT_KEYWORDS):
                    continue
                signals.append({
                    "source":       "google_trends",
                    "market":       market,
                    "geo":          geo,
                    "title":        entry.get("title", ""),
                    "raw_content":  f"{entry.get('title','')} — {entry.get('summary','')[:200]}",
                    "traffic":      entry.get("ht_approx_traffic", ""),
                    "picture":      entry.get("ht_picture", ""),
                    "fetched_at":   datetime.now().isoformat(timespec="seconds"),
                    "relevance":    "high" if market in ("AU", "US", "UK") else "medium",
                })
                kept += 1
            print(f"    {market} ({geo}): {kept} restaurant-relevant trends")
        except Exception as e:
            print(f"  [source-mining] trends {market} failed: {e}")
    return signals


# ─── Main mining function ──────────────────────────────────────────────────

def mine_all(source_filter: Optional[str] = None) -> dict:
    """
    Run all configured source miners and write research_signals.json.

    Args:
        source_filter: if set, only run this source ('apify', 'rss', 'trends')

    Returns:
        {"signals": [...], "total": N, "mined_at": "..."}
    """
    sources = _load_sources()
    all_signals: list[dict] = []

    miners = {
        "apify":  lambda: _mine_apify(),
        "rss":    lambda: _mine_rss(sources),
        "trends": lambda: _mine_trends(sources),
    }

    for name, miner in miners.items():
        if source_filter and name != source_filter:
            continue
        print(f"  mining {name}...")
        signals = miner()
        print(f"    → {len(signals)} signals")
        all_signals.extend(signals)

    payload = {
        "mined_at": datetime.now().isoformat(timespec="seconds"),
        "total": len(all_signals),
        "source_filter": source_filter,
        "signals": all_signals,
    }

    SIGNALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SIGNALS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"\n  wrote {SIGNALS_FILE} ({len(all_signals)} signals)")

    return payload


# ─── CLI ────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Skill 1 — Source Mining")
    p.add_argument("--source", choices=["apify", "rss", "trends"],
                   help="mine a specific source only (default: all)")
    args = p.parse_args()
    mine_all(source_filter=args.source)


if __name__ == "__main__":
    main()
