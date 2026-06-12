"""
competitive.py — Skill 3: Competitive Ideation

Evaluates analyzed research against the competitive landscape. Identifies
content gaps, engagement patterns, and strategic positioning. Outputs a
ranked list of content opportunities with rationale.

Model: Claude Sonnet
Input: data/analysis_brief.json + data/trend_signals.json + friends_db.json
Output: data/content_opportunities.json

Usage:
    python3 competitive.py
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BASE_DIR            = Path(__file__).parent
ANALYSIS_FILE       = BASE_DIR / "data" / "analysis_brief.json"
FRIENDS_FILE        = BASE_DIR / "data" / "friends_db.json"
OPPORTUNITIES_FILE  = BASE_DIR / "data" / "content_opportunities.json"
ANTHROPIC_KEY       = os.getenv("ANTHROPIC_API_KEY", "")
MODEL_SONNET        = "claude-sonnet-4-6"


COMPETITIVE_PROMPT = """You are the Content Strategist for the Bella content engine.

Bella creates short-form video content (Instagram Stories ~30s, Reels 30-60s) plus
derivative blog posts, Twitter threads, and social posts about restaurant SEO. Her
audience is independent restaurant operators in Melbourne (AU), NYC (US), and London (UK).

She has 8 canonical friends — real restaurant operators whose stories she tells:
{friends_summary}

Below is the ANALYSIS BRIEF from the research pipeline (themes, angles, timing
windows) plus the available TREND DATA from competitor content scraping.

Your job: evaluate this intelligence against the competitive landscape and produce
a RANKED list of content opportunities. Each opportunity should be:
1. Something competitors are NOT covering (gap)
2. Tied to a specific friend from the list above (friend_fit)
3. Actionable within the next 14 days (urgency)
4. Clear about WHY this angle works (rationale)

Return ONLY valid JSON — an array of 8-12 opportunity objects:
[
  {{
    "rank": 1,
    "angle": "string — the content angle in one sentence",
    "gap": "string — what competitors are missing",
    "format_recommendation": "story | reel | both | reel + blog",
    "friend_fit": ["friend_id"],
    "market": "AU | US | UK | ALL",
    "urgency": "high | medium | low",
    "rationale": "string — 2-3 sentences on why this angle, why now",
    "suggested_hook_doctrine": "1-Callout | 2-Counter-Intuitive | 3-Number | 4-POV | 5-Truth | 6-Real Event | 7-Cold Open",
    "pillar": 1
  }}
]

ANALYSIS BRIEF:
{analysis_text}

TREND DATA:
{trend_text}
"""


def _friends_summary() -> str:
    """One-line summary per friend for the prompt."""
    if not FRIENDS_FILE.exists():
        return "(friends_db.json missing)"
    db = json.loads(FRIENDS_FILE.read_text())
    items = db.get("friends", db) if isinstance(db, dict) else db
    lines = []
    for f in items:
        lines.append(
            f"  {f['id']:12} — {f.get('name','')} / {f.get('city','')} / "
            f"{f.get('cuisine','')} / enemy: {f.get('enemy_archetype','')}"
        )
    return "\n".join(lines)


def generate_opportunities() -> list[dict]:
    """
    Evaluate research + trends against the competitive landscape.
    Returns ranked content opportunities and writes to data/content_opportunities.json.
    """
    # Load analysis brief
    if not ANALYSIS_FILE.exists():
        raise FileNotFoundError(
            f"{ANALYSIS_FILE} not found — run `python3 analysis.py` first"
        )
    analysis = json.loads(ANALYSIS_FILE.read_text())
    analysis_text = json.dumps(analysis, indent=2)[:3000]

    # Load trend data (optional)
    trend_file = BASE_DIR / "data" / "trend_signals.json"
    trend_text = "(no trend data)"
    if trend_file.exists():
        try:
            trend_data = json.loads(trend_file.read_text())
            trend_text = json.dumps(trend_data, indent=2)[:2000]
        except Exception:
            pass

    from llm_client import call_with_fallback
    prompt = COMPETITIVE_PROMPT.format(
        friends_summary=_friends_summary(),
        analysis_text=analysis_text,
        trend_text=trend_text,
    )
    raw = call_with_fallback(
        primary=MODEL_SONNET,
        prompt=prompt,
        max_tokens=3000,
        caller_name="competitive",
    )

    # Parse JSON
    try:
        text = raw.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0]
        elif text.startswith("```"):
            text = text.split("```", 2)[1].split("```", 1)[0]
        opportunities = json.loads(text.strip())
    except json.JSONDecodeError:
        opportunities = [{"raw_response": raw, "parse_error": True}]

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": MODEL_SONNET,
        "total": len(opportunities),
        "opportunities": opportunities,
    }

    OPPORTUNITIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    OPPORTUNITIES_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"[competitive] wrote {OPPORTUNITIES_FILE} ({len(opportunities)} opportunities)")

    for opp in opportunities[:5]:
        if isinstance(opp, dict) and not opp.get("parse_error"):
            print(f"  #{opp.get('rank','?')} [{opp.get('urgency','?')}] "
                  f"{opp.get('angle','?')[:70]}")

    return opportunities


# ─── CLI ───────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Skill 3 — Competitive Ideation")
    p.parse_args()
    generate_opportunities()


if __name__ == "__main__":
    main()
